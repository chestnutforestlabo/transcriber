from models import get_sd_model, get_asr_model
from utils import diarize_text, save_transcripts_json, save_index_json
from data import AudioInput

import os
import argparse
from tqdm import tqdm
import torch


def transcribe(args):
    dataset = AudioInput(args.audio_dir)
    args.num_speakers = dataset.num_speakers

    asr_model = get_asr_model(args)
    sd_model  = get_sd_model(args)
    
    sd_model.setup_model_if_needed()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    sd_model.model.to(device)

    all_results = []
    for item in tqdm(dataset, desc="Processing audio"):
        basename = item["basename"]
        waveform = item["waveform"]
        
        # Construct full path for file-based diarization
        audio_path = os.path.join(args.audio_dir, basename)

        # ASR: pass raw waveform array
        # asr_output  = asr_model.run(waveform)
        asr_output = asr_model.run(audio_path)
        print(asr_output)
        
        # Diarization: pass file path string
        diar_output = sd_model.run(audio_path)
        print(diar_output)

        merged = diarize_text(args, asr_output, diar_output)
        all_results.append((basename, merged))

    return all_results


def main(args):
    results = transcribe(args)
    processed_files = []

    for name, segments in results:
        basename_no_ext = os.path.splitext(name)[0]
        save_transcripts_json(args, segments, basename_no_ext)
        processed_files.append(name)

    save_index_json(processed_files)
    print(f"Finished processing {len(processed_files)} files.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio_dir",      type=str, required=True, help="path to the directory containing audio files per num_speakers")
    parser.add_argument("--language", type=str, default="en", help="language of the audio files")
    parser.add_argument("--diarization_time", action="store_true", help="use pyannote/embedding for diarization")
    parser.add_argument("--asr_model_name", type=str, default="whisper-large-v3", help="ASR model ID for HuggingFace pipeline")
    args = parser.parse_args()
    main(args)