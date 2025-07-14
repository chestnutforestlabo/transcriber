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

    # ASR and Diarization models
    asr_model = get_asr_model(args)
    sd_model  = get_sd_model(args)
    sd_model.setup_model_if_needed()

    # Move diarization model to GPU if available
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    sd_model.model.to(device)

    processed_files = []
    # Process and save each file sequentially
    for item in tqdm(dataset, desc="Processing audio files"):
        basename = item["basename"]
        audio_path = os.path.join(args.audio_dir, basename)

        # Run ASR
        asr_output = asr_model.run(audio_path)
        # Run Diarization
        diar_output = sd_model.run(audio_path)

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
    parser.add_argument("--language", type=str, default="en", help="Language of audio files (e.g. 'en', 'ja')")
    parser.add_argument("--diarization_time", action="store_true", help="Use pyannote/embedding for diarization if set")
    parser.add_argument("--asr_model_name", type=str, default="whisper-large-v3", help="HuggingFace ASR model name")
    args = parser.parse_args()
    main(args)