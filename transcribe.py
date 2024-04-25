import whisper
from pyannote.audio import Pipeline
from pyannote_whisper.utils import diarize_text

pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1")
model = whisper.load_model("tiny.en")
asr_result = model.transcribe("data/afjiv.wav")
diarization_result = pipeline("data/afjiv.wav")
final_result = diarize_text(asr_result, diarization_result)

for seg, spk, sent in final_result:
    line = f'{seg.start:.2f} {seg.end:.2f} {spk} {sent}'
    print(line)
