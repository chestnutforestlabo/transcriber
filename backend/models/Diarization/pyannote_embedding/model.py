from pyannote.audio import Pipeline
import time
from backend.models.base import BaseModel

class SpeechDiarization(BaseModel):
    def setup_model(self):
        pipeline = Pipeline.from_pretrained("pyannote/embedding")
        return pipeline
    
    def inference(self):
        pass
    
    def parse_output(self, diarization_result):
        return diarization_result