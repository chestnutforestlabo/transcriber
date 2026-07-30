from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

import numpy as np

# A lavalier microphone usually captures the remote speaker at least 6 dB
# below its wearer.  Ratios close to 0 dB are deliberately retained so that
# genuine simultaneous speech remains on both channels.
DEFAULT_CROSSTALK_THRESHOLD_DB = -6.0
CROSSTALK_HYSTERESIS_DB = 2.0
MIN_GATE_STATE_DURATION_SEC = 0.2
MIN_ASR_ACTIVE_DURATION_SEC = 0.1
RMS_FRAME_DURATION_SEC = 0.032
RMS_EPSILON = 1e-8

# The upper quartile is a robust estimate of each microphone's ordinary
# close-talk speech level.  Unlike the maximum it ignores clap/transient peaks,
# and unlike the median it is not easily pulled down when VAD also detects
# low-level bleed from another microphone.
SPEECH_LEVEL_PERCENTILE = 75.0

# Silero's defaults are tuned for general audio.  These shorter minimums keep
# brief Japanese backchannels while still joining tiny VAD gaps.
VAD_THRESHOLD = 0.5
VAD_MIN_SPEECH_DURATION_MS = 100
VAD_MIN_SILENCE_DURATION_MS = 100
VAD_SPEECH_PAD_MS = 50

SpeechInterval = tuple[int, int]
VoiceActivityDetector = Callable[
    [np.ndarray, int],
    Iterable[SpeechInterval | dict[str, int]],
]


@dataclass(frozen=True)
class StereoGatingResult:
    """Gated audio plus sample-level VAD and keep decisions."""

    waveform: np.ndarray
    speech_mask: np.ndarray
    keep_mask: np.ndarray

    @property
    def removed_mask(self) -> np.ndarray:
        """Return VAD-positive samples removed as likely crosstalk."""
        return self.speech_mask & ~self.keep_mask


@dataclass(frozen=True)
class MultichannelGatingResult:
    """Gated N-channel audio plus VAD, keep, and gain-calibration data."""

    waveform: np.ndarray
    speech_mask: np.ndarray
    keep_mask: np.ndarray
    speech_levels: np.ndarray

    @property
    def removed_mask(self) -> np.ndarray:
        """Return VAD-positive samples removed as likely crosstalk."""
        return self.speech_mask & ~self.keep_mask


class SileroVoiceActivityDetector:
    """Lazily loaded CPU VAD shared by the input channels."""

    def __init__(self, threshold: float = VAD_THRESHOLD) -> None:
        """Store the VAD probability threshold and defer model loading."""
        self.threshold = threshold
        self._model = None
        self._get_speech_timestamps = None

    def _load(self) -> None:
        if self._model is not None:
            return

        try:
            from silero_vad import get_speech_timestamps, load_silero_vad
        except ImportError as exc:
            raise ImportError(
                "Channel mode requires `silero-vad`. Run `uv sync` to install it."
            ) from exc

        self._model = load_silero_vad()
        self._get_speech_timestamps = get_speech_timestamps

    def __call__(
        self,
        waveform: np.ndarray,
        sampling_rate: int,
    ) -> list[SpeechInterval]:
        """Return speech intervals as sample-index pairs."""
        self._load()

        import torch

        audio = torch.from_numpy(
            np.asarray(waveform, dtype=np.float32),
        )
        timestamps = self._get_speech_timestamps(
            audio,
            self._model,
            sampling_rate=sampling_rate,
            threshold=self.threshold,
            min_speech_duration_ms=VAD_MIN_SPEECH_DURATION_MS,
            min_silence_duration_ms=VAD_MIN_SILENCE_DURATION_MS,
            speech_pad_ms=VAD_SPEECH_PAD_MS,
            return_seconds=False,
        )
        return [
            (int(timestamp["start"]), int(timestamp["end"])) for timestamp in timestamps
        ]


def _intervals_to_mask(
    intervals: Iterable[SpeechInterval | dict[str, int]],
    sample_count: int,
) -> np.ndarray:
    mask = np.zeros(sample_count, dtype=bool)
    for interval in intervals:
        if isinstance(interval, dict):
            start = interval.get("start")
            end = interval.get("end")
        else:
            start, end = interval
        if start is None or end is None:
            continue
        bounded_start = max(0, min(sample_count, int(start)))
        bounded_end = max(bounded_start, min(sample_count, int(end)))
        mask[bounded_start:bounded_end] = True
    return mask


