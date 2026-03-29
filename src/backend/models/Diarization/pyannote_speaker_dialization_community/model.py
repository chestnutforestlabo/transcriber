from pyannote.audio import Pipeline
from pyannote.audio.core.task import Specifications
from pyannote.core import Annotation, Segment
import torch
import soundfile as sf
from models.base import BaseModel
import time
from typing import List, Tuple
import os


class SpeechDiarization(BaseModel):
    def setup_model(self) -> Pipeline:
        """
        Load the pyannote community speaker-diarization pipeline.
        """
        os.environ.setdefault("TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD", "1")

        # PyTorch 2.6+ defaults to weights_only=True in torch.load, so allowlist
        # pyannote's Specifications class used by legacy checkpoints.
        torch.serialization.add_safe_globals([Specifications])

        token = os.environ.get("HF_TOKEN")
        if token is not None:
            return Pipeline.from_pretrained(
                "pyannote/speaker-diarization-community-1",
                token=token,
                cache_dir=os.environ.get("HF_HOME", "./models")
            )

        return Pipeline.from_pretrained(
            "pyannote/speaker-diarization-community-1",
            cache_dir=os.environ.get("HF_HOME", "./models")
        )

    def inference(self, audio_source: str) -> Annotation:
        """
        Run diarization on a single audio file path and return an Annotation.

        audio_source: Path to the audio file.
        """
        print("==============Start Diarization==============")
        start_time = time.time()

        waveform, sample_rate = sf.read(audio_source, always_2d=True, dtype="float32")
        # pyannote expects (channels, time)
        waveform = torch.from_numpy(waveform.T)

        ann: Annotation = self.model(
            {"uri": audio_source, "waveform": waveform, "sample_rate": sample_rate},
            num_speakers=self.args.num_speakers
        )
        return ann, start_time

    def parse_output(self, ann: Annotation, start_time: float) -> List[Tuple[Segment, str]]:
        print(ann)
        print(f"==============Diarization done in {time.time() - start_time:.2f} seconds.==============")

        if hasattr(ann, "speaker_diarization"):
            return ann.speaker_diarization

        return ann
