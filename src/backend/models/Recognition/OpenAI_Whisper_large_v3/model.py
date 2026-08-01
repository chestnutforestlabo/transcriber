import os
import time
from typing import Any, List, Tuple

import numpy as np
import whisper
from models.base import BaseModel
from pyannote.core import Segment


class AutomaticSpeechRecognition(BaseModel):
    def setup_model(self):
        # specify where to save the model
        return whisper.load_model(
            "large-v3", download_root=os.environ.get("HF_HOME", "./models")
        )

    def inference(self, audio: Any) -> Any:
        print("==============Start ASR==============")
        start_time = time.time()

        if isinstance(audio, np.ndarray):
            audio = audio.astype(np.float32, copy=False)

        result = self.model.transcribe(
            audio,
            language=self.args.openai_language,
            verbose=False,
            word_timestamps=True,
            beam_size=getattr(self.args, "asr_beam_size", 5),
            initial_prompt=getattr(self.args, "asr_initial_prompt", None),
        )
        return result, start_time

    def parse_output(self, raw_outputs: Any, start_time: float) -> List[Tuple]:
        segments: List[Tuple] = []
        for seg in raw_outputs.get("segments", []):
            start = seg["start"]
            end = seg["end"]
            text = seg["text"].strip()
            words = []
            for word in seg.get("words", []):
                word_start = word.get("start")
                word_end = word.get("end")
                if word_start is None or word_end is None:
                    continue
                words.append(
                    (
                        Segment(float(word_start), float(word_end)),
                        str(word.get("word", "")),
                    )
                )
            segments.append((Segment(start, end), text, words))
        print(segments)
        print(
            f"==============ASR done in {time.time() - start_time:.2f}s.=============="
        )
        return segments
