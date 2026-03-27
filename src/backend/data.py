import os
import numpy as np
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

    @staticmethod
    def _audio_envelope(waveform: np.ndarray, window_size: int) -> np.ndarray:
        if waveform.ndim == 1:
            amplitude = np.abs(waveform)
        else:
            amplitude = np.max(np.abs(waveform), axis=1)
        if window_size <= 1:
            return amplitude
        kernel = np.ones(window_size, dtype=np.float64) / window_size
        return np.convolve(amplitude, kernel, mode="same")

    @staticmethod
    def _mask_to_intervals(mask: np.ndarray) -> list[tuple[int, int]]:
        if mask.size == 0:
            return []
        padded = np.pad(mask.astype(np.int8), (1, 1), mode="constant", constant_values=0)
        diff = np.diff(padded)
        starts = np.where(diff == 1)[0]
        ends = np.where(diff == -1)[0]
        return [(int(s), int(e)) for s, e in zip(starts, ends) if e > s]

    def _detect_silences(
        self,
        waveform: np.ndarray,
        sr: int,
        threshold_ratio: float = 0.02,
        min_threshold: float = 1e-4
    ) -> list[tuple[int, int]]:
        window_size = max(1, int(sr * 0.02))
        envelope = self._audio_envelope(waveform, window_size)
        max_amp = float(np.max(envelope)) if envelope.size > 0 else 0.0
        threshold = max(min_threshold, max_amp * threshold_ratio)
        silent_mask = envelope <= threshold
        return self._mask_to_intervals(silent_mask)

    def _shrink_long_silences(
        self,
        waveform: np.ndarray,
        sr: int,
        max_silence_sec: float = 2.0
    ) -> np.ndarray:
        silences = self._detect_silences(waveform, sr)
        max_silence_samples = int(max_silence_sec * sr)
        if not silences:
            return waveform

        chunks = []
        cursor = 0
        for start, end in silences:
            if start > cursor:
                chunks.append(waveform[cursor:start])
            silence_len = end - start
            if silence_len <= max_silence_samples:
                chunks.append(waveform[start:end])
            else:
                keep = max_silence_samples
                chunks.append(waveform[start:start + keep])
            cursor = end
        if cursor < len(waveform):
            chunks.append(waveform[cursor:])

        if not chunks:
            return waveform
        return np.concatenate(chunks, axis=0)

    def _split_by_silence_candidates(
        self,
        waveform: np.ndarray,
        sr: int,
        min_chunk_sec: float = 20.0,
        max_chunk_sec: float = 30.0,
        min_split_silence_sec: float = 0.15
    ) -> list[np.ndarray]:
        total_samples = len(waveform)
        if total_samples == 0:
            return [waveform]

        min_chunk = int(min_chunk_sec * sr)
        max_chunk = int(max_chunk_sec * sr)
        min_split_silence = int(min_split_silence_sec * sr)

        silences = self._detect_silences(waveform, sr)
        mids = []
        for start, end in silences:
            if (end - start) >= min_split_silence:
                mid = (start + end) // 2
                if 0 < mid < total_samples:
                    mids.append(mid)
        mids = sorted(set(mids))

        if not mids:
            return [waveform]

        boundaries: list[tuple[int, int]] = []
        start = 0

        while start < total_samples:
            remaining = total_samples - start
            if remaining <= max_chunk:
                boundaries.append((start, total_samples))
                break

            window_min = start + min_chunk
            window_max = start + max_chunk
            in_window = [m for m in mids if window_min <= m < window_max]

            if in_window:
                end = in_window[-1]
            else:
                after_max = [m for m in mids if m >= window_max]
                end = after_max[0] if after_max else total_samples

            if end <= start:
                end = min(start + max_chunk, total_samples)

            boundaries.append((start, end))
            start = end

        if len(boundaries) >= 2:
            last_start, last_end = boundaries[-1]
            prev_start, prev_end = boundaries[-2]
            last_len = last_end - last_start
            prev_len = prev_end - prev_start
            if last_len < min_chunk and (prev_len + last_len) <= max_chunk:
                boundaries[-2] = (prev_start, last_end)
                boundaries.pop()

        return [waveform[s:e] for s, e in boundaries if e > s]

    def _preprocess_waveform(self, waveform: np.ndarray, sr: int) -> list[np.ndarray]:
        duration_sec = len(waveform) / float(sr)
        if duration_sec <= 30.0:
            return [waveform]

        compressed = self._shrink_long_silences(waveform, sr, max_silence_sec=2.0)
        segments = self._split_by_silence_candidates(
            compressed,
            sr,
            min_chunk_sec=20.0,
            max_chunk_sec=30.0,
            min_split_silence_sec=0.15
        )
        return segments if segments else [compressed]

    def __getitem__(self, idx: int) -> dict:
        fname = self.audio_list[idx]
        path = os.path.join(self.audio_dir, fname)
        waveform, sr = sf.read(path)
        if sr != self.sampling_rate:
            waveform = lr_resample(
                waveform,
                orig_sr=sr,
                target_sr=self.sampling_rate,
                axis=0
            )
            sr = self.sampling_rate
        waveform_segments = self._preprocess_waveform(waveform, sr)
        return {
            "basename":    fname,
            "waveform":    waveform_segments,
            "sample_count": sum(len(seg) for seg in waveform_segments),
            "segment_sample_counts": [len(seg) for seg in waveform_segments]
        }
