from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass, field

import numpy as np
import soundfile as sf
from librosa.core import resample as lr_resample
from librosa.onset import onset_strength
from scipy.signal import correlate, correlation_lags

DEFAULT_ALIGNMENT_WINDOW_SEC = 120.0
ONSET_HOP_DURATION_SEC = 0.01
MIN_CORRELATION_OVERLAP_SEC = 1.0
MIN_ALIGNMENT_CONFIDENCE = 0.35
MIN_PEAK_RATIO = 1.25
PEAK_EXCLUSION_SEC = 0.25
MIN_DRIFT_ANCHOR_SEPARATION_SEC = 5.0
MAX_REASONABLE_DRIFT_PPM = 5_000.0
CORRELATION_EPSILON = 1e-12
# Lags whose overlap holds almost no onset energy (silence vs. silence) make the
# normalized score 0/0-unstable and can spuriously reach ~1.0, so require the
# overlap energy to be a meaningful fraction of the best overlap's energy.
SILENT_OVERLAP_ENERGY_RATIO = 1e-3


@dataclass(frozen=True)
class CorrelationAnchor:
    """One matched onset anchor expressed in both recording timelines."""

    main_time_sec: float
    aux_time_sec: float
    confidence: float
    peak_ratio: float

    def to_meta(self) -> dict[str, float]:
        """Return JSON-serializable anchor diagnostics."""
        return {
            "main_time_sec": self.main_time_sec,
            "aux_time_sec": self.aux_time_sec,
            "confidence": self.confidence,
            "peak_ratio": self.peak_ratio,
        }


