from abc import ABC, abstractmethod
from typing import Any, Union, Optional
import numpy as np

class BaseModel(ABC):
    def __init__(self, args: Any, config: Optional[dict] = None) -> None:
        self.args = args
        self.config = config or {}
        self.model = None

    @abstractmethod
    def setup_model(self) -> Any:
        """
        Loads and initializes the model and returns a model object.
        return: model object
        """
        pass

    @abstractmethod
    def inference(self, audio: Union[str, np.ndarray]) -> Any:
        """
        Accepts audio file paths or numpy arrays and returns model-specific inference results.
        return: model-specific inference results
        """
        pass

    @abstractmethod
    def parse_output(self, raw_output: Any) -> str:
        """
        The model's raw output is converted and formatted into text and returned.
        return: list of tuples (Segment(start_time, end_time), text) >> Use "from pyannote.core import Segment, Annotation, Timeline"
        """
        pass

    def setup_model_if_needed(self) -> None:
        """
        If the model has not been initialized, call setup_model.
        """
        if self.model is None:
            self.model = self.setup_model()
    
    def run(self, audio: Union[str, np.ndarray]) -> str:
        self.setup_model_if_needed()
        raw = self.inference(audio)
        output = self.parse_output(raw)
        return output