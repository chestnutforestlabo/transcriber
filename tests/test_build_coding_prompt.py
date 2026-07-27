import json
from pathlib import Path

from coding.build_coding_prompt import (
    build_human_interval_candidates,
    build_scaffold,
    merge_chunk_results,
    write_prompts,
)


def test_three_second_gap_scaffold_builds_conversation_and_silence_candidates():
    """A three-second break separates candidate conversation groups."""
    transcript = [
        {"start": 2.0, "end": 3.0, "speaker": "視覚障害者", "text": "ねえ"},
        {"start": 4.0, "end": 5.0, "speaker": "同行者", "text": "はい"},
        # Exactly three seconds starts a new candidate group.
        {"start": 8.0, "end": 9.0, "speaker": "視覚障害者", "text": "次は"},
        {"start": 9.5, "end": 10.0, "speaker": "同行者", "text": "うん"},
    ]

    candidates = build_human_interval_candidates(transcript, 15.0)

    assert [(item["label"], item["start"], item["end"]) for item in candidates] == [
        ("無言", 0.0, 2.0),
        ("会話", 2.0, 8.0),
        ("会話", 8.0, 13.0),
        ("無言", 13.0, 15.0),
    ]


def test_scaffold_maps_only_codable_ai_kinds_and_system_stops():
    """System and filler utterances remain context rather than coded intervals."""
    transcript = []
    ai_events = {
        "meta": {
            "duration_sec": 20.0,
            "experiment": {"start": 0.0, "end": 20.0},
        },
        "ai_utterances": [
            {"start": 1.0, "end": 2.0, "kind": "scene"},
            {"start": 3.0, "end": 4.0, "kind": "qa_answer"},
            {"start": 5.0, "end": 6.0, "kind": "deepdive"},
            {"start": 7.0, "end": 8.0, "kind": "tsunagi"},
            {"start": 9.0, "end": 10.0, "kind": "system"},
        ],
        "system_stops": [{"start": 12.0, "end": 14.0}],
    }

    scaffold = build_scaffold(transcript, ai_events)
    labels = [item["label"] for item in scaffold["intervals"]]

    assert labels.count("AI説明") == 1
    assert labels.count("AI応答") == 2
    assert labels.count("システム停止") == 1
    assert "会話" not in labels
    assert labels.count("無言") == 1


def test_chunk_prompts_use_sixty_second_overlap_and_merge_by_core(tmp_path):
    """Chunk overlap informs boundaries while each core contributes once."""
    transcript_path = tmp_path / "walk.json"
    ai_events_path = tmp_path / "ai_events.json"
    prompt_path = tmp_path / "coding_prompt.txt"
    transcript_path.write_text(
        json.dumps(
            [
                {
                    "start": 110.0,
                    "end": 130.0,
                    "speaker": "SPEAKER_00",
                    "text": "境界をまたぐ発話",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    ai_events_path.write_text(
        json.dumps(
            {
                "meta": {
                    "duration_sec": 240.0,
                    "experiment": {"start": 0.0, "end": 240.0},
                },
                "ai_utterances": [],
                "speech_yields": [],
                "qa_interactions": [],
                "system_stops": [],
                "prompt_modes": [],
            }
        ),
        encoding="utf-8",
    )

    manifest_path = write_prompts(
        transcript_path=transcript_path,
        ai_events_path=ai_events_path,
        speaker_roles={"SPEAKER_00": "視覚障害者"},
        output_path=prompt_path,
        chunk_minutes=2.0,
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert [
        (chunk["window_start"], chunk["window_end"]) for chunk in manifest["chunks"]
    ] == [(0.0, 150.0), (90.0, 240.0)]

    for index, chunk in enumerate(manifest["chunks"], start=1):
        result = {
            "version": 1,
            "audio": "walk.wav",
            "intervals": [
                {
                    "id": f"iv-{index:04d}",
                    "label": "会話",
                    "start": 110.0,
                    "end": 130.0,
                    "source": "llm",
                    "note": "",
                }
            ],
            "events": [],
        }
        if index == 1:
            result["events"].append(
                {
                    "id": "ev-0001",
                    "label": "応答なし発話",
                    "time": 119.0,
                    "end": 119.5,
                    "speaker": "視覚障害者",
                    "tags": [],
                    "attrs": {"co_labels": []},
                    "text": "ねえ",
                    "note": "",
                }
            )
        Path(chunk["result"]).write_text(
            json.dumps(result, ensure_ascii=False),
            encoding="utf-8",
        )

    merged_path = tmp_path / "coding.json"
    merged = merge_chunk_results(manifest_path, merged_path)

    assert [
        (item["label"], item["start"], item["end"]) for item in merged["intervals"]
    ] == [("会話", 110.0, 130.0)]
    assert [event["time"] for event in merged["events"]] == [119.0]
