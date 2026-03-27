from typing import Any, List, Tuple
from pyannote.core import Segment
from models.base import BaseModel
import time
import torch
import soundfile as sf


class AutomaticSpeechRecognition(BaseModel):
    def setup_model(self):
        from transformers import pipeline

        model_id = "kotoba-tech/kotoba-whisper-v2.0"
        torch_dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        model_kwargs = {"attn_implementation": "sdpa"} if torch.cuda.is_available() else {}

        return pipeline(
            "automatic-speech-recognition",
            model=model_id,
            torch_dtype=torch_dtype,
            device=device,
            model_kwargs=model_kwargs
        )

    def inference(self, audio: Any) -> Any:
        print("==============Start ASR==============")
        start_time = time.time()
        result = self.model(
            audio,
            return_timestamps=True,
            generate_kwargs={
                "language": self.args.language,
                "task": "transcribe"
            }
        )
        return {
            "result": result,
            "audio": audio
        }, start_time

    def parse_output(self, raw_outputs: Any, start_time: float) -> List[Tuple[Segment, str]]:
        segments: List[Tuple[Segment, str]] = []

        result = raw_outputs.get("result") if isinstance(raw_outputs, dict) else None
        audio = raw_outputs.get("audio") if isinstance(raw_outputs, dict) else None
        chunks = result.get("chunks") if isinstance(result, dict) else None
        if chunks:
            for chunk in chunks:
                ts = chunk.get("timestamp", (None, None))
                if not isinstance(ts, (list, tuple)) or len(ts) != 2:
                    continue
                start, end = ts
                if start is None or end is None:
                    continue
                text = str(chunk.get("text", "")).strip()
                segments.append((Segment(float(start), float(end)), text))
        elif isinstance(result, dict):
            text = str(result.get("text", "")).strip()
            if text:
                duration = 0.0
                if isinstance(audio, str):
                    try:
                        duration = float(sf.info(audio).duration)
                    except RuntimeError:
                        duration = 0.0
                segments.append((Segment(0.0, duration), text))

        print(segments)
        print(f"==============ASR done in {time.time() - start_time:.2f}s.==============")
        return segments
