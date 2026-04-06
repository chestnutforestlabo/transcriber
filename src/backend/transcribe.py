from models import get_sd_model, get_asr_model, get_online_llm_model
from utils import diarize_text, save_transcripts_json, save_index_json
from data import AudioInput

import os
import argparse
from tqdm import tqdm
import torch
import numpy as np
import tempfile
import soundfile as sf
from pyannote.core import Segment


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


def _run_asr_on_segments(asr_model, args, segments: list[np.ndarray], sampling_rate: int):
    merged = []
    offset = 0.0
    for segment in segments:
        chunk_output = _run_asr_on_segment(asr_model, args, segment, sampling_rate)
        for seg, text in chunk_output:
            shifted = Segment(seg.start + offset, seg.end + offset)
            merged.append((shifted, text))
        offset += len(segment) / float(sampling_rate)
    merged.sort(key=lambda x: (x[0].start, x[0].end))
    return merged


def transcribe(args):
    dataset = AudioInput(args.audio_dir, target_files=args.audio_files)
    args.num_speakers = dataset.num_speakers

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
        else:
            waveform_segments = item["waveform"]
            concatenated_waveform = np.concatenate(waveform_segments, axis=0)

            # Run ASR on split waveforms and merge timestamps by offset
            asr_output = _run_asr_on_segments(
                asr_model=asr_model,
                args=args,
                segments=waveform_segments,
                sampling_rate=dataset.sampling_rate
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


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio_dir", type=str, required=True, help="Directory containing audio files")
    parser.add_argument("--audio_files", type=str, nargs="+", default=None, help="Optional file name(s) to process from --audio_dir (e.g. sample1.wav sample2.wav)")
    parser.add_argument("--online_llm", action="store_true", help="Whether to use an online LLM for ASR + diarization instead of separate models")
    parser.add_argument("--online_llm_model", type=str, choices=["gemini"], default="gemini", help="Online LLM model to use for ASR & diarization")
    parser.add_argument("--openai_language", type=str, default="ja", help="Language of audio files for OpenAI Whisper (e.g. 'en'(English), 'ja'(Janpanese))")
    parser.add_argument("--qwen_language", type=str, choices=['Chinese', 'English', 'Cantonese', 'Arabic', 'German', 'French', 'Spanish', 
                                                            'Portuguese', 'Indonesian', 'Italian', 'Korean', 'Russian', 'Thai', 'Vietnamese', 
                                                            'Japanese', 'Turkish', 'Hindi', 'Malay', 'Dutch', 'Swedish', 'Danish', 'Finnish', 
                                                            'Polish', 'Czech', 'Filipino', 'Persian', 'Greek', 'Romanian', 'Hungarian', 'Macedonian'], 
                        default="Japanese", help="Language of audio files for Qwen ASR")
    parser.add_argument("--diarization_model_name", type=str, choices=["community", "precision"], default="community", help="Diarization model to use")
    parser.add_argument("--asr_model_name", type=str, choices=["kotoba", "openai", "qwen"], default="openai", help="ASR model to use")
    args = parser.parse_args()
    main(args)
