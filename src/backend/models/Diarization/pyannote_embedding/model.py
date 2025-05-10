from pyannote.audio import Pipeline
import time
from models.base import BaseModel
import os

class SpeechDiarization(BaseModel):
    def setup_model(self):
        pipeline = Pipeline.from_pretrained("pyannote/embedding",use_auth_token=os.environ["HF_TOKEN"])
        return pipeline
    
    def inference(self):
        pass
    
    def parse_output(self, diarization_result):
        return diarization_result