import argparse
import os
import tempfile

import numpy as np
import soundfile as sf
import torch
from data import AudioInput
from pyannote.core import Segment
from stereo import (
    DEFAULT_CROSSTALK_THRESHOLD_DB,
    MIN_ASR_ACTIVE_DURATION_SEC,
    VoiceActivityDetector,
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


def transcribe(args):
    channel_mode = bool(getattr(args, "channel_mode", False))
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
    args.num_speakers = 2 if channel_mode else dataset.num_speakers

    if args.audio_files is None and dataset.skipped_files:
        print(
            f"Skipping {len(dataset.skipped_files)} already processed file(s): "
            + ", ".join(dataset.skipped_files)
        )
    if len(dataset) == 0:
        print("No audio files to process.")
        return []

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
        if use_online_llm
        else dataset
    )
    # Process and save each file sequentially
    for item in tqdm(data_iter, total=len(dataset), desc="Processing audio files"):
        basename = item["basename"]
        audio_path = os.path.join(args.audio_dir, basename)
        if use_online_llm:
            # OnlineLLM output already includes timestamp + speaker attribution.
            merged = online_llm_model.run(audio_path)
        elif channel_mode:
            merged = transcribe_stereo_segments(
                asr_model=asr_model,
                args=args,
                segments=item["waveform"],
                sampling_rate=dataset.sampling_rate,
            )
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

        # Save JSON and TXT for this file
        basename_no_ext = os.path.splitext(basename)[0]
        save_transcripts_json(args, merged, basename_no_ext)
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
            "Remove channel speech whose RMS is this many dB or more below "
            "the other channel (default: %(default)s dB)"
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
