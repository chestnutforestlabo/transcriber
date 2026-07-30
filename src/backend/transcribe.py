import argparse
import os
import tempfile

import numpy as np
import soundfile as sf
import torch
from alignment import (
    DEFAULT_ALIGNMENT_WINDOW_SEC,
    AlignedChannels,
    align_audio_files,
)
from data import AudioInput
from pyannote.core import Segment
from stereo import (
    DEFAULT_CROSSTALK_THRESHOLD_DB,
    MIN_ASR_ACTIVE_DURATION_SEC,
    VoiceActivityDetector,
    gate_multichannel_waveform,
    gate_stereo_waveform,
)
from tqdm import tqdm
from utils import diarize_text, save_index_json, save_transcripts_json

from models import get_asr_model, get_online_llm_model, get_sd_model


def _to_mono(segment: np.ndarray) -> np.ndarray:
    if segment.ndim == 1:
        return segment.astype(np.float32, copy=False)
    return np.mean(segment, axis=1, dtype=np.float32)


def _run_asr_on_segment(asr_model, args, segment: np.ndarray, sampling_rate: int):
    if args.asr_model_name == "openai":
        return asr_model.run(_to_mono(segment))
    if args.asr_model_name == "kotoba":
        return asr_model.run(_to_mono(segment))
    if args.asr_model_name == "qwen":
        return asr_model.run((_to_mono(segment), sampling_rate))
    return asr_model.run(_to_mono(segment))


def _shift_words(words, offset: float):
    shifted_words = []
    for word in words or []:
        if isinstance(word, dict):
            shifted = dict(word)
            if shifted.get("start") is not None:
                shifted["start"] = float(shifted["start"]) + offset
            if shifted.get("end") is not None:
                shifted["end"] = float(shifted["end"]) + offset
            shifted_words.append(shifted)
            continue

        if isinstance(word, (tuple, list)) and len(word) >= 2:
            word_segment = word[0]
            if isinstance(word_segment, Segment):
                shifted_segment = Segment(
                    word_segment.start + offset,
                    word_segment.end + offset,
                )
                shifted_words.append((shifted_segment, *word[1:]))
                continue

        shifted_words.append(word)
    return shifted_words


def _run_asr_on_segments(
    asr_model,
    args,
    segments: list[np.ndarray],
    sampling_rate: int,
    process_segments: list[bool] | None = None,
):
    if process_segments is not None and len(process_segments) != len(segments):
        raise ValueError("process_segments must match the number of audio segments.")

    merged = []
    offset = 0.0
    for index, segment in enumerate(segments):
        if process_segments is not None and not process_segments[index]:
            offset += len(segment) / float(sampling_rate)
            continue

        chunk_output = _run_asr_on_segment(asr_model, args, segment, sampling_rate)
        for item in chunk_output:
            seg, text = item[:2]
            shifted = Segment(seg.start + offset, seg.end + offset)
            if len(item) >= 3:
                merged.append((shifted, text, _shift_words(item[2], offset)))
            else:
                merged.append((shifted, text))
        offset += len(segment) / float(sampling_rate)
    merged.sort(key=lambda x: (x[0].start, x[0].end))
    return merged


def transcribe_stereo_segments(
    asr_model,
    args,
    segments: list[np.ndarray],
    sampling_rate: int,
    vad_detector: VoiceActivityDetector | None = None,
):
    """Gate and transcribe synchronized L/R segments on one shared timeline."""
    if not segments:
        return []
    if any(segment.ndim != 2 or segment.shape[1] != 2 for segment in segments):
        raise ValueError("Channel mode received a non-stereo preprocessed segment.")

    segment_lengths = [len(segment) for segment in segments]
    concatenated = np.concatenate(segments, axis=0)
    gating = gate_stereo_waveform(
        concatenated,
        sampling_rate,
        crosstalk_threshold_db=getattr(
            args,
            "channel_crosstalk_threshold_db",
            DEFAULT_CROSSTALK_THRESHOLD_DB,
        ),
        vad_detector=vad_detector,
    )

    boundaries = np.cumsum([0, *segment_lengths])
    minimum_active_samples = max(
        1,
        int(np.ceil(MIN_ASR_ACTIVE_DURATION_SEC * sampling_rate)),
    )
    merged = []
    for channel, speaker in enumerate(("SPEAKER_00", "SPEAKER_01")):
        channel_segments = [
            gating.waveform[start:end, channel]
            for start, end in zip(
                boundaries[:-1],
                boundaries[1:],
                strict=True,
            )
        ]
        active_segments = [
            int(np.count_nonzero(gating.keep_mask[start:end, channel]))
            >= minimum_active_samples
            for start, end in zip(
                boundaries[:-1],
                boundaries[1:],
                strict=True,
            )
        ]
        asr_output = _run_asr_on_segments(
            asr_model=asr_model,
            args=args,
            segments=channel_segments,
            sampling_rate=sampling_rate,
            process_segments=active_segments,
        )
        merged.extend((segment, speaker, text) for segment, text, *_ in asr_output)

    merged.sort(key=lambda item: (item[0].start, item[0].end, item[1]))
    return merged


