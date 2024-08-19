import os
import whisper
from pyannote.audio import Pipeline
from pyannote_whisper.utils import diarize_text

def transcribe_file(file_path, num_speakers):
    # Load the models
    pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1")
    model = whisper.load_model("large")

    # Perform ASR and diarization
    asr_result = model.transcribe(file_path)
    diarization_result = pipeline(file_path, num_speakers=num_speakers)
    final_result = diarize_text(asr_result, diarization_result)

    # Create the transcribed directory if it doesn't exist
    os.makedirs("transcribed", exist_ok=True)

    # Extract filename without extension
    file_name = os.path.splitext(os.path.basename(file_path))[0]

    # Define the output file path
    output_file_path = os.path.join("transcribed", f"{file_name}.txt")

    # Write the results to the output file
    with open(output_file_path, "w") as output_file:
        for seg, spk, sent in final_result:
            line = f'{seg.start:.2f} {seg.end:.2f} {spk} {sent}\n'
            output_file.write(line)

    print(f"Transcription saved to {output_file_path}")

def main(args):
    data_dir = args.data_path
    num_speakers = args.num_speakers

    # Iterate over all .wav files in the data directory
    for file_name in os.listdir(data_dir):
        if file_name.endswith(".wav"):
            file_path = os.path.join(data_dir, file_name)
            # Extract filename without extension
            base_name = os.path.splitext(file_name)[0]
            output_file_path = os.path.join("transcribed", f"{base_name}.txt")

            # Check if the file has already been transcribed
            if not os.path.exists(output_file_path):
                transcribe_file(file_path, num_speakers)
            else:
                print(f"Skipping {file_name}, already transcribed.")

if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("--data_path", type=str, default="data", help="path to the directory containing audio files")
    parser.add_argument("--num_speakers", type=int, default=2, help="number of speakers")

    args = parser.parse_args()
    main(args)
