from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf
from data import AudioInput
from pyannote.core import Segment
from stereo import gate_stereo_waveform
from transcribe import transcribe_stereo_segments


def _tone(frequency: float, duration: float, sampling_rate: int) -> np.ndarray:
    time = np.arange(int(duration * sampling_rate)) / sampling_rate
    return np.sin(2.0 * np.pi * frequency * time).astype(np.float32)


class FixedVoiceActivityDetector:
    def __init__(self, intervals):
        self.intervals = intervals
        self.call_count = 0

    def __call__(self, waveform, sampling_rate):
        self.call_count += 1
        return self.intervals


def test_crosstalk_gate_removes_leakage_and_keeps_speaker_and_overlap():
    sampling_rate = 16_000
    waveform = np.zeros((4 * sampling_rate, 2), dtype=np.float32)
    leakage_gain = 10.0 ** (-12.0 / 20.0)

    left_speech = 0.4 * _tone(440.0, 1.0, sampling_rate)
    waveform[:sampling_rate, 0] = left_speech
    waveform[:sampling_rate, 1] = left_speech * leakage_gain

    right_speech = 0.4 * _tone(880.0, 1.0, sampling_rate)
    waveform[2 * sampling_rate : 3 * sampling_rate, 1] = right_speech
    waveform[2 * sampling_rate : 3 * sampling_rate, 0] = right_speech * leakage_gain

    waveform[3 * sampling_rate :, 0] = 0.3 * _tone(
        440.0,
        1.0,
        sampling_rate,
    )
    waveform[3 * sampling_rate :, 1] = 0.3 * _tone(
        880.0,
        1.0,
        sampling_rate,
    )

    detector = FixedVoiceActivityDetector(
        [
            (0, sampling_rate),
            (2 * sampling_rate, 4 * sampling_rate),
        ]
    )
    result = gate_stereo_waveform(
        waveform,
        sampling_rate,
        vad_detector=detector,
    )

    center_left = slice(int(0.2 * sampling_rate), int(0.8 * sampling_rate))
    center_right = slice(int(2.2 * sampling_rate), int(2.8 * sampling_rate))
    overlap = slice(int(3.2 * sampling_rate), int(3.8 * sampling_rate))

    assert detector.call_count == 2
    assert np.max(np.abs(result.waveform[center_left, 0])) > 0.35
    assert np.max(np.abs(result.waveform[center_left, 1])) == 0.0
    assert np.max(np.abs(result.waveform[center_right, 0])) == 0.0
    assert np.max(np.abs(result.waveform[center_right, 1])) > 0.35
    assert np.max(np.abs(result.waveform[overlap, 0])) > 0.25
    assert np.max(np.abs(result.waveform[overlap, 1])) > 0.25


def test_crosstalk_gate_ignores_brief_rms_decision_reversal():
    sampling_rate = 16_000
    tone = _tone(440.0, 1.0, sampling_rate)
    waveform = np.column_stack([0.4 * tone, 0.04 * tone])
    brief_start = int(0.4 * sampling_rate)
    brief_end = int(0.5 * sampling_rate)
    waveform[brief_start:brief_end, 0] = 0.04 * tone[brief_start:brief_end]
    waveform[brief_start:brief_end, 1] = 0.4 * tone[brief_start:brief_end]

    result = gate_stereo_waveform(
        waveform,
        sampling_rate,
        vad_detector=FixedVoiceActivityDetector([(0, sampling_rate)]),
    )

    # The 100 ms dominance swap is below the 200 ms stabilization interval.
    # It must not create a pair of short gate-state flips.
    assert np.max(np.abs(result.waveform[brief_start:brief_end, 0])) > 0.03
    assert np.max(np.abs(result.waveform[brief_start:brief_end, 1])) == 0.0


def test_channel_mode_asr_is_mocked_per_channel_and_merged_by_start():
    sampling_rate = 16_000
    first = np.column_stack(
        [
            0.4 * _tone(440.0, 1.0, sampling_rate),
            0.04 * _tone(440.0, 1.0, sampling_rate),
        ]
    )
    second = np.column_stack(
        [
            0.04 * _tone(880.0, 1.0, sampling_rate),
            0.4 * _tone(880.0, 1.0, sampling_rate),
        ]
    )

    class MockASR:
        def __init__(self):
            self.calls = 0

        def run(self, waveform):
            text = ("左の発話", "右の発話")[self.calls]
            self.calls += 1
            return [(Segment(0.0, len(waveform) / sampling_rate), text)]

    asr = MockASR()
    args = SimpleNamespace(
        asr_model_name="openai",
        channel_crosstalk_threshold_db=-6.0,
    )
    detector = FixedVoiceActivityDetector([(0, 2 * sampling_rate)])

    output = transcribe_stereo_segments(
        asr,
        args,
        [first, second],
        sampling_rate,
        vad_detector=detector,
    )

    assert asr.calls == 2
    assert output == [
        (Segment(0.0, 1.0), "SPEAKER_00", "左の発話"),
        (Segment(1.0, 2.0), "SPEAKER_01", "右の発話"),
    ]


def test_stereo_preprocess_keeps_channels_sample_aligned(tmp_path):
    sampling_rate = 48_000
    audio_dir = tmp_path / "num_speakers_2"
    audio_dir.mkdir()

    waveform = np.zeros((35 * sampling_rate, 2), dtype=np.float32)
    first = 0.1 * _tone(440.0, 4.0, sampling_rate)
    last = 0.1 * _tone(660.0, 4.0, sampling_rate)
    waveform[: 4 * sampling_rate, 0] = first
    waveform[: 4 * sampling_rate, 1] = -first
    waveform[-4 * sampling_rate :, 0] = last
    waveform[-4 * sampling_rate :, 1] = -last
    sf.write(
        audio_dir / "stereo.wav",
        waveform,
        sampling_rate,
        subtype="PCM_24",
    )

    dataset = AudioInput(str(audio_dir), channel_mode=True)
    item = dataset[0]
    processed = np.concatenate(item["waveform"], axis=0)

    assert processed.ndim == 2
    assert processed.shape[1] == 2
    assert len(processed) < 15 * dataset.sampling_rate
    np.testing.assert_allclose(processed[:, 0], -processed[:, 1], atol=2e-5)
    assert item["sample_count"] == len(processed)
    assert sum(item["segment_sample_counts"]) == len(processed)


def test_channel_mode_rejects_mono_wav_with_normal_mode_guidance(tmp_path):
    audio_dir = tmp_path / "num_speakers_2"
    audio_dir.mkdir()
    sf.write(
        audio_dir / "mono.wav",
        np.zeros(16_000, dtype=np.float32),
        16_000,
    )

    with pytest.raises(ValueError, match="normal mode without --channel_mode"):
        AudioInput(str(audio_dir), channel_mode=True)
