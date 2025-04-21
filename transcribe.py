import os
import whisper
from pyannote.audio import Pipeline
from pyannote_whisper.utils import diarize_text
import time
import logging
import json
import shutil

# def transcribe_file(file_path, num_speakers, logger):
#     # Load the models
#     pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1")
#     model = whisper.load_model("large")

#     # Perform ASR and diarization with Japanese language specified
#     logger.info("start asr")
#     start_asr = time.time()
#     asr_result = model.transcribe(file_path, language="ja")
#     logger.info(f"ASR done in {time.time() - start_asr:.2f} seconds.")
#     logger.info("start diarization")
#     start_diarization = time.time()
#     diarization_result = pipeline(file_path, num_speakers=num_speakers)
#     final_result = diarize_text(asr_result, diarization_result)
#     logger.info(f"Diarization done in {time.time() - start_diarization:.2f} seconds.")
#     # Create the transcribed directory if it doesn't exist
#     os.makedirs("transcribed", exist_ok=True)

#     # Extract filename without extension
#     file_name = os.path.splitext(os.path.basename(file_path))[0]

#     # Define the output file path
#     output_file_path = os.path.join("transcribed", f"{file_name}.txt")

#     # Write the results to the output file
#     with open(output_file_path, "w") as output_file:
#         for seg, spk, sent in final_result:
#             line = f'{seg.start:.2f} {seg.end:.2f} **{spk}** {sent}\n\n'
#             output_file.write(line)

#     logger.info(f"Transcription saved to {output_file_path}")

def transcribe_file(file_path, output_file_path, num_speakers, logger):
    # Load the models
    pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1")
    model = whisper.load_model("large")

    # Perform ASR and diarization with Japanese language specified
    logger.info("start asr")
    start_asr = time.time()
    asr_result = model.transcribe(file_path, language="ja")
    logger.info(f"ASR done in {time.time() - start_asr:.2f} seconds.")
    logger.info("start diarization")
    start_diarization = time.time()
    diarization_result = pipeline(file_path, num_speakers=num_speakers)
    final_result = diarize_text(asr_result, diarization_result)
    logger.info(f"Diarization done in {time.time() - start_diarization:.2f} seconds.")

    os.makedirs("transcribed", exist_ok=True)
    file_name = os.path.splitext(os.path.basename(file_path))[0]
    logger.info(f"Transcription saved to {output_file_path}")

    # Convert to JSON format
    output_data = []
    for seg, spk, sent in final_result:
        output_data.append({
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "speaker": spk,
            "text": sent.strip()
        })

    with open(output_file_path, "w", encoding="utf-8") as json_file:
        json.dump(output_data, json_file, ensure_ascii=False, indent=2)

def main(args):
    data_dir = args.data_path
    num_speakers = args.num_speakers
    logger = logging.getLogger()
    logging.basicConfig(filename='transcribe.log', level=logging.INFO)

    # Iterate over all .wav files in the data directory
    for file_name in os.listdir(data_dir):
        if file_name.endswith(".wav"):
            file_path = os.path.join(data_dir, file_name)
            # Extract filename without extension
            base_name = os.path.splitext(file_name)[0]
            output_file_path = os.path.join("frontend/public/transcripts", f"{base_name}.json")

            # Check if the file has already been transcribed
            if not os.path.exists(output_file_path):
                logger.info(f"Transcribing {file_name}...")
                start = time.time()
                transcribe_file(file_path, output_file_path, num_speakers, logger)
                logger.info(f"Transcribed {file_name} in {time.time() - start:.2f} seconds.")
                shutil.copy2(file_path, "frontend/public/audios")
                index_path = os.path.join("frontend/public/audios/index.json")
                with open(index_path, "w", encoding="utf-8") as f:
                    json.dump(file_name, f, ensure_ascii=False, indent=2)
            else:
                logger.info(f"Skipping {file_name}, already transcribed.")

if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("--data_path", type=str, default="data", help="path to the directory containing audio files")
    parser.add_argument("--num_speakers", type=int, default=2, help="number of speakers")

    args = parser.parse_args()
    main(args)