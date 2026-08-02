from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

INTERVAL_LABELS = frozenset({"会話", "無言", "AI説明", "AI応答", "システム停止"})
EVENT_LABELS = frozenset(
    {
        "視覚障害者からの話題提示",
        "同行者からの話題提示",
        "視覚障害者から同行者への質問",
        "同行者から視覚障害者への質問",
        "AI情報の共有",
        "同行者からの周囲説明",
        "応答なし発話",
        "ガイド発話",
    }
)
SPEAKERS = frozenset({"視覚障害者", "同行者", "実験者"})
SOURCES = frozenset({"auto", "llm", "human"})
TAGS = frozenset({"周囲の話題"})
CO_LABELS = frozenset({"話題提示", "質問"})
RESPONSE_TYPES = frozenset({"自発", "質問応答"})
AI_REFERENCES = frozenset({"explicit", "within_30s"})


class CodingValidationError(ValueError):
    """Raised when a coding result does not conform to the Goal 3 schema."""

    def __init__(self, errors: Sequence[str]) -> None:
        """Store individual validation errors and create a readable message."""
        self.errors = list(errors)
        super().__init__("\n".join(self.errors))


def _is_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _require_keys(
    value: Mapping[str, Any],
    required: set[str],
    location: str,
    errors: list[str],
) -> None:
    for key in sorted(required - set(value)):
        errors.append(f"{location}: missing required key {key!r}")


def _validate_review(value: Any, location: str, errors: list[str]) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        errors.append(f"{location}.review must be an object")
        return
    status = value.get("status")
    if status not in {None, "confirmed", "needs_correction"}:
        errors.append(
            f"{location}.review.status must be null, 'confirmed', or 'needs_correction'"
        )
    if not isinstance(value.get("note", ""), str):
        errors.append(f"{location}.review.note must be a string")


def _validate_interval(
    item: Any,
    index: int,
    duration_sec: float | None,
    errors: list[str],
) -> tuple[float, float] | None:
    location = f"intervals[{index}]"
    if not isinstance(item, dict):
        errors.append(f"{location} must be an object")
        return None
    _require_keys(
        item,
        {"id", "label", "start", "end", "source", "note"},
        location,
        errors,
    )
    if not isinstance(item.get("id"), str) or not item.get("id"):
        errors.append(f"{location}.id must be a non-empty string")
    if item.get("label") not in INTERVAL_LABELS:
        errors.append(f"{location}.label is not an allowed interval label")
    if item.get("source") not in SOURCES:
        errors.append(f"{location}.source must be 'auto', 'llm' or 'human'")
    if not isinstance(item.get("note"), str):
        errors.append(f"{location}.note must be a string")

    start = item.get("start")
    end = item.get("end")
    if not _is_number(start):
        errors.append(f"{location}.start must be a finite number")
    if not _is_number(end):
        errors.append(f"{location}.end must be a finite number")
    if not (_is_number(start) and _is_number(end)):
        _validate_review(item.get("review"), location, errors)
        return None
    start_value = float(start)
    end_value = float(end)
    if start_value < 0:
        errors.append(f"{location}.start must be non-negative")
    if start_value >= end_value:
        errors.append(f"{location} must satisfy start < end")
    if duration_sec is not None and end_value > duration_sec + 1e-6:
        errors.append(f"{location}.end exceeds audio duration {duration_sec}")
    _validate_review(item.get("review"), location, errors)
    return start_value, end_value


def _validate_attrs(
    attrs: Any,
    label: Any,
    location: str,
    errors: list[str],
) -> None:
    if not isinstance(attrs, dict):
        errors.append(f"{location}.attrs must be an object")
        return
    co_labels = attrs.get("co_labels", [])
    if not isinstance(co_labels, list) or any(
        label_value not in CO_LABELS for label_value in co_labels
    ):
        errors.append(
            f"{location}.attrs.co_labels must contain only '話題提示' or '質問'"
        )
        co_labels = []
    if label == "AI情報の共有" and not (set(co_labels) & CO_LABELS):
        errors.append(
            f"{location}: AI情報の共有 requires 話題提示 or 質問 in attrs.co_labels"
        )
    response_type = attrs.get("response_type")
    if label == "同行者からの周囲説明" and response_type not in RESPONSE_TYPES:
        errors.append(
            f"{location}: 同行者からの周囲説明 requires "
            "attrs.response_type ('自発' or '質問応答')"
        )
    if response_type is not None and response_type not in RESPONSE_TYPES:
        errors.append(f"{location}.attrs.response_type has an invalid value")
    ai_reference = attrs.get("ai_reference")
    if ai_reference is not None and ai_reference not in AI_REFERENCES:
        errors.append(f"{location}.attrs.ai_reference has an invalid value")