@dataclass
class AuxAlignment:
    """Linear mapping from an auxiliary timeline to the main timeline."""

    offset_sec: float
    drift_ppm: float
    time_scale: float
    method: str
    start_anchor: CorrelationAnchor | None = None
    end_anchor: CorrelationAnchor | None = None
    warnings: list[str] = field(default_factory=list)

    def aux_to_main(
        self,
        aux_time_sec: np.ndarray | float,
    ) -> np.ndarray | float:
        """Map auxiliary-local seconds onto the main recording timeline."""
        return self.offset_sec + self.time_scale * aux_time_sec

    def to_meta(self) -> dict[str, object]:
        """Return JSON-serializable alignment parameters and diagnostics."""
        return {
            "method": self.method,
            "offset_sec": self.offset_sec,
            "drift_ppm": self.drift_ppm,
            "time_scale": self.time_scale,
            "start_anchor": (
                self.start_anchor.to_meta() if self.start_anchor is not None else None
            ),
            "end_anchor": (
                self.end_anchor.to_meta() if self.end_anchor is not None else None
            ),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class AlignedChannels:
    """Synchronized channels over their common main-timeline interval."""

    waveform: np.ndarray
    sampling_rate: int
    overlap_start_sec: float
    overlap_end_sec: float
    alignments: tuple[AuxAlignment, ...]
    aux_paths: tuple[str, ...]

    def to_meta(self, main_path: str) -> dict[str, object]:
        """Build output metadata for every auxiliary speaker channel."""
        auxiliary_channels = []
        for index, (path, alignment) in enumerate(
            zip(self.aux_paths, self.alignments, strict=True),
            start=2,
        ):
            auxiliary_channels.append(
                {
                    "path": path,
                    "speaker": f"SPEAKER_{index:02d}",
                    **alignment.to_meta(),
                }
            )
        return {
            "mode": "pseudo_multichannel",
            "reference_audio": main_path,
            "sampling_rate": self.sampling_rate,
            "overlap": {
                "start_sec": self.overlap_start_sec,
                "end_sec": self.overlap_end_sec,
            },
            "auxiliary_channels": auxiliary_channels,
        }


def _onset_envelope(
    waveform: np.ndarray,
    sampling_rate: int,
    hop_length: int,
) -> np.ndarray:
    audio = np.asarray(waveform, dtype=np.float32)
    channels = audio[:, None] if audio.ndim == 1 else audio
    envelopes = [
        onset_strength(
            y=channels[:, channel],
            sr=sampling_rate,
            hop_length=hop_length,
            n_fft=512,
        )
        for channel in range(channels.shape[1])
    ]
    envelope = np.max(np.vstack(envelopes), axis=0)
    baseline = float(np.median(envelope))
    return np.maximum(envelope - baseline, 0.0)


def _peak_ratio(scores: np.ndarray, peak_index: int, exclusion_frames: int) -> float:
    eligible = np.ones(len(scores), dtype=bool)
    start = max(0, peak_index - exclusion_frames)
    end = min(len(scores), peak_index + exclusion_frames + 1)
    eligible[start:end] = False
    finite_candidates = scores[eligible & np.isfinite(scores)]
    if finite_candidates.size == 0:
        return 999.0 if scores[peak_index] > 0.0 else 0.0
    second_peak = max(0.0, float(np.max(finite_candidates)))
    ratio = (scores[peak_index] + CORRELATION_EPSILON) / (
        second_peak + CORRELATION_EPSILON
    )
    return float(np.clip(ratio, 0.0, 999.0))


def _correlation_anchor(
    main_window: np.ndarray,
    aux_window: np.ndarray,
    sampling_rate: int,
    main_window_start_sec: float,
    aux_window_start_sec: float,
) -> CorrelationAnchor:
    hop_length = max(1, int(round(ONSET_HOP_DURATION_SEC * sampling_rate)))
    main_envelope = _onset_envelope(main_window, sampling_rate, hop_length)
    aux_envelope = _onset_envelope(aux_window, sampling_rate, hop_length)
    if main_envelope.size == 0 or aux_envelope.size == 0:
        return CorrelationAnchor(
            main_time_sec=main_window_start_sec,
            aux_time_sec=aux_window_start_sec,
            confidence=0.0,
            peak_ratio=0.0,
        )

    numerator = correlate(main_envelope, aux_envelope, mode="full", method="fft")
    main_energy = correlate(
        np.square(main_envelope),
        np.ones(len(aux_envelope)),
        mode="full",
        method="fft",
    )
    aux_energy = correlate(
        np.ones(len(main_envelope)),
        np.square(aux_envelope),
        mode="full",
        method="fft",
    )
    denominator = np.sqrt(np.maximum(main_energy * aux_energy, 0.0))
    scores = np.full(len(numerator), -np.inf, dtype=np.float64)
    energy_floor = SILENT_OVERLAP_ENERGY_RATIO * float(np.max(denominator))
    valid_energy = denominator > max(energy_floor, CORRELATION_EPSILON)
    scores[valid_energy] = numerator[valid_energy] / denominator[valid_energy]

    lags = correlation_lags(len(main_envelope), len(aux_envelope), mode="full")
    overlap_frames = np.minimum(
        len(main_envelope) - np.maximum(lags, 0),
        len(aux_envelope) + np.minimum(lags, 0),
    )
    minimum_overlap_frames = max(
        1,
        int(np.ceil(MIN_CORRELATION_OVERLAP_SEC * sampling_rate / hop_length)),
    )
    scores[overlap_frames < minimum_overlap_frames] = -np.inf

    if not np.isfinite(scores).any():
        return CorrelationAnchor(
            main_time_sec=main_window_start_sec,
            aux_time_sec=aux_window_start_sec,
            confidence=0.0,
            peak_ratio=0.0,
        )

    peak_index = int(np.nanargmax(scores))
    lag = int(lags[peak_index])
    overlap = int(overlap_frames[peak_index])
    if lag >= 0:
        main_start = lag
        aux_start = 0
    else:
        main_start = 0
        aux_start = -lag

    products = (
        main_envelope[main_start : main_start + overlap]
        * aux_envelope[aux_start : aux_start + overlap]
    )
    local_peak = int(np.argmax(products)) if products.size else 0
    main_frame = main_start + local_peak
    aux_frame = aux_start + local_peak
    exclusion_frames = max(
        1,
        int(round(PEAK_EXCLUSION_SEC * sampling_rate / hop_length)),
    )
    return CorrelationAnchor(
        main_time_sec=main_window_start_sec
        + main_frame * hop_length / float(sampling_rate),
        aux_time_sec=aux_window_start_sec
        + aux_frame * hop_length / float(sampling_rate),
        confidence=float(np.clip(scores[peak_index], 0.0, 1.0)),
        peak_ratio=_peak_ratio(scores, peak_index, exclusion_frames),
    )


def _anchor_is_confident(anchor: CorrelationAnchor) -> bool:
    return (
        anchor.confidence >= MIN_ALIGNMENT_CONFIDENCE
        and anchor.peak_ratio >= MIN_PEAK_RATIO
    )


def estimate_aux_alignment(
    main_waveform: np.ndarray,
    aux_waveform: np.ndarray,
    sampling_rate: int,
    window_sec: float = DEFAULT_ALIGNMENT_WINDOW_SEC,
    manual_offset_sec: float | None = None,
) -> AuxAlignment:
    """Estimate ``main_time = offset + scale * aux_time`` from two clap windows."""
    if sampling_rate <= 0:
        raise ValueError("sampling_rate must be positive.")
    if window_sec <= 0.0:
        raise ValueError("window_sec must be positive.")
    if len(main_waveform) == 0 or len(aux_waveform) == 0:
        raise ValueError("Cannot align empty audio.")
    if manual_offset_sec is not None:
        return AuxAlignment(
            offset_sec=float(manual_offset_sec),
            drift_ppm=0.0,
            time_scale=1.0,
            method="manual",
        )

    main_window_samples = min(
        len(main_waveform),
        int(round(window_sec * sampling_rate)),
    )
    aux_window_samples = min(
        len(aux_waveform),
        int(round(window_sec * sampling_rate)),
    )
    start_anchor = _correlation_anchor(
        main_waveform[:main_window_samples],
        aux_waveform[:aux_window_samples],
        sampling_rate,
        0.0,
        0.0,
    )
    warnings = []
    if not _anchor_is_confident(start_anchor):
        warnings.append(
            "Start clap correlation is ambiguous; verify the result or use "
            "--aux_offset."
        )

    start_offset = start_anchor.main_time_sec - start_anchor.aux_time_sec
    main_tail_start = max(0, len(main_waveform) - main_window_samples)
    aux_tail_start = max(0, len(aux_waveform) - aux_window_samples)
    has_distinct_tail_window = main_tail_start > 0 and aux_tail_start > 0
    if not has_distinct_tail_window:
        warnings.append(
            "Recording is too short for distinct start/end windows; "
            "clock-drift correction was skipped."
        )
        return AuxAlignment(
            offset_sec=start_offset,
            drift_ppm=0.0,
            time_scale=1.0,
            method="automatic_offset_only",
            start_anchor=start_anchor,
            warnings=warnings,
        )

    end_anchor = _correlation_anchor(
        main_waveform[main_tail_start:],
        aux_waveform[aux_tail_start:],
        sampling_rate,
        main_tail_start / float(sampling_rate),
        aux_tail_start / float(sampling_rate),
    )
    if not _anchor_is_confident(end_anchor):
        warnings.append(
            "End clap correlation is ambiguous; clock-drift correction was "
            "skipped."
        )
        return AuxAlignment(
            offset_sec=start_offset,
            drift_ppm=0.0,
            time_scale=1.0,
            method="automatic_offset_only",
            start_anchor=start_anchor,
            end_anchor=end_anchor,
            warnings=warnings,
        )

    aux_separation = end_anchor.aux_time_sec - start_anchor.aux_time_sec
    main_separation = end_anchor.main_time_sec - start_anchor.main_time_sec
    if (
        aux_separation < MIN_DRIFT_ANCHOR_SEPARATION_SEC
        or main_separation <= 0.0
    ):
        warnings.append(
            "Clap anchors are not sufficiently separated; clock-drift "
            "correction was skipped."
        )
        return AuxAlignment(
            offset_sec=start_offset,
            drift_ppm=0.0,
            time_scale=1.0,
            method="automatic_offset_only",
            start_anchor=start_anchor,
            end_anchor=end_anchor,
            warnings=warnings,
        )

    time_scale = main_separation / aux_separation
    drift_ppm = (time_scale - 1.0) * 1_000_000.0
    if abs(drift_ppm) > MAX_REASONABLE_DRIFT_PPM:
        warnings.append(
            f"Estimated drift ({drift_ppm:+.1f} ppm) is implausibly large; "
            "clock-drift correction was skipped."
        )
        return AuxAlignment(
            offset_sec=start_offset,
            drift_ppm=0.0,
            time_scale=1.0,
            method="automatic_offset_only",
            start_anchor=start_anchor,
            end_anchor=end_anchor,
            warnings=warnings,
        )

    offset_sec = (
        start_anchor.main_time_sec - time_scale * start_anchor.aux_time_sec
    )
    return AuxAlignment(
        offset_sec=offset_sec,
        drift_ppm=drift_ppm,
        time_scale=time_scale,
        method="automatic_offset_and_drift",
        start_anchor=start_anchor,
        end_anchor=end_anchor,
        warnings=warnings,
    )


def _read_audio(
    path: str,
    target_sampling_rate: int,
    auxiliary: bool,
) -> np.ndarray:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Audio file not found: {path}")

    read_path = path
    temporary_directory = None
    if auxiliary and os.path.splitext(path)[1].lower() != ".wav":
        temporary_directory = tempfile.TemporaryDirectory()
        read_path = os.path.join(temporary_directory.name, "converted.wav")
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-i",
                    path,
                    "-c:a",
                    "pcm_s16le",
                    read_path,
                ],
                check=True,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "ffmpeg is required to convert non-WAV auxiliary audio."
            ) from exc
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                f"ffmpeg could not convert auxiliary audio: {path}"
            ) from exc

    try:
        waveform, sampling_rate = sf.read(
            read_path,
            always_2d=True,
            dtype="float32",
        )
    finally:
        if temporary_directory is not None:
            temporary_directory.cleanup()

    if auxiliary:
        if waveform.shape[1] > 1:
            print(
                f"Auxiliary audio {path} has {waveform.shape[1]} channels; "
                "using ch0."
            )
        waveform = waveform[:, 0]
    elif waveform.shape[1] != 2:
        raise ValueError(
            "Pseudo-multichannel mode requires a 2-channel main WAV "
            f"(received {waveform.shape[1]}ch: {path})."
        )

    if sampling_rate != target_sampling_rate:
        waveform = lr_resample(
            waveform,
            orig_sr=sampling_rate,
            target_sr=target_sampling_rate,
            axis=0,
        )
    return np.asarray(waveform, dtype=np.float32)


