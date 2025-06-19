from pyannote.core import Segment, Annotation, Timeline
from collections import defaultdict
import json
import os
import shutil

PUNC_SENT_END = ['.', '?', '!', '、', '。']

# def add_speaker_info_to_text(timestamp_texts, ann):
#     spk_text = []
#     for seg, text in timestamp_texts:
#         spk = ann.crop(seg).argmax()
#         spk_text.append((seg, spk, text))
#     return spk_text

def add_speaker_info_to_text(timestamp_texts, ann):
    spk_text = []
    for seg, text in timestamp_texts:
        cropped = ann.crop(seg, mode="loose")
        durations = defaultdict(float)
        for subseg, _, label in cropped.itertracks(yield_label=True):
            durations[label] += subseg.duration
            speaker = max(durations, key=durations.get)
        spk_text.append((seg, speaker, text))
    return spk_text

def merge_cache(text_cache):
    sentence = ''.join([item[-1] for item in text_cache])
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

        elif text and len(text) > 0 and text[-1] in PUNC_SENT_END:
            text_cache.append((seg, spk, text))
            merged_spk_text.append(merge_cache(text_cache))
            text_cache = []
            pre_spk = spk
        else:
            text_cache.append((seg, spk, text))
            pre_spk = spk
    if len(text_cache) > 0:
        merged_spk_text.append(merge_cache(text_cache))
    return merged_spk_text

def diarize_text(args, AutomaticSpeechRecognition_output, diarization_result):
    # pyannote/speaker-diarization-3.1
    if not args.diarization_time:
        spk_text = add_speaker_info_to_text(AutomaticSpeechRecognition_output, diarization_result)
        merged_output = merge_sentence(spk_text)
    # pyannote/embedding
    else:
        pass
    return merged_output

def write_to_txt(spk_sent, file):
    with open(file, 'w') as fp:
        for seg, spk, sentence in spk_sent:
            line = f'{seg.start:.2f} {seg.end:.2f} {spk} {sentence}\n'
            fp.write(line)

def save_transcripts_json(args, output_data, file_name):
    serializable = []
    prev_end = 0.
    for i, item in enumerate(output_data):
        seg, speaker, text = item
        start = float(seg.start)
        end = float(seg.end)
        if start > prev_end:
            serializable[i-1]["end"] = start
        serializable.append({
            "start":   start,
            "end":     end,
            "speaker": speaker,
            "text":    text
        })
        prev_end = end
    # Save speech recognition results in JSON format in two locations (frontend・backup)
    output_dirs = ["src/frontend/public/transcripts", "outputs"]
    for output_dir in output_dirs:
        os.makedirs(output_dir, exist_ok=True)
        output_file_path = os.path.join(output_dir, f"{file_name}.json")
        with open(output_file_path, "w", encoding="utf-8") as json_file:
            json.dump(serializable, json_file, ensure_ascii=False, indent=2)
        if output_dir == "outputs":
            txt_file_path = os.path.join(output_dir, f"{file_name}.txt")
            with open(txt_file_path, "w", encoding="utf-8") as txt_file:
                for item in serializable:
                    txt_file.write(f"speaker{item['speaker']}:{item['text']}\n")
    # Copy audio
    audio_paths = ["src/frontend/public/audios", "outputs"]
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