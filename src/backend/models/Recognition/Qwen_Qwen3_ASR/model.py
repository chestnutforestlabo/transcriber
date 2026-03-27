from typing import Any, List, Tuple
from pyannote.core import Segment
from models.base import BaseModel
import time
import torch
import soundfile as sf


class AutomaticSpeechRecognition(BaseModel):
    def setup_model(self):
        try:
            from qwen_asr import Qwen3ASRModel
        except ImportError as exc:
            raise ImportError(
                "Qwen3-ASR requires `qwen-asr` package. Install with: pip install -U qwen-asr"
            ) from exc

        dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
        device_map = "cuda:0" if torch.cuda.is_available() else "cpu"

        return Qwen3ASRModel.from_pretrained(
            "Qwen/Qwen3-ASR-1.7B",
            dtype=dtype,
            device_map=device_map,
            max_inference_batch_size=8,
            max_new_tokens=512
        )

    def inference(self, audio: Any) -> Any:
        print("==============Start ASR==============")
        start_time = time.time()
        results = self.model.transcribe(
            audio=audio,
            language=None,
            return_time_stamps=True
        )
        return {
            "results": results,
            "audio": audio
        }, start_time

    @staticmethod
    def _parse_qwen_timestamps(ts_list: Any) -> List[Tuple[float, float]]:
        parsed: List[Tuple[float, float]] = []
        if not ts_list:
            return parsed

        for item in ts_list:
            start = None
            end = None

            if isinstance(item, dict):
                start = item.get("start", item.get("start_time"))
                end = item.get("end", item.get("end_time"))
            else:
                start = getattr(item, "start", getattr(item, "start_time", None))
                end = getattr(item, "end", getattr(item, "end_time", None))

            if start is None or end is None:
                continue
            parsed.append((float(start), float(end)))

        return parsed

    def parse_output(self, raw_outputs: Any, start_time: float) -> List[Tuple[Segment, str]]:
        segments: List[Tuple[Segment, str]] = []

        results = raw_outputs.get("results", []) if isinstance(raw_outputs, dict) else []
        audio = raw_outputs.get("audio") if isinstance(raw_outputs, dict) else None

        if isinstance(results, list) and len(results) > 0:
            result = results[0]
            text = str(getattr(result, "text", "")).strip()
            ts_list = getattr(result, "time_stamps", None)
            parsed_ts = self._parse_qwen_timestamps(ts_list)

            if parsed_ts and text:
                first_start = parsed_ts[0][0]
                last_end = parsed_ts[-1][1]
                segments.append((Segment(first_start, last_end), text))
            elif text:
                duration = 0.0
                if isinstance(audio, str):
                    try:
                        info = sf.info(audio)
                        duration = float(info.duration)
                    except RuntimeError:
                        duration = 0.0
                segments.append((Segment(0.0, duration), text))

        print(segments)
        print(f"==============ASR done in {time.time() - start_time:.2f}s.==============")
        return segments
