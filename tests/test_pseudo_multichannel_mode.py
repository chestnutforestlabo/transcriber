import json
from types import SimpleNamespace

import numpy as np
import soundfile as sf
from alignment import estimate_aux_alignment
from pyannote.core import Segment
from stereo import gate_multichannel_waveform
from transcribe import transcribe_multichannel_segments
from utils import save_transcripts_json


def _tone(frequency: float, duration: float, sampling_rate: int) -> np.ndarray:
    time = np.arange(int(round(duration * sampling_rate))) / sampling_rate
    return np.sin(2.0 * np.pi * frequency * time).astype(np.float32)


def _add_burst(
    waveform: np.ndarray,
    time_sec: float,
    burst: np.ndarray,
    sampling_rate: int,
) -> None:
    start = int(round(time_sec * sampling_rate))
    end = min(len(waveform), start + len(burst))
    waveform[start:end] += burst[: end - start]


def _clap(sampling_rate: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    sample_count = int(round(0.035 * sampling_rate))
    envelope = np.exp(-np.linspace(0.0, 7.0, sample_count))
    return (0.9 * rng.standard_normal(sample_count) * envelope).astype(np.float32)


def test_onset_alignment_recovers_known_start_offset_within_30ms():
    sampling_rate = 8_000
    offset_sec = 1.7
    main = np.zeros((20 * sampling_rate, 2), dtype=np.float32)
    aux = np.zeros(int(round((20.0 - offset_sec) * sampling_rate)), dtype=np.float32)

    for index, main_time in enumerate((2.5, 18.0)):
        burst = _clap(sampling_rate, seed=index)
        _add_burst(main[:, 0], main_time, burst, sampling_rate)
        _add_burst(main[:, 1], main_time, 0.8 * burst, sampling_rate)
        _add_burst(aux, main_time - offset_sec, 0.6 * burst, sampling_rate)

    alignment = estimate_aux_alignment(
        main,
        aux,
        sampling_rate,
        window_sec=5.0,
    )

    assert alignment.method == "automatic_offset_and_drift"
    assert abs(alignment.offset_sec - offset_sec) <= 0.03
    assert alignment.start_anchor is not None
    assert alignment.start_anchor.confidence >= 0.35


def test_onset_alignment_estimates_positive_50ppm_clock_drift():
    sampling_rate = 4_000
    offset_sec = 1.7
    expected_drift_ppm = 50.0
    time_scale = 1.0 + expected_drift_ppm / 1_000_000.0
    main_duration_sec = 400.0
    aux_duration_sec = (main_duration_sec - offset_sec) / time_scale
    main = np.zeros(
        (int(main_duration_sec * sampling_rate), 2),
        dtype=np.float32,
    )
    aux = np.zeros(
        int(round(aux_duration_sec * sampling_rate)),
        dtype=np.float32,
    )

    for index, main_time in enumerate((5.0, 390.0)):
        aux_time = (main_time - offset_sec) / time_scale
        burst = _clap(sampling_rate, seed=index + 10)
        _add_burst(main[:, 0], main_time, burst, sampling_rate)
        _add_burst(main[:, 1], main_time, 0.7 * burst, sampling_rate)
        _add_burst(aux, aux_time, 0.5 * burst, sampling_rate)

    alignment = estimate_aux_alignment(
        main,
        aux,
        sampling_rate,
        window_sec=12.0,
    )

    assert alignment.method == "automatic_offset_and_drift"
    assert abs(alignment.offset_sec - offset_sec) <= 0.03
    assert abs(alignment.drift_ppm - expected_drift_ppm) <= 30.0
    mapped_end_clap = alignment.aux_to_main(
        (390.0 - offset_sec) / time_scale
    )
    assert abs(mapped_end_clap - 390.0) <= 0.03


class AllSpeechVoiceActivityDetector:
    def __init__(self, sample_count: int):
        self.sample_count = sample_count
        self.call_count = 0

    def __call__(self, waveform, sampling_rate):
        self.call_count += 1
        return [(0, self.sample_count)]


def _three_channel_conversation(
    sampling_rate: int,
    auxiliary_gain: float,
) -> np.ndarray:
    duration_sec = 5
    waveform = np.zeros((duration_sec * sampling_rate, 3), dtype=np.float32)
    microphone_gains = np.array([1.0, 1.0, auxiliary_gain])
    leakage_gain = 10.0 ** (-12.0 / 20.0)

    def add_speaker(start_sec: int, speaker: int, frequency: float) -> None:
        source = 0.4 * _tone(frequency, 1.0, sampling_rate)
        start = start_sec * sampling_rate
        end = start + sampling_rate
        for channel in range(3):
            pickup = 1.0 if channel == speaker else leakage_gain
            waveform[start:end, channel] += (
                source * microphone_gains[channel] * pickup
            )

    add_speaker(0, speaker=0, frequency=440.0)
    add_speaker(1, speaker=1, frequency=660.0)
    add_speaker(2, speaker=1, frequency=660.0)
    add_speaker(3, speaker=2, frequency=880.0)
    add_speaker(4, speaker=0, frequency=440.0)
    add_speaker(4, speaker=2, frequency=880.0)
    return waveform


def test_three_channel_gate_removes_leaks_and_retains_simultaneous_speech():
    sampling_rate = 16_000
    waveform = _three_channel_conversation(
        sampling_rate,
        auxiliary_gain=0.5,
    )
    detector = AllSpeechVoiceActivityDetector(len(waveform))

    result = gate_multichannel_waveform(
        waveform,
        sampling_rate,
        vad_detector=detector,
    )

    first_speaker = slice(int(0.2 * sampling_rate), int(0.8 * sampling_rate))
    auxiliary_speaker = slice(
        int(3.2 * sampling_rate),
        int(3.8 * sampling_rate),
    )
    simultaneous = slice(
        int(4.2 * sampling_rate),
        int(4.8 * sampling_rate),
    )

    assert detector.call_count == 3
    assert np.max(np.abs(result.waveform[first_speaker, 0])) > 0.35
    assert np.max(np.abs(result.waveform[first_speaker, 1:])) == 0.0
    assert np.max(np.abs(result.waveform[auxiliary_speaker, 2])) > 0.15
    assert np.max(np.abs(result.waveform[auxiliary_speaker, :2])) == 0.0
    assert np.max(np.abs(result.waveform[simultaneous, 0])) > 0.35
    assert np.max(np.abs(result.waveform[simultaneous, 2])) > 0.15
    assert np.max(np.abs(result.waveform[simultaneous, 1])) == 0.0


def test_gain_normalization_keeps_ownership_when_aux_gain_is_halved():
    sampling_rate = 16_000
    full_gain = _three_channel_conversation(sampling_rate, auxiliary_gain=1.0)
    half_gain = _three_channel_conversation(sampling_rate, auxiliary_gain=0.5)

    full_result = gate_multichannel_waveform(
        full_gain,
        sampling_rate,
        vad_detector=AllSpeechVoiceActivityDetector(len(full_gain)),
    )
    half_result = gate_multichannel_waveform(
        half_gain,
        sampling_rate,
        vad_detector=AllSpeechVoiceActivityDetector(len(half_gain)),
    )

    centers = np.array([0.5, 1.5, 2.5, 3.5, 4.5]) * sampling_rate
    center_samples = centers.astype(int)
    np.testing.assert_array_equal(
        full_result.keep_mask[center_samples],
        half_result.keep_mask[center_samples],
    )
    np.testing.assert_array_equal(
        half_result.keep_mask[center_samples],
        np.array(
            [
                [True, False, False],
                [False, True, False],
                [False, True, False],
                [False, False, True],
                [True, False, True],
            ]
        ),
    )


def test_three_channel_asr_is_mocked_per_kept_channel_and_timeline_shifted():
    sampling_rate = 16_000
    waveform = _three_channel_conversation(
        sampling_rate,
        auxiliary_gain=0.5,
    )
    segments = np.split(waveform, 5)

    class MockASR:
        def __init__(self):
            self.calls = 0

        def run(self, channel_waveform):
            self.calls += 1
            duration = len(channel_waveform) / sampling_rate
            return [(Segment(0.0, duration), f"utterance-{self.calls}")]

    asr = MockASR()
    output = transcribe_multichannel_segments(
        asr,
        SimpleNamespace(
            asr_model_name="openai",
            channel_crosstalk_threshold_db=-6.0,
        ),
        segments,
        sampling_rate,
        timeline_offset_sec=1.7,
        vad_detector=AllSpeechVoiceActivityDetector(len(waveform)),
    )

    assert asr.calls == 6
    assert [(round(item[0].start, 1), item[1]) for item in output] == [
        (1.7, "SPEAKER_00"),
        (2.7, "SPEAKER_01"),
        (3.7, "SPEAKER_01"),
        (4.7, "SPEAKER_02"),
        (5.7, "SPEAKER_00"),
        (5.7, "SPEAKER_02"),
    ]


def test_alignment_diagnostics_are_saved_in_transcript_json_meta(
    tmp_path,
    monkeypatch,
):
    audio_dir = tmp_path / "audios"
    audio_dir.mkdir()
    sf.write(
        audio_dir / "sample.wav",
        np.zeros(16_000, dtype=np.float32),
        16_000,
    )
    (tmp_path / "src/frontend/public/audios").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    metadata = {
        "channel_alignment": {
            "auxiliary_channels": [
                {
                    "offset_sec": 1.7,
                    "drift_ppm": 50.0,
                    "start_anchor": {"confidence": 0.9},
                    "end_anchor": {"confidence": 0.8},
                }
            ]
        }
    }
    save_transcripts_json(
        SimpleNamespace(audio_dir=str(audio_dir)),
        [(Segment(1.7, 2.7), "SPEAKER_02", "テスト")],
        "sample",
        metadata=metadata,
    )

    for path in (
        tmp_path / "src/frontend/public/transcripts/sample.json",
        tmp_path / "outputs/sample/sample.json",
    ):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["meta"] == metadata
        assert payload["transcripts"][0]["speaker"] == "SPEAKER_02"

    sf.write(
        audio_dir / "legacy.wav",
        np.zeros(16_000, dtype=np.float32),
        16_000,
    )
    save_transcripts_json(
        SimpleNamespace(audio_dir=str(audio_dir)),
        [(Segment(0.0, 1.0), "SPEAKER_00", "従来形式")],
        "legacy",
    )
    legacy_payload = json.loads(
        (
            tmp_path / "src/frontend/public/transcripts/legacy.json"
        ).read_text(encoding="utf-8")
    )
    assert isinstance(legacy_payload, list)