def transcribe_multichannel_segments(
    asr_model,
    args,
    segments: list[np.ndarray],
    sampling_rate: int,
    timeline_offset_sec: float = 0.0,
    vad_detector: VoiceActivityDetector | None = None,
):
    """Gate and transcribe synchronized N-channel segments."""
    if not segments:
        return []
    channel_count = segments[0].shape[1] if segments[0].ndim == 2 else 0
    if channel_count < 2 or any(
        segment.ndim != 2 or segment.shape[1] != channel_count
        for segment in segments
    ):
        raise ValueError(
            "Pseudo-multichannel mode received inconsistent channel segments."
        )

    segment_lengths = [len(segment) for segment in segments]
    concatenated = np.concatenate(segments, axis=0)
    gating = gate_multichannel_waveform(
        concatenated,
        sampling_rate,
        crosstalk_threshold_db=getattr(
            args,
            "channel_crosstalk_threshold_db",
            DEFAULT_CROSSTALK_THRESHOLD_DB,
        ),
        vad_detector=vad_detector,
    )

    boundaries = np.cumsum([0, *segment_lengths])
    minimum_active_samples = max(
        1,
        int(np.ceil(MIN_ASR_ACTIVE_DURATION_SEC * sampling_rate)),
    )
    merged = []
    for channel in range(channel_count):
        channel_segments = [
            gating.waveform[start:end, channel]
            for start, end in zip(
                boundaries[:-1],
                boundaries[1:],
                strict=True,
            )
        ]
        active_segments = [
            int(np.count_nonzero(gating.keep_mask[start:end, channel]))
            >= minimum_active_samples
            for start, end in zip(
                boundaries[:-1],
                boundaries[1:],
                strict=True,
            )
        ]
        asr_output = _run_asr_on_segments(
            asr_model=asr_model,
            args=args,
            segments=channel_segments,
            sampling_rate=sampling_rate,
            process_segments=active_segments,
        )
        speaker = f"SPEAKER_{channel:02d}"
        for segment, text, *_ in asr_output:
            shifted = Segment(
                segment.start + timeline_offset_sec,
                segment.end + timeline_offset_sec,
            )
            merged.append((shifted, speaker, text))

    merged.sort(key=lambda item: (item[0].start, item[0].end, item[1]))
    return merged


def _print_alignment_summary(aligned: AlignedChannels) -> None:
    for channel, (path, alignment) in enumerate(
        zip(aligned.aux_paths, aligned.alignments, strict=True),
        start=2,
    ):
        start_confidence = (
            f"{alignment.start_anchor.confidence:.3f}"
            if alignment.start_anchor is not None
            else "manual"
        )
        end_confidence = (
            f"{alignment.end_anchor.confidence:.3f}"
            if alignment.end_anchor is not None
            else "n/a"
        )
        start_peak_ratio = (
            f"{alignment.start_anchor.peak_ratio:.2f}"
            if alignment.start_anchor is not None
            else "n/a"
        )
        end_peak_ratio = (
            f"{alignment.end_anchor.peak_ratio:.2f}"
            if alignment.end_anchor is not None
            else "n/a"
        )
        print(
            f"Aux ch{channel} ({path}): offset={alignment.offset_sec:+.6f}s, "
            f"drift={alignment.drift_ppm:+.2f}ppm, "
            f"start_confidence={start_confidence} (peak_ratio={start_peak_ratio}), "
            f"end_confidence={end_confidence} (peak_ratio={end_peak_ratio}), "
            f"method={alignment.method}"
        )
        for message in alignment.warnings:
            print(f"WARNING: Aux ch{channel}: {message}")
    print(
        "Aligned overlap on main timeline: "
        f"{aligned.overlap_start_sec:.3f}s–{aligned.overlap_end_sec:.3f}s"
    )