def align_audio_files(
    main_path: str,
    aux_paths: list[str],
    target_sampling_rate: int = 16_000,
    manual_offsets_sec: list[float] | None = None,
    window_sec: float = DEFAULT_ALIGNMENT_WINDOW_SEC,
) -> AlignedChannels:
    """Load, align, drift-correct, and trim main plus auxiliary channels."""
    if not aux_paths:
        raise ValueError("At least one auxiliary audio path is required.")
    if manual_offsets_sec is not None and len(manual_offsets_sec) != len(aux_paths):
        raise ValueError("--aux_offset requires exactly one value per --aux_audio.")

    main_waveform = _read_audio(main_path, target_sampling_rate, auxiliary=False)
    aux_waveforms = [
        _read_audio(path, target_sampling_rate, auxiliary=True) for path in aux_paths
    ]
    offsets = manual_offsets_sec or [None] * len(aux_paths)
    alignments = [
        estimate_aux_alignment(
            main_waveform,
            aux_waveform,
            target_sampling_rate,
            window_sec=window_sec,
            manual_offset_sec=manual_offset,
        )
        for aux_waveform, manual_offset in zip(
            aux_waveforms,
            offsets,
            strict=True,
        )
    ]

    main_duration = len(main_waveform) / float(target_sampling_rate)
    overlap_start = max(
        0.0,
        *(alignment.offset_sec for alignment in alignments),
    )
    overlap_end = min(
        main_duration,
        *(
            float(
                alignment.aux_to_main(
                    len(aux_waveform) / float(target_sampling_rate)
                )
            )
            for alignment, aux_waveform in zip(
                alignments,
                aux_waveforms,
                strict=True,
            )
        ),
    )
    start_sample = max(0, int(np.ceil(overlap_start * target_sampling_rate)))
    end_sample = min(
        len(main_waveform),
        int(np.floor(overlap_end * target_sampling_rate)),
    )
    if end_sample <= start_sample:
        raise ValueError(
            "Main and auxiliary recordings have no overlapping interval after "
            "alignment."
        )

    main_times = np.arange(start_sample, end_sample) / float(target_sampling_rate)
    channels = [
        main_waveform[start_sample:end_sample, 0],
        main_waveform[start_sample:end_sample, 1],
    ]
    for alignment, aux_waveform in zip(
        alignments,
        aux_waveforms,
        strict=True,
    ):
        aux_positions = (
            (main_times - alignment.offset_sec)
            / alignment.time_scale
            * target_sampling_rate
        )
        channels.append(
            np.interp(
                aux_positions,
                np.arange(len(aux_waveform)),
                aux_waveform,
            ).astype(np.float32)
        )

    return AlignedChannels(
        waveform=np.column_stack(channels),
        sampling_rate=target_sampling_rate,
        overlap_start_sec=start_sample / float(target_sampling_rate),
        overlap_end_sec=end_sample / float(target_sampling_rate),
        alignments=tuple(alignments),
        aux_paths=tuple(aux_paths),
    )
