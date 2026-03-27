from typing import Any, List, Tuple
from pyannote.core import Segment
from models.base import BaseModel
import time
import torch
import numpy as np


class AutomaticSpeechRecognition(BaseModel):
    def setup_model(self):
        from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor

        model_id = "kotoba-tech/kotoba-whisper-v2.0"
        torch_dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
        self.model_dtype = torch_dtype
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.processor = AutoProcessor.from_pretrained(model_id)

        model = AutoModelForSpeechSeq2Seq.from_pretrained(
            model_id,
            torch_dtype=torch_dtype,
            low_cpu_mem_usage=True,
            use_safetensors=True,
        )
        return model.to(self.device)

    def inference(self, audio: Any) -> Any:
        print("==============Start ASR==============")
        start_time = time.time()
        waveform = audio
        if isinstance(waveform, np.ndarray):
            waveform = waveform.astype(np.float32, copy=False)

        inputs = self.processor(
            waveform,
            sampling_rate=16000,
            return_tensors="pt",
        )

        input_features = inputs["input_features"].to(self.device, dtype=self.model_dtype)
        language = "ja"

        generated_ids = self.model.generate(
            input_features,
            language=language,
            task="transcribe",
        )
        text = self.processor.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()

        duration = len(waveform) / 16000.0 if hasattr(waveform, "__len__") else 0.0
        return {
            "text": text,
            "duration": duration,
        }, start_time

    def parse_output(self, raw_outputs: Any, start_time: float) -> List[Tuple[Segment, str]]:
        segments: List[Tuple[Segment, str]] = []

        if isinstance(raw_outputs, dict):
            text = str(raw_outputs.get("text", "")).strip()
            duration = float(raw_outputs.get("duration", 0.0))
            if text:
                segments.append((Segment(0.0, duration), text))

        print(segments)
        print(f"==============ASR done in {time.time() - start_time:.2f}s.==============")
        return segments