def transcribe(args):
    channel_mode = bool(getattr(args, "channel_mode", False))
    aux_paths = list(getattr(args, "aux_audio", None) or [])
    manual_offsets = getattr(args, "aux_offset", None)
    if aux_paths and not channel_mode:
        raise ValueError("--aux_audio is only valid together with --channel_mode.")
    if manual_offsets and not aux_paths:
        raise ValueError("--aux_offset requires --aux_audio.")
    if manual_offsets is not None and len(manual_offsets) != len(aux_paths):
        raise ValueError("--aux_offset requires exactly one value per --aux_audio.")
    if channel_mode and args.online_llm:
        raise ValueError(
            "--channel_mode uses the selected local ASR model and cannot be "
            "combined with --online_llm."
        )

    dataset = AudioInput(
        args.audio_dir,
        target_files=args.audio_files,
        channel_mode=channel_mode,
    )
    args.num_speakers = (
        2 + len(aux_paths) if channel_mode else dataset.num_speakers
    )

    if args.audio_files is None and dataset.skipped_files:
        print(
            f"Skipping {len(dataset.skipped_files)} already processed file(s): "
            + ", ".join(dataset.skipped_files)
        )
    if len(dataset) == 0:
        print("No audio files to process.")
        return []
    if aux_paths and len(dataset) != 1:
        raise ValueError(
            "--aux_audio describes channels for one main WAV; select exactly "
            "one file with --audio_files when --audio_dir contains multiple WAVs."
        )

    use_online_llm = bool(args.online_llm)

    if use_online_llm:
        online_llm_model = get_online_llm_model(args)
    elif channel_mode:
        asr_model = get_asr_model(args)
    else:
        # ASR and Diarization models
        asr_model = get_asr_model(args)
        sd_model = get_sd_model(args)
        sd_model.setup_model_if_needed()

        # Move diarization model to GPU if available
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        sd_model.model.to(device)

    processed_files = []
    data_iter = (
        ({"basename": basename} for basename in dataset.audio_list)
        if use_online_llm or aux_paths
        else dataset
    )
    # Process and save each file sequentially
    for item in tqdm(data_iter, total=len(dataset), desc="Processing audio files"):
        basename = item["basename"]
        audio_path = os.path.join(args.audio_dir, basename)
        if use_online_llm:
            # OnlineLLM output already includes timestamp + speaker attribution.
            merged = online_llm_model.run(audio_path)
            transcript_meta = None
        elif aux_paths:
            aligned = align_audio_files(
                main_path=audio_path,
                aux_paths=aux_paths,
                target_sampling_rate=dataset.sampling_rate,
                manual_offsets_sec=manual_offsets,
                window_sec=getattr(
                    args,
                    "aux_alignment_window_sec",
                    DEFAULT_ALIGNMENT_WINDOW_SEC,
                ),
            )
            _print_alignment_summary(aligned)
            aligned_segments = dataset.split_preserving_timeline(
                aligned.waveform,
                aligned.sampling_rate,
            )
            merged = transcribe_multichannel_segments(
                asr_model=asr_model,
                args=args,
                segments=aligned_segments,
                sampling_rate=aligned.sampling_rate,
                timeline_offset_sec=aligned.overlap_start_sec,
            )
            transcript_meta = {
                "channel_alignment": aligned.to_meta(main_path=audio_path),
            }
        elif channel_mode:
            merged = transcribe_stereo_segments(
                asr_model=asr_model,
                args=args,
                segments=item["waveform"],
                sampling_rate=dataset.sampling_rate,
            )
            transcript_meta = None
        else:
            waveform_segments = item["waveform"]
            concatenated_waveform = np.concatenate(waveform_segments, axis=0)

            # Run ASR on split waveforms and merge timestamps by offset
            asr_output = _run_asr_on_segments(
                asr_model=asr_model,
                args=args,
                segments=waveform_segments,
                sampling_rate=dataset.sampling_rate,
            )

            # Run diarization on the same preprocessed (concatenated) audio timeline
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_audio:
                tmp_audio_path = tmp_audio.name
            try:
                sf.write(tmp_audio_path, concatenated_waveform, dataset.sampling_rate)
                diar_output = sd_model.run(tmp_audio_path)
            finally:
                if os.path.exists(tmp_audio_path):
                    os.remove(tmp_audio_path)

            # Merge ASR + speaker info
            merged = diarize_text(args, asr_output, diar_output)
            transcript_meta = None

        # Save JSON and TXT for this file
        basename_no_ext = os.path.splitext(basename)[0]
        save_transcripts_json(
            args,
            merged,
            basename_no_ext,
            metadata=transcript_meta,
        )
        # Update index.json immediately
        save_index_json(basename)

        processed_files.append(basename)
        print(f"==============Saved transcripts for {basename}==============")

    return processed_files


