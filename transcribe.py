import whisper
from pyannote.audio import Pipeline
from pyannote_whisper.utils import diarize_text

def main(args):
    pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1")
    model = whisper.load_model("large")
    asr_result = model.transcribe(args.path)
    diarization_result = pipeline(args.path, num_speakers=args.num_speakers)
    final_result = diarize_text(asr_result, diarization_result)

    for seg, spk, sent in final_result:
        line = f'{seg.start:.2f} {seg.end:.2f} {spk} {sent}'
        print(line)

if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("--path", type=str, default="data/test.wav", help="path to audio file")
    parser.add_argument("--num_speakers", type=int, default=2, help="number of speakers")

    args = parser.parse_args()
    main(args)
