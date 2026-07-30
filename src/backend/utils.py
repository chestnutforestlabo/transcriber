import json
import os
import shutil
from collections import defaultdict

from pyannote.core import Segment

PUNC_SENT_END = [".", "?", "!", "、", "。"]

# A second speaker must occupy at least this much time, or this ratio of the
# ASR segment, before word-level speaker assignment is enabled.
MIN_SIGNIFICANT_SPEAKER_DURATION = 0.5
MIN_SIGNIFICANT_SPEAKER_RATIO = 0.30

# A brief interruption surrounded by the main speaker is treated as a
# backchannel and kept with the main speaker.
MAX_BACKCHANNEL_DURATION = 0.6
BACKCHANNEL_BOUNDARY_TOLERANCE = 0.15


def _unpack_asr_item(item):
    """Return ``(segment, text, words)`` for legacy and word-aware ASR output."""
    if len(item) < 2:
        raise ValueError("ASR output items must contain at least a segment and text.")
    words = item[2] if len(item) >= 3 else None
    return item[0], item[1], words


def _normalize_word(word):
    """Convert supported word timestamp shapes into ``(Segment, text)``."""
    if isinstance(word, dict):
        start = word.get("start")
        end = word.get("end")
        text = word.get("word", word.get("text", ""))
        if start is None or end is None:
            return None
        return Segment(float(start), float(end)), str(text)

    if isinstance(word, (tuple, list)) and len(word) >= 2:
        segment = word[0]
        if isinstance(segment, Segment):
            return segment, str(word[1])

    return None


def _speaker_intervals(segment, ann):
    """Return diarization intervals cropped to an ASR segment."""
    cropped = ann.crop(segment, mode="intersection")
    intervals = [
        (subsegment, label)
        for subsegment, _, label in cropped.itertracks(yield_label=True)
        if subsegment.duration > 0.0
    ]
    return sorted(intervals, key=lambda item: (item[0].start, item[0].end))


def _speaker_durations(intervals):
    durations = defaultdict(float)
    for segment, label in intervals:
        durations[label] += segment.duration
    return durations


def _is_brief_interruption(interval, label, intervals, main_speaker):
    if label == main_speaker or interval.duration >= MAX_BACKCHANNEL_DURATION:
        return False

    before = any(
        other_label == main_speaker
        and other.start < interval.start
        and other.end >= interval.start - BACKCHANNEL_BOUNDARY_TOLERANCE
        for other, other_label in intervals
    )
    after = any(
        other_label == main_speaker
        and other.end > interval.end
        and other.start <= interval.end + BACKCHANNEL_BOUNDARY_TOLERANCE
        for other, other_label in intervals
    )
    return before and after


def _remove_brief_backchannels(intervals, main_speaker):
    return [
        (segment, label)
        for segment, label in intervals
        if not _is_brief_interruption(
            segment,
            label,
            intervals,
            main_speaker,
        )
    ]


def _has_significant_speaker_change(segment, durations, main_speaker):
    if main_speaker is None or segment.duration <= 0.0:
        return False

    for speaker, duration in durations.items():
        if speaker == main_speaker:
            continue
        if (
            duration >= MIN_SIGNIFICANT_SPEAKER_DURATION
            or duration / segment.duration >= MIN_SIGNIFICANT_SPEAKER_RATIO
        ):
            return True
    return False


def _speaker_for_word(word_segment, intervals, main_speaker):
    durations = defaultdict(float)
    for diar_segment, speaker in intervals:
        overlap = min(word_segment.end, diar_segment.end) - max(
            word_segment.start,
            diar_segment.start,
        )
        if overlap > 0.0:
            durations[speaker] += overlap

    if not durations:
        return main_speaker

    # Prefer the main speaker when overlap durations tie.
    return max(
        durations,
        key=lambda speaker: (durations[speaker], speaker == main_speaker),
    )


def _split_words_by_speaker(words, intervals, main_speaker):
    assigned_words = []
    for word in words or []:
        normalized = _normalize_word(word)
        if normalized is None:
            continue
        word_segment, word_text = normalized
        speaker = _speaker_for_word(word_segment, intervals, main_speaker)
        assigned_words.append((word_segment, speaker, word_text))

    if not assigned_words or len({item[1] for item in assigned_words}) < 2:
        return []

    groups = []
    current = []
    for item in assigned_words:
        if current and item[1] != current[-1][1]:
            groups.append(current)
            current = [item]
        else:
            current.append(item)
    if current:
        groups.append(current)

    split_segments = []
    for group in groups:
        start = group[0][0].start
        end = group[-1][0].end
        text = "".join(item[2] for item in group).strip()
        if text and end >= start:
            split_segments.append((Segment(start, end), group[0][1], text))
    return split_segments


