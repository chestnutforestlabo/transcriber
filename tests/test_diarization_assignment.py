from types import SimpleNamespace

import numpy as np
from pyannote.core import Annotation, Segment
from utils import add_speaker_info_to_text, diarize_text


def _annotation(*turns):
    annotation = Annotation()
    for start, end, speaker in turns:
        annotation[Segment(start, end)] = speaker
    return annotation


def test_word_timestamps_split_asr_segment_at_speaker_change():
    waveform = np.zeros(4 * 16_000, dtype=np.float32)
    duration = len(waveform) / 16_000
    annotation = _annotation(
        (0.0, 2.0, "SPEAKER_00"),
        (2.0, duration, "SPEAKER_01"),
    )
    asr_output = [
        (
            Segment(0.0, duration),
            "今日はよろしくお願いします",
            [
                (Segment(0.1, 0.8), "今日は"),
                (Segment(0.8, 1.7), "よろしく"),
                (Segment(2.1, 3.0), "お願い"),
                (Segment(3.0, 3.8), "します"),
            ],
        )
    ]

    output = diarize_text(SimpleNamespace(), asr_output, annotation)

    assert len(output) == 2
    assert output[0][1:] == ("SPEAKER_00", "今日はよろしく")
    assert output[1][1:] == ("SPEAKER_01", "お願いします")
    assert output[0][0] == Segment(0.1, 1.7)
    assert output[1][0] == Segment(2.1, 3.8)


def test_short_backchannel_surrounded_by_main_speaker_is_not_split():
    annotation = _annotation(
        (0.0, 1.2, "SPEAKER_00"),
        (1.2, 1.6, "SPEAKER_01"),
        (1.6, 3.0, "SPEAKER_00"),
    )
    segment = Segment(0.0, 3.0)
    asr_output = [
        (
            segment,
            "ありがとうございます",
            [
                (Segment(0.2, 1.0), "ありがとう"),
                (Segment(1.25, 1.5), "うん"),
                (Segment(1.7, 2.7), "ございます"),
            ],
        )
    ]

    output = add_speaker_info_to_text(asr_output, annotation)

    assert output == [(segment, "SPEAKER_00", "ありがとうございます")]


def test_legacy_asr_without_words_falls_back_to_majority_speaker():
    segment = Segment(0.0, 4.0)
    annotation = _annotation(
        (0.0, 3.0, "SPEAKER_00"),
        (3.0, 4.0, "SPEAKER_01"),
    )

    output = add_speaker_info_to_text(
        [(segment, "単語タイムスタンプなし")],
        annotation,
    )

    assert output == [(segment, "SPEAKER_00", "単語タイムスタンプなし")]


def test_speaker_ratio_threshold_enables_split_below_duration_threshold():
    segment = Segment(0.0, 1.0)
    annotation = _annotation(
        (0.0, 0.6, "SPEAKER_00"),
        (0.6, 1.0, "SPEAKER_01"),
    )
    asr_output = [
        (
            segment,
            "はい了解",
            [
                {"start": 0.1, "end": 0.55, "word": "はい"},
                {"start": 0.65, "end": 0.95, "word": "了解"},
            ],
        )
    ]

    output = add_speaker_info_to_text(asr_output, annotation)

    assert [item[1] for item in output] == ["SPEAKER_00", "SPEAKER_01"]
    assert [item[2] for item in output] == ["はい", "了解"]