def _runs(values: np.ndarray) -> list[tuple[int, int, bool]]:
    if values.size == 0:
        return []

    changes = np.flatnonzero(values[1:] != values[:-1]) + 1
    starts = np.concatenate(([0], changes))
    ends = np.concatenate((changes, [len(values)]))
    return [
        (int(start), int(end), bool(values[start]))
        for start, end in zip(starts, ends, strict=True)
    ]


def _suppress_short_reversals(
    states: np.ndarray,
    active: np.ndarray,
    minimum_frames: int,
) -> np.ndarray:
    """Ignore brief state flips bounded by the same decision on both sides."""
    stabilized = states.copy()
    for active_start, active_end, is_active in _runs(active):
        if not is_active:
            continue

        span = stabilized[active_start:active_end].copy()
        while True:
            span_runs = _runs(span)
            replacement = None
            for index in range(1, len(span_runs) - 1):
                start, end, value = span_runs[index]
                previous_value = span_runs[index - 1][2]
                next_value = span_runs[index + 1][2]
                if (
                    end - start < minimum_frames
                    and previous_value == next_value
                    and value != previous_value
                ):
                    replacement = (start, end, previous_value)
                    break
            if replacement is None:
                break
            start, end, value = replacement
            span[start:end] = value

        stabilized[active_start:active_end] = span
    return stabilized


def _leak_frames(
    rms: np.ndarray,
    active: np.ndarray,
    channel: int,
    threshold_db: float,
    minimum_frames: int,
) -> np.ndarray:
    other_channel = 1 - channel
    ratio_db = 20.0 * np.log10(
        (rms[:, channel] + RMS_EPSILON) / (rms[:, other_channel] + RMS_EPSILON)
    )

    leaking = False
    decisions = np.zeros(len(rms), dtype=bool)
    for index, is_active in enumerate(active):
        if not is_active:
            leaking = False
            continue

        if leaking:
            if ratio_db[index] >= threshold_db + CROSSTALK_HYSTERESIS_DB:
                leaking = False
        elif ratio_db[index] <= threshold_db:
            leaking = True
        decisions[index] = leaking

    return _suppress_short_reversals(decisions, active, minimum_frames)


def gate_stereo_waveform(
    waveform: np.ndarray,
    sampling_rate: int,
    crosstalk_threshold_db: float = DEFAULT_CROSSTALK_THRESHOLD_DB,
    vad_detector: VoiceActivityDetector | None = None,
) -> StereoGatingResult:
    """Remove quiet remote-speaker leakage while retaining overlap speech."""
    stereo = np.asarray(waveform, dtype=np.float32)
    if stereo.ndim != 2 or stereo.shape[1] != 2:
        raise ValueError(
            "Channel mode requires a 2-channel stereo waveform "
            f"(received shape {stereo.shape})."
        )
    if crosstalk_threshold_db >= 0.0:
        raise ValueError(
            "The crosstalk threshold must be negative dB (for example, -6.0)."
        )
    if sampling_rate <= 0:
        raise ValueError("sampling_rate must be positive.")
    if len(stereo) == 0:
        empty_mask = np.zeros((0, 2), dtype=bool)
        return StereoGatingResult(
            waveform=stereo.copy(),
            speech_mask=empty_mask,
            keep_mask=empty_mask.copy(),
        )

    detector = vad_detector or SileroVoiceActivityDetector()
    speech_mask = np.column_stack(
        [
            _intervals_to_mask(
                detector(stereo[:, channel], sampling_rate),
                len(stereo),
            )
            for channel in range(2)
        ]
    )

    frame_samples = max(1, int(round(RMS_FRAME_DURATION_SEC * sampling_rate)))
    frame_count = int(np.ceil(len(stereo) / frame_samples))
    padded_samples = frame_count * frame_samples
    padded_waveform = np.pad(
        stereo,
        ((0, padded_samples - len(stereo)), (0, 0)),
    )
    frames = padded_waveform.reshape(frame_count, frame_samples, 2)
    rms = np.sqrt(np.mean(np.square(frames, dtype=np.float64), axis=1))

    padded_speech = np.pad(
        speech_mask,
        ((0, padded_samples - len(stereo)), (0, 0)),
    )
    active_frames = padded_speech.reshape(frame_count, frame_samples, 2).any(axis=1)
    minimum_frames = max(
        1,
        int(np.ceil(MIN_GATE_STATE_DURATION_SEC * sampling_rate / frame_samples)),
    )

    leak_frames = np.column_stack(
        [
            _leak_frames(
                rms,
                active_frames[:, channel],
                channel,
                crosstalk_threshold_db,
                minimum_frames,
            )
            for channel in range(2)
        ]
    )
    leak_mask = np.repeat(leak_frames, frame_samples, axis=0)[: len(stereo)]
    keep_mask = speech_mask & ~leak_mask

    gated = stereo.copy()
    gated[~keep_mask] = 0.0
    return StereoGatingResult(
        waveform=gated,
        speech_mask=speech_mask,
        keep_mask=keep_mask,
    )


