from typing import Any, List, Tuple
from transformers import pipeline
from pyannote.core import Segment
from models.base import BaseModel
import time
import whisper
import os
class AutomaticSpeechRecognition(BaseModel):
    def setup_model(self):
        # specify where to save the model
        return whisper.load_model("large-v3", download_root=os.environ.get("HF_HOME", "./models"))
    
    def inference(self, audio: Any) -> Any:
        print("==============Start ASR==============")
        start_time = time.time()
        result = self.model.transcribe(
            audio,
            language=self.args.language,
            verbose=False
        )
        return result, start_time

    def parse_output(self, raw_outputs: Any, start_time: float) -> List[Tuple[Segment, str]]:
        segments: List[Tuple[Segment, str]] = []
        for seg in raw_outputs.get("segments", []):
            start = seg["start"]
            end   = seg["end"]
            text  = seg["text"].strip()
            segments.append((Segment(start, end), text))
        print(segments)
        print(f"==============ASR done in {time.time() - start_time:.2f}s.==============")
        return segments