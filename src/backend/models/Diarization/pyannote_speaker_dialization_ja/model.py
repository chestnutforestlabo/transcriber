import os
import time
from typing import Any

import soundfile as sf
import torch
from models.base import BaseModel
from pyannote.audio import Pipeline
from pyannote.audio.core.task import Specifications
from pyannote.core import Annotation

PIPELINE_ID = "pyannote/speaker-diarization-3.1"
SEGMENTATION_MODEL_ID = (
    "diarizers-community/speaker-segmentation-fine-tuned-callhome-jpn"
)


class SpeechDiarization(BaseModel):
    """Pyannote 3.1 pipeline with CALLHOME Japanese segmentation."""

    def setup_model(self) -> Pipeline:
        os.environ.setdefault("TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD", "1")
        torch.serialization.add_safe_globals([Specifications])

        token = os.environ.get("HF_TOKEN")
        cache_dir = os.environ.get("HF_HOME", "./models")
        pipeline = Pipeline.from_pretrained(
            PIPELINE_ID,
            token=token,
            cache_dir=cache_dir,
        )
        if pipeline is None:
            raise RuntimeError(
                f"Could not load {PIPELINE_ID}. Check HF_TOKEN and accept the "
                "model terms on Hugging Face."
            )

        try:
            from diarizers import SegmentationModel
        except ImportError as exc:
            raise ImportError(
                "The pyannote_ja backend requires the `diarizers` package."
            ) from exc

        segmentation_model = SegmentationModel().from_pretrained(
            SEGMENTATION_MODEL_ID,
            cache_dir=cache_dir,
            token=token,
        )
        pipeline._segmentation.model = segmentation_model.to_pyannote_model()
        return pipeline

    def inference(self, audio_source: str) -> tuple[Any, float]:
        print("==============Start Diarization (pyannote_ja)==============")
        start_time = time.time()

        waveform, sample_rate = sf.read(
            audio_source,
            always_2d=True,
            dtype="float32",
        )
        waveform = torch.from_numpy(waveform.T)
        output = self.model(
            {
                "uri": audio_source,
                "waveform": waveform,
                "sample_rate": sample_rate,
            },
            num_speakers=self.args.num_speakers,
        )
        return output, start_time

    def parse_output(self, output: Any, start_time: float) -> Annotation:
        print(output)
        print(
            "==============Diarization done in "
            f"{time.time() - start_time:.2f} seconds.=============="
        )

        if getattr(self.args, "use_exclusive_diarization", True):
            exclusive = getattr(output, "exclusive_speaker_diarization", None)
            if exclusive is not None:
                return exclusive

        diarization = getattr(output, "speaker_diarization", None)
        if diarization is not None:
            return diarization
        return output
