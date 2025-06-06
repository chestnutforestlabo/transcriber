import os
from torch.utils.data import Dataset
import soundfile as sf
from librosa.core import resample as lr_resample

class AudioInput(Dataset):
    def __init__(self, audio_dir: str, sampling_rate: int = 16000):
        self.audio_dir = audio_dir
        self._num_speakers = audio_dir.replace("/","").split("_")[-1]
        self.sampling_rate = sampling_rate
        self.audio_list = [
            fname for fname in os.listdir(audio_dir)
            if os.path.isfile(os.path.join(audio_dir, fname))
            and fname.lower().endswith(".wav")
        ]

    @property
    def num_speakers(self) -> int:
        return int(self._num_speakers)

    def __len__(self) -> int:
        return len(self.audio_list)

    def __getitem__(self, idx: int) -> dict:
        fname = self.audio_list[idx]
        path = os.path.join(self.audio_dir, fname)
        waveform, sr = sf.read(path)
        if sr != self.sampling_rate:
            waveform = lr_resample(
                waveform,
                orig_sr=sr,
                target_sr=self.sampling_rate
            )
        return {
            "basename":    fname,
            "waveform":    waveform,
            "sample_count": len(waveform)
        }