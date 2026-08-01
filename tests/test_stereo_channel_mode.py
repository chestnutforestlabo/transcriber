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


class PerChannelVoiceActivityDetector:
    def __init__(self, intervals_by_channel):
        self.intervals_by_channel = intervals_by_channel
        self.call_count = 0

    def __call__(self, waveform, sampling_rate):
        intervals = self.intervals_by_channel[self.call_count]
        self.call_count += 1
        return intervals


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


@pytest.mark.parametrize("asr_model_name", ["qwen", "kotoba"])
def test_timestampless_channel_asr_uses_vad_boundaries_and_padded_audio(
    asr_model_name,
):
    sampling_rate = 1_000
    sample_count = 3_000
    left = np.linspace(0.1, 0.5, sample_count, dtype=np.float32)
    waveform = np.column_stack([left, np.zeros(sample_count, dtype=np.float32)])
    intervals = [(500, 1_000), (1_800, 2_300)]
    detector = PerChannelVoiceActivityDetector([intervals, []])

    class MockASR:
        def __init__(self):
            self.calls = []

        def run(self, audio):
            if isinstance(audio, tuple):
                audio, received_sampling_rate = audio
                assert received_sampling_rate == sampling_rate
            self.calls.append(audio.copy())
            return [(Segment(0.1, 0.2), f"発話{len(self.calls)}")]

    asr = MockASR()
    output = transcribe_stereo_segments(
        asr,
        SimpleNamespace(
            asr_model_name=asr_model_name,
            channel_crosstalk_threshold_db=-6.0,
        ),
        [waveform],
        sampling_rate,
        vad_detector=detector,
    )

    assert detector.call_count == 2
    assert len(asr.calls) == 2
    np.testing.assert_array_equal(asr.calls[0], left[300:1_200])
    np.testing.assert_array_equal(asr.calls[1], left[1_600:2_500])
    assert output == [
        (Segment(0.5, 1.0), "SPEAKER_00", "発話1"),
        (Segment(1.8, 2.3), "SPEAKER_00", "発話2"),
    ]


def test_timestampless_channel_asr_discards_empty_and_hallucinated_text():
    sampling_rate = 1_000
    sample_count = 3_000
    waveform = np.column_stack(
        [
            np.ones(sample_count, dtype=np.float32),
            np.zeros(sample_count, dtype=np.float32),
        ]
    )
    intervals = [(200, 600), (1_000, 1_400), (2_000, 2_400)]

    class MockASR:
        def __init__(self):
            self.responses = iter(
                ["", "ご視聴ありがとうございました。", "実際の発話"]
            )

        def run(self, audio):
            return [(Segment(0.0, len(audio) / sampling_rate), next(self.responses))]

    output = transcribe_stereo_segments(
        MockASR(),
        SimpleNamespace(
            asr_model_name="kotoba",
            channel_crosstalk_threshold_db=-6.0,
        ),
        [waveform],
        sampling_rate,
        vad_detector=PerChannelVoiceActivityDetector([intervals, []]),
    )

    assert output == [
        (Segment(2.0, 2.4), "SPEAKER_00", "実際の発話"),
    ]


def test_timestampless_channel_asr_splits_continuous_speech_over_30_seconds():
    sampling_rate = 100
    sample_count = 65 * sampling_rate
    waveform = np.column_stack(
        [
            np.ones(sample_count, dtype=np.float32),
            np.zeros(sample_count, dtype=np.float32),
        ]
    )

    class MockASR:
        def __init__(self):
            self.calls = 0
            self.call_durations = []

        def run(self, audio):
            self.calls += 1
            self.call_durations.append(len(audio) / sampling_rate)
            return [(Segment(0.0, len(audio) / sampling_rate), "連続発話")]

    asr = MockASR()
    output = transcribe_stereo_segments(
        asr,
        SimpleNamespace(
            asr_model_name="kotoba",
            channel_crosstalk_threshold_db=-6.0,
        ),
        [waveform],
        sampling_rate,
        vad_detector=PerChannelVoiceActivityDetector([[(0, sample_count)], []]),
    )

    assert asr.calls == 3
    assert output[0][0].start == 0.0
    assert output[-1][0].end == 65.0
    assert all(segment.duration <= 30.0 for segment, _, _ in output)
    assert all(duration <= 30.0 for duration in asr.call_durations)


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
