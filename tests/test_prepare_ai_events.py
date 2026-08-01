import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from coding.prepare_ai_events import (
    discard_frames_from_line,
    prepare_ai_events,
    read_merged_events,
)


def _write_audio(path: Path, duration: float = 60.0) -> None:
    sf.write(path, np.zeros(int(duration * 8_000), dtype=np.float32), 8_000)


def _write_log(path: Path, events, *, version: int | None = 2) -> None:
    with path.open("w", encoding="utf-8") as stream:
        if version is not None:
            stream.write(
                json.dumps(
                    {"event": "log_meta", "schema_version": version},
                    ensure_ascii=False,
                )
                + "\n"
            )
        for event in events:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")


def test_timezone_and_sync_anchor_are_converted_to_audio_seconds(tmp_path):
    """JST absolute time and a protocol anchor produce the same UTC mapping."""
    audio = tmp_path / "walk.wav"
    log = tmp_path / "app.jsonl"
    _write_audio(audio)
    _write_log(
        log,
        [
            {"event": "experiment_start", "at": "2026-07-23T05:00:00Z"},
            {
                "event": "speech_start",
                "at": "2026-07-23T05:00:10Z",
                "id": "speech-1",
                "kind": "scene",
                "text": "石垣があります",
            },
            {
                "event": "speech_end",
                "at": "2026-07-23T05:00:14Z",
                "id": "speech-1",
                "reason": "finished",
            },
            {"event": "experiment_end", "at": "2026-07-23T05:00:40Z"},
        ],
    )

    anchored = prepare_ai_events(
        [log],
        audio,
        sync="audio=2.5,log=experiment_start",
    )
    absolute = prepare_ai_events(
        [log],
        audio,
        recording_start="2026-07-23T14:00:00+09:00",
    )

    assert anchored["meta"]["experiment"] == {"start": 2.5, "end": 42.5}
    assert anchored["ai_utterances"][0]["start"] == 12.5
    assert anchored["ai_utterances"][0]["end"] == 16.5
    assert absolute["meta"]["experiment"] == {"start": 0.0, "end": 40.0}
    assert absolute["ai_utterances"][0]["start"] == 10.0


def test_system_stops_are_clipped_and_include_stopped_at_experiment_start(
    tmp_path,
):
    """Only user stops overlapping the experiment bracket are emitted."""
    audio = tmp_path / "walk.wav"
    log = tmp_path / "app.jsonl"
    _write_audio(audio, 45.0)
    _write_log(
        log,
        [
            {
                "event": "session_stop",
                "at": "2026-07-23T04:59:55Z",
                "reason": "user",
            },
            {"event": "experiment_start", "at": "2026-07-23T05:00:00Z"},
            {
                "event": "session_start",
                "at": "2026-07-23T05:00:05Z",
                "prompt_mode": "atmosphere",
            },
            {
                "event": "session_stop",
                "at": "2026-07-23T05:00:10Z",
                "reason": "user",
            },
            {
                "event": "session_start",
                "at": "2026-07-23T05:00:20Z",
                "prompt_mode": "atmosphere",
            },
            {"event": "experiment_end", "at": "2026-07-23T05:00:30Z"},
            {
                "event": "session_stop",
                "at": "2026-07-23T05:00:35Z",
                "reason": "user",
            },
        ],
    )

    result = prepare_ai_events(
        [log],
        audio,
        sync="audio=0,log=experiment_start",
    )

    assert result["system_stops"] == [
        {"start": 0.0, "end": 5.0},
        {"start": 10.0, "end": 20.0},
    ]


def test_v2_pairs_cancelled_speech_and_never_estimates(tmp_path):
    """V2 emits only exact start/end pairs, including cancelled speech."""
    audio = tmp_path / "walk.wav"
    log = tmp_path / "app.jsonl"
    _write_audio(audio)
    _write_log(
        log,
        [
            {"event": "experiment_start", "at": "2026-07-23T05:00:00Z"},
            {
                "event": "speech_start",
                "at": "2026-07-23T05:00:02Z",
                "id": "paired",
                "kind": "deepdive",
                "text": "詳しい説明",
            },
            {
                "event": "speech_start",
                "at": "2026-07-23T05:00:03Z",
                "id": "unpaired",
                "kind": "scene",
                "text": "終了なし",
            },
            {
                "event": "speech_end",
                "at": "2026-07-23T05:00:04Z",
                "id": "paired",
                "reason": "cancelled",
            },
            {"event": "experiment_end", "at": "2026-07-23T05:00:10Z"},
        ],
    )

    result = prepare_ai_events(
        [log],
        audio,
        sync="audio=0,log=experiment_start",
    )

    assert result["ai_utterances"] == [
        {
            "start": 2.0,
            "end": 4.0,
            "kind": "deepdive",
            "text": "詳しい説明",
            "end_reason": "cancelled",
            "estimated_end": False,
        }
    ]