def main(args):
    processed = transcribe(args)
    print(f"Finished processing {len(processed)} files.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--audio_dir", type=str, required=True, help="Directory containing audio files"
    )
    parser.add_argument(
        "--audio_files",
        type=str,
        nargs="+",
        default=None,
        help=(
            "Optional file name(s) to process from --audio_dir "
            "(e.g. sample1.wav sample2.wav)"
        ),
    )
    parser.add_argument(
        "--online_llm",
        action="store_true",
        help=(
            "Whether to use an online LLM for ASR + diarization "
            "instead of separate models"
        ),
    )
    parser.add_argument(
        "--online_llm_model",
        type=str,
        choices=["gemini"],
        default="gemini",
        help="Online LLM model to use for ASR & diarization",
    )
    parser.add_argument(
        "--openai_language",
        type=str,
        default="ja",
        help=(
            "Language of audio files for OpenAI Whisper "
            "(e.g. 'en'(English), 'ja'(Janpanese))"
        ),
    )
    parser.add_argument(
        "--qwen_language",
        type=str,
        choices=[
            "Chinese",
            "English",
            "Cantonese",
            "Arabic",
            "German",
            "French",
            "Spanish",
            "Portuguese",
            "Indonesian",
            "Italian",
            "Korean",
            "Russian",
            "Thai",
            "Vietnamese",
            "Japanese",
            "Turkish",
            "Hindi",
            "Malay",
            "Dutch",
            "Swedish",
            "Danish",
            "Finnish",
            "Polish",
            "Czech",
            "Filipino",
            "Persian",
            "Greek",
            "Romanian",
            "Hungarian",
            "Macedonian",
        ],
        default="Japanese",
        help="Language of audio files for Qwen ASR",
    )
    parser.add_argument(
        "--diarization_model_name",
        type=str,
        choices=["community", "precision", "pyannote_ja", "diarizen"],
        default="community",
        help="Diarization model to use",
    )
    parser.add_argument(
        "--use_exclusive_diarization",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Use exclusive speaker diarization when the selected backend provides it "
            "(enabled by default)"
        ),
    )
    parser.add_argument(
        "--channel_mode",
        action="store_true",
        help=(
            "Treat a 2-channel WAV as fixed speakers "
            "(L=SPEAKER_00, R=SPEAKER_01) without diarization"
        ),
    )
    parser.add_argument(
        "--channel_crosstalk_threshold_db",
        type=float,
        default=DEFAULT_CROSSTALK_THRESHOLD_DB,
        help=(
            "Remove channel speech whose normalized RMS is this many dB or "
            "more below the loudest channel (default: %(default)s dB)"
        ),
    )
    parser.add_argument(
        "--aux_audio",
        type=str,
        nargs="+",
        default=None,
        help=(
            "Auxiliary recording(s) to align as SPEAKER_02 onward; valid only "
            "with --channel_mode"
        ),
    )
    parser.add_argument(
        "--aux_offset",
        type=float,
        nargs="+",
        default=None,
        help=(
            "Manual main-timeline start offset in seconds for each --aux_audio; "
            "disables automatic drift correction for that auxiliary channel"
        ),
    )
    parser.add_argument(
        "--aux_alignment_window_sec",
        type=float,
        default=DEFAULT_ALIGNMENT_WINDOW_SEC,
        help=(
            "Duration of the start/end windows used for clap alignment "
            "(default: %(default)s seconds)"
        ),
    )
    parser.add_argument(
        "--asr_model_name",
        type=str,
        choices=["kotoba", "openai", "qwen"],
        default="openai",
        help="ASR model to use",
    )
    args = parser.parse_args()
    main(args)
