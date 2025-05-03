# models/Recognition/whisper_large_v3_turbo/model.py
from typing import Any, List, Tuple
from transformers import pipeline
from pyannote.core import Segment
from models.base import BaseModel
import time
import whisper

class AutomaticSpeechRecognition(BaseModel):
    def setup_model(self):
        return whisper.load_model("large-v3")

    def inference(self, audio: Any) -> Any:
        print("Start ASR")
        start = time.time()
        result = self.model.transcribe(
            audio,
            language=self.args.language,
            verbose=False
        )
        print(f"ASR done in {time.time() - start:.2f}s.")
        return result

    def parse_output(self, raw_outputs: Any) -> List[Tuple[Segment, str]]:
        segments: List[Tuple[Segment, str]] = []
        for seg in raw_outputs.get("segments", []):
            start = seg["start"]
            end   = seg["end"]
            text  = seg["text"].strip()
            segments.append((Segment(start, end), text))
        return segments