def test_yields_qa_and_prompt_modes_are_correlated_inside_bracket(tmp_path):
    """QA answer starts after qa_result and yield pairs remain correlated."""
    audio = tmp_path / "walk.wav"
    log = tmp_path / "app.jsonl"
    _write_audio(audio, 20.0)
    _write_log(
        log,
        [
            {
                "event": "session_start",
                "at": "2026-07-23T04:59:59Z",
                "prompt_mode": "atmosphere",
            },
            {"event": "experiment_start", "at": "2026-07-23T05:00:00Z"},
            {"event": "qa_start", "at": "2026-07-23T05:00:01Z", "topics": []},
            {"event": "qa_heard", "at": "2026-07-23T05:00:02Z"},
            {
                "event": "qa_vlm_request",
                "at": "2026-07-23T05:00:03Z",
                "question": "門は何色？",
            },
            {
                "event": "qa_vlm_response",
                "at": "2026-07-23T05:00:04Z",
                "speech_output": "赤色です",
            },
            {"event": "qa_result", "at": "2026-07-23T05:00:04.1Z"},
            {"event": "speech_yield", "at": "2026-07-23T05:00:04.15Z", "active": True},
            {"event": "speech_yield", "at": "2026-07-23T05:00:04.2Z", "active": False},
            {
                "event": "speech_start",
                "at": "2026-07-23T05:00:04.3Z",
                "id": "answer",
                "kind": "qa_answer",
                "text": "赤色です",
            },
            {
                "event": "speech_end",
                "at": "2026-07-23T05:00:05Z",
                "id": "answer",
                "reason": "finished",
            },
            {"event": "experiment_end", "at": "2026-07-23T05:00:10Z"},
        ],
    )

    result = prepare_ai_events(
        [log],
        audio,
        sync="audio=0,log=experiment_start",
    )

    assert result["qa_interactions"] == [
        {
            "qa_start": 1.0,
            "question_heard": 2.0,
            "question": "門は何色？",
            "answer_start": 4.3,
            "answer_text": "赤色です",
        }
    ]
    assert result["speech_yields"] == [{"start": 4.15, "end": 4.2}]
    assert result["prompt_modes"] == [{"time": 0.0, "mode": "atmosphere"}]


def test_legacy_estimation_requires_explicit_flag(tmp_path):
    """Legacy response matching and duration estimation require --legacy."""
    audio = tmp_path / "pilot.wav"
    log = tmp_path / "pilot.jsonl"
    _write_audio(audio, 10.0)
    _write_log(
        log,
        [
            {
                "event": "live_vlm_response",
                "at": "2026-07-23T05:00:01Z",
                "raw_output": {"new_information": [{"text": "六文字です！"}]},
            },
            {"event": "speech_start", "at": "2026-07-23T05:00:01.5Z"},
        ],
        version=None,
    )

    with pytest.raises(ValueError, match="schema v2"):
        prepare_ai_events(
            [log],
            audio,
            recording_start="2026-07-23T05:00:00Z",
        )

    result = prepare_ai_events(
        [log],
        audio,
        recording_start="2026-07-23T05:00:00Z",
        legacy=True,
    )

    assert len(result["ai_utterances"]) == 1
    assert result["ai_utterances"][0]["estimated_end"] is True
    assert result["ai_utterances"][0]["kind"] == "scene"


def test_frames_are_discarded_before_event_decoding_and_files_are_merged(tmp_path):
    """Large frame values are skipped while compact events merge by time."""
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    huge_frame = 'abc],\\"still-string\\":true' * 2_000
    _write_log(
        first,
        [
            {
                "event": "live_vlm_request",
                "at": "2026-07-23T05:00:02Z",
                "frames": [huge_frame],
                "request_id": "later",
            }
        ],
    )
    _write_log(
        second,
        [
            {
                "event": "scene_request",
                "at": "2026-07-23T05:00:01Z",
                "frames": [huge_frame],
                "request_id": "earlier",
            }
        ],
    )

    events = read_merged_events([first, second])
    cleaned = discard_frames_from_line(
        '{"event":"x","frames":["[not nesting]"],"kept":1}\n'
    )

    assert [event["request_id"] for event in events] == ["earlier", "later"]
    assert all("frames" not in event for event in events)
    assert json.loads(cleaned) == {"event": "x", "frames": None, "kept": 1}


def test_v2_without_bracket_falls_back_to_recording_window(tmp_path, capsys):
    """押し忘れ対応: v2 ログにブラケットが無くても録音窓で処理できる。"""
    audio = tmp_path / "walk.wav"
    log = tmp_path / "app.jsonl"
    _write_audio(audio, duration=60.0)
    _write_log(
        log,
        [
            {
                "event": "speech_start",
                "at": "2026-07-31T09:00:02Z",
                "id": "s1",
                "kind": "scene",
                "text": "右に赤い看板",
            },
            {
                "event": "speech_end",
                "at": "2026-07-31T09:00:04Z",
                "id": "s1",
                "reason": "finished",
            },
        ],
    )

    result = prepare_ai_events(
        [log],
        audio,
        recording_start="2026-07-31T18:00:00+09:00",
    )

    assert result["meta"]["experiment"] == {"start": 0.0, "end": 60.0}
    assert result["ai_utterances"] == [
        {
            "start": 2.0,
            "end": 4.0,
            "kind": "scene",
            "text": "右に赤い看板",
            "end_reason": "finished",
            "estimated_end": False,
        }
    ]


def test_sidecar_time_json_is_discovered_automatically(tmp_path, capsys):
    """record_mac_dji.sh の sidecar があれば --sync/--recording_start 不要。"""
    audio = tmp_path / "rec_20260731_180000.wav"
    log = tmp_path / "app.jsonl"
    _write_audio(audio, duration=60.0)
    (tmp_path / "rec_20260731_180000.time.json").write_text(
        '{"recording_start": "2026-07-31T18:00:00+09:00"}\n', encoding="utf-8"
    )
    _write_log(
        log,
        [
            {
                "event": "speech_start",
                "at": "2026-07-31T09:00:05Z",
                "id": "s1",
                "kind": "scene",
                "text": "左に横断歩道",
            },
            {
                "event": "speech_end",
                "at": "2026-07-31T09:00:07Z",
                "id": "s1",
                "reason": "finished",
            },
        ],
    )

    result = prepare_ai_events([log], audio)

    assert result["ai_utterances"][0]["start"] == 5.0
    assert result["ai_utterances"][0]["end"] == 7.0