def _validate_event(
    item: Any,
    index: int,
    duration_sec: float | None,
    errors: list[str],
) -> tuple[float, float] | None:
    location = f"events[{index}]"
    if not isinstance(item, dict):
        errors.append(f"{location} must be an object")
        return None
    _require_keys(
        item,
        {
            "id",
            "label",
            "time",
            "end",
            "speaker",
            "tags",
            "attrs",
            "text",
            "note",
        },
        location,
        errors,
    )
    if not isinstance(item.get("id"), str) or not item.get("id"):
        errors.append(f"{location}.id must be a non-empty string")
    label = item.get("label")
    if label not in EVENT_LABELS:
        errors.append(f"{location}.label is not an allowed event label")
    if item.get("speaker") not in SPEAKERS:
        errors.append(f"{location}.speaker is not an allowed speaker")
    if not isinstance(item.get("text"), str):
        errors.append(f"{location}.text must be a string")
    if not isinstance(item.get("note"), str):
        errors.append(f"{location}.note must be a string")
    tags = item.get("tags")
    if not isinstance(tags, list) or any(tag not in TAGS for tag in tags):
        errors.append(f"{location}.tags may contain only '周囲の話題'")
    _validate_attrs(item.get("attrs"), label, location, errors)
    # source はイベントでは任意(LLM 出力には無く、レビュー UI の手動追加が "human" を付ける)
    if "source" in item and item.get("source") not in SOURCES:
        errors.append(f"{location}.source must be 'auto', 'llm' or 'human'")

    start = item.get("time")
    end = item.get("end")
    if not _is_number(start):
        errors.append(f"{location}.time must be a finite number")
    if not _is_number(end):
        errors.append(f"{location}.end must be a finite number")
    if not (_is_number(start) and _is_number(end)):
        _validate_review(item.get("review"), location, errors)
        return None
    start_value = float(start)
    end_value = float(end)
    if start_value < 0:
        errors.append(f"{location}.time must be non-negative")
    if start_value >= end_value:
        errors.append(f"{location} must satisfy time < end")
    if duration_sec is not None and end_value > duration_sec + 1e-6:
        errors.append(f"{location}.end exceeds audio duration {duration_sec}")
    _validate_review(item.get("review"), location, errors)
    return start_value, end_value


def validate_coding_data(
    data: Any,
    *,
    duration_sec: float | None = None,
) -> list[str]:
    """Return all schema and semantic validation errors."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["root must be an object"]
    _require_keys(data, {"version", "audio", "intervals", "events"}, "root", errors)
    if data.get("version") != 1:
        errors.append("version must be 1")
    if not isinstance(data.get("audio"), str) or not data.get("audio"):
        errors.append("audio must be a non-empty string")

    intervals = data.get("intervals")
    events = data.get("events")
    if not isinstance(intervals, list):
        errors.append("intervals must be an array")
        intervals = []
    if not isinstance(events, list):
        errors.append("events must be an array")
        events = []

    interval_times = [
        result
        for index, item in enumerate(intervals)
        if (result := _validate_interval(item, index, duration_sec, errors)) is not None
    ]
    event_times = [
        result
        for index, item in enumerate(events)
        if (result := _validate_event(item, index, duration_sec, errors)) is not None
    ]

    if interval_times != sorted(interval_times):
        errors.append("intervals must be monotonically ordered by (start, end)")
    if event_times != sorted(event_times):
        errors.append("events must be monotonically ordered by (time, end)")

    ids = [
        item.get("id")
        for item in [*intervals, *events]
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    ]
    if len(ids) != len(set(ids)):
        errors.append("all interval/event ids must be unique")
    return errors


def validate_coding_result(
    data: Any,
    *,
    duration_sec: float | None = None,
) -> None:
    """Raise ``CodingValidationError`` unless the result is valid."""
    errors = validate_coding_data(data, duration_sec=duration_sec)
    if errors:
        raise CodingValidationError(errors)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate a conversation coding JSON.")
    parser.add_argument("coding_json")
    parser.add_argument("--duration", type=float)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the coding-result validation CLI."""
    args = _build_parser().parse_args(argv)
    path = Path(args.coding_json)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        validate_coding_result(data, duration_sec=args.duration)
    except (OSError, json.JSONDecodeError, CodingValidationError) as exc:
        print(f"Validation failed for {path}:\n{exc}")
        return 1
    print(f"Validation succeeded: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
