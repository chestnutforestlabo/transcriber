from pyannote.audio import Pipeline
from pyannote.core import Annotation, Segment
from models.base import BaseModel
import time
from typing import List, Tuple, Union
import os

class SpeechDiarization(BaseModel):
    def setup_model(self) -> Pipeline:
        """
        Load the Pyannote speaker-diarization pipeline.
        """
        # return Pipeline.from_pretrained(
        #     "pyannote/speaker-diarization-3.1",
        #     use_auth_token=self.config.get("huggingface_token")
        # )
        # also specify where to save the model
        return Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=os.environ["HF_TOKEN"],
            cache_dir=os.environ.get("HF_HOME", "./models")
        )

    def inference(self, audio_source: str) -> Annotation:
        """
        Run diarization on a single audio file path and return an Annotation.

        audio_source: Path to the audio file.
        """
        print("Start Diarization")
        start_time = time.time()
        ann: Annotation = self.model(
            {"uri": audio_source, "audio": audio_source},
            num_speakers=self.args.num_speakers
        )
        print(f"Diarization done in {time.time() - start_time:.2f} seconds.")
        return ann
    
    def parse_output(self, ann: Annotation):
        return ann