def gate_multichannel_waveform(
    waveform: np.ndarray,
    sampling_rate: int,
    crosstalk_threshold_db: float = DEFAULT_CROSSTALK_THRESHOLD_DB,
    vad_detector: VoiceActivityDetector | None = None,
) -> MultichannelGatingResult:
    """Gate crosstalk across gain-normalized synchronized input channels."""
    channels = np.asarray(waveform, dtype=np.float32)
    if channels.ndim != 2 or channels.shape[1] < 2:
        raise ValueError(
            "Multichannel gating requires at least 2 channels "
            f"(received shape {channels.shape})."
        )
    if crosstalk_threshold_db >= 0.0:
        raise ValueError(
            "The crosstalk threshold must be negative dB (for example, -6.0)."
        )
    if sampling_rate <= 0:
        raise ValueError("sampling_rate must be positive.")
    if len(channels) == 0:
        empty_mask = np.zeros(channels.shape, dtype=bool)
        return MultichannelGatingResult(
            waveform=channels.copy(),
            speech_mask=empty_mask,
            keep_mask=empty_mask.copy(),
            speech_levels=np.ones(channels.shape[1], dtype=np.float64),
        )

    detector = vad_detector or SileroVoiceActivityDetector()
    speech_mask = np.column_stack(
        [
            _intervals_to_mask(
                detector(channels[:, channel], sampling_rate),
                len(channels),
            )
            for channel in range(channels.shape[1])
        ]
    )

    frame_samples = max(1, int(round(RMS_FRAME_DURATION_SEC * sampling_rate)))
    frame_count = int(np.ceil(len(channels) / frame_samples))
    padded_samples = frame_count * frame_samples
    padded_waveform = np.pad(
        channels,
        ((0, padded_samples - len(channels)), (0, 0)),
    )
    frames = padded_waveform.reshape(
        frame_count,
        frame_samples,
        channels.shape[1],
    )
    rms = np.sqrt(np.mean(np.square(frames, dtype=np.float64), axis=1))

    padded_speech = np.pad(
        speech_mask,
        ((0, padded_samples - len(channels)), (0, 0)),
    )
    active_frames = padded_speech.reshape(
        frame_count,
        frame_samples,
        channels.shape[1],
    ).any(axis=1)
    speech_levels = np.ones(channels.shape[1], dtype=np.float64)
    for channel in range(channels.shape[1]):
        candidates = rms[active_frames[:, channel], channel]
        candidates = candidates[candidates > RMS_EPSILON]
        if candidates.size:
            speech_levels[channel] = max(
                RMS_EPSILON,
                float(np.percentile(candidates, SPEECH_LEVEL_PERCENTILE)),
            )

    normalized_rms = rms / speech_levels[None, :]
    active_normalized_rms = np.where(active_frames, normalized_rms, 0.0)
    maximum_rms = np.max(active_normalized_rms, axis=1, keepdims=True)
    relative_db = 20.0 * np.log10(
        (active_normalized_rms + RMS_EPSILON)
        / (maximum_rms + RMS_EPSILON)
    )
    keep_frames = active_frames & (relative_db >= crosstalk_threshold_db)

    minimum_frames = max(
        1,
        int(np.ceil(MIN_GATE_STATE_DURATION_SEC * sampling_rate / frame_samples)),
    )
    for channel in range(channels.shape[1]):
        keep_frames[:, channel] = _suppress_short_reversals(
            keep_frames[:, channel],
            active_frames[:, channel],
            minimum_frames,
        )

    frame_keep_mask = np.repeat(keep_frames, frame_samples, axis=0)[: len(channels)]
    keep_mask = speech_mask & frame_keep_mask
    gated = channels.copy()
    gated[~keep_mask] = 0.0
    return MultichannelGatingResult(
        waveform=gated,
        speech_mask=speech_mask,
        keep_mask=keep_mask,
        speech_levels=speech_levels,
    )