def add_speaker_info_to_text(timestamp_texts, ann):
    spk_text = []
    for item in timestamp_texts:
        seg, text, words = _unpack_asr_item(item)
        intervals = _speaker_intervals(seg, ann)
        durations = _speaker_durations(intervals)
        if durations:
            speaker = max(durations, key=durations.get)
        else:
            speaker = None

        effective_intervals = _remove_brief_backchannels(intervals, speaker)
        effective_durations = _speaker_durations(effective_intervals)
        if words and _has_significant_speaker_change(
            seg,
            effective_durations,
            speaker,
        ):
            split_segments = _split_words_by_speaker(
                words,
                effective_intervals,
                speaker,
            )
            if split_segments:
                spk_text.extend(split_segments)
                continue

        spk_text.append((seg, speaker, text))
    return spk_text


def merge_cache(text_cache):
    sentence = "".join([item[-1] for item in text_cache])
    spk = text_cache[0][1]
    start = text_cache[0][0].start
    end = text_cache[-1][0].end
    return Segment(start, end), spk, sentence


def merge_sentence(spk_text):
    merged_spk_text = []
    pre_spk = None
    text_cache = []
    for seg, spk, text in spk_text:
        if spk != pre_spk and pre_spk is not None and len(text_cache) > 0:
            merged_spk_text.append(merge_cache(text_cache))
            text_cache = [(seg, spk, text)]
            pre_spk = spk

        elif text and len(text) > 0 and text[-1] in PUNC_SENT_END and spk != pre_spk:
            text_cache.append((seg, spk, text))
            merged_spk_text.append(merge_cache(text_cache))
            text_cache = []
            pre_spk = spk
        else:
            text_cache.append((seg, spk, text))
            pre_spk = spk
    if len(text_cache) > 0:
        merged_spk_text.append(merge_cache(text_cache))
    merged_spk_text = fill_null_speaker(merged_spk_text)
    merged_spk_text = merge_consecutive_speaker(merged_spk_text)
    return merged_spk_text


def merge_consecutive_speaker(spk_sent):
    merged = []
    for seg, spk, text in spk_sent:
        if merged and merged[-1][1] == spk:
            prev_seg, _, prev_text = merged[-1]
            new_seg = Segment(prev_seg.start, seg.end)
            new_text = prev_text + " " + text
            merged[-1] = (new_seg, spk, new_text)
        else:
            merged.append((seg, spk, text))
    return merged


def fill_null_speaker(spk_sent):
    filled = []
    for i, (seg, spk, text) in enumerate(spk_sent):
        if spk is None:
            prev_spk = filled[-1][1] if i > 0 else None
            next_spk = spk_sent[i + 1][1] if i + 1 < len(spk_sent) else None
            spk = prev_spk or next_spk or "unknown"
        filled.append((seg, spk, text))
    return filled


def diarize_text(args, automatic_speech_recognition_output, diarization_result):
    spk_text = add_speaker_info_to_text(
        automatic_speech_recognition_output, diarization_result
    )
    merged_output = merge_sentence(spk_text)
    return merged_output


def write_to_txt(spk_sent, file):
    with open(file, "w") as fp:
        for seg, spk, sentence in spk_sent:
            line = f"{seg.start:.2f} {seg.end:.2f} {spk} {sentence}\n"
            fp.write(line)


def save_transcripts_json(args, output_data, file_name, metadata=None):
    serializable = []
    prev_end = 0.0
    for i, item in enumerate(output_data):
        seg, speaker, text = item
        start = float(seg.start)
        end = float(seg.end)
        if i > 0 and start > prev_end:
            serializable[i - 1]["end"] = start
        serializable.append(
            {"start": start, "end": end, "speaker": speaker, "text": text}
        )
        prev_end = end
    # Save speech recognition results in JSON format in two locations (frontend・backup)
    output_dirs = ["src/frontend/public/transcripts", f"outputs/{file_name}"]
    for output_dir in output_dirs:
        os.makedirs(output_dir, exist_ok=True)
        output_file_path = os.path.join(output_dir, f"{file_name}.json")
        payload = (
            {"meta": metadata, "transcripts": serializable}
            if metadata is not None
            else serializable
        )
        with open(output_file_path, "w", encoding="utf-8") as json_file:
            json.dump(payload, json_file, ensure_ascii=False, indent=2)
        if output_dir == output_dirs[1]:
            txt_file_path = os.path.join(output_dir, f"{file_name}.txt")
            with open(txt_file_path, "w", encoding="utf-8") as txt_file:
                for item in serializable:
                    line = (
                        f"{item['start']:.2f} {item['end']:.2f} "
                        f"{item['speaker']}:{item['text']}\n"
                    )
                    txt_file.write(line)
    # Copy audio
    audio_paths = ["src/frontend/public/audios", f"outputs/{file_name}"]
    for audio_path in audio_paths:
        shutil.copy2(os.path.join(args.audio_dir, f"{file_name}.wav"), audio_path)


def save_index_json(file_names):
    os.makedirs("src/frontend/public/audios", exist_ok=True)
    index_paths = ["src/frontend/public/audios/index.json", "outputs/index.json"]
    for index_path in index_paths:
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    data = []
        else:
            data = []
        if isinstance(file_names, list):
            for item in file_names:
                if item not in data:
                    data.append(item)
        else:
            if file_names not in data:
                data.append(file_names)

        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
