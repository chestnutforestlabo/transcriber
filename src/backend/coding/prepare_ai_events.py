from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence

import soundfile as sf

LEGACY_CHARACTERS_PER_SECOND = 6.5
LEGACY_RESPONSE_MATCH_SEC = 1.0


@dataclass(frozen=True)
class SyncAnchor:
    """Mapping between one log timestamp and the audio timeline."""

    audio_sec: float
    log_time: datetime
    description: str

    def to_audio_sec(self, value: datetime) -> float:
        """Convert an absolute log timestamp to audio-relative seconds."""
        return self.audio_sec + (value - self.log_time).total_seconds()


def parse_iso8601(value: str) -> datetime:
    """Parse an ISO8601 timestamp and normalize it to UTC."""
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    fractional = re.fullmatch(
        r"(.*:\d{2})\.(\d+)([+-]\d{2}:\d{2})",
        normalized,
    )
    if fractional is not None:
        digits = (fractional.group(2) + "000000")[:6]
        normalized = f"{fractional.group(1)}.{digits}{fractional.group(3)}"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"Invalid ISO8601 timestamp: {value}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"Timestamp must include a timezone: {value}")
    return parsed.astimezone(timezone.utc)


def _scan_json_string(text: str, start: int) -> int:
    index = start + 1
    while index < len(text):
        if text[index] == "\\":
            index += 2
            continue
        if text[index] == '"':
            return index + 1
        index += 1
    raise ValueError("Unterminated JSON string")


def _scan_json_value(text: str, start: int) -> int:
    if start >= len(text):
        raise ValueError("Missing JSON value")
    if text[start] == '"':
        return _scan_json_string(text, start)
    if text[start] not in "[{":
        index = start
        while index < len(text) and text[index] not in ",}]":
            index += 1
        return index

    stack = [text[start]]
    index = start + 1
    while index < len(text) and stack:
        char = text[index]
        if char == '"':
            index = _scan_json_string(text, index)
            continue
        if char in "[{":
            stack.append(char)
        elif char in "]}":
            expected = "[" if char == "]" else "{"
            if stack[-1] != expected:
                raise ValueError("Malformed JSON nesting")
            stack.pop()
        index += 1
    if stack:
        raise ValueError("Unterminated JSON value")
    return index


def discard_frames_from_line(line: str) -> str:
    """Replace any ``frames`` value before JSON decoding its base64 payload."""
    pieces: list[str] = []
    cursor = 0
    index = 0
    while index < len(line):
        if line[index] != '"':
            index += 1
            continue
        string_end = _scan_json_string(line, index)
        key_end = string_end
        while key_end < len(line) and line[key_end].isspace():
            key_end += 1
        if key_end >= len(line) or line[key_end] != ":":
            index = string_end
            continue
        try:
            key = json.loads(line[index:string_end])
        except json.JSONDecodeError:
            index = string_end
            continue
        if key != "frames":
            index = string_end
            continue

        value_start = key_end + 1
        while value_start < len(line) and line[value_start].isspace():
            value_start += 1
        value_end = _scan_json_value(line, value_start)
        pieces.append(line[cursor:value_start])
        pieces.append("null")
        cursor = value_end
        index = value_end

    if not pieces:
        return line
    pieces.append(line[cursor:])
    return "".join(pieces)


def _event_name(event: dict[str, Any]) -> str:
    for key in ("event", "type", "name"):
        value = event.get(key)
        if isinstance(value, str):
            return value
    return ""


def _read_log_file(path: Path) -> tuple[list[dict[str, Any]], int | None]:
    events: list[dict[str, Any]] = []
    schema_version: int | None = None
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                event = json.loads(discard_frames_from_line(line))
            except (json.JSONDecodeError, ValueError) as exc:
                raise ValueError(
                    f"{path}:{line_number}: invalid JSONL event: {exc}"
                ) from exc
            if not isinstance(event, dict):
                raise ValueError(
                    f"{path}:{line_number}: each JSONL line must be an object"
                )
            event.pop("frames", None)
            if _event_name(event) == "log_meta":
                raw_version = event.get("schema_version")
                if isinstance(raw_version, int):
                    schema_version = raw_version
                continue
            at = event.get("at")
            if not isinstance(at, str):
                continue
            event["_at"] = parse_iso8601(at)
            event["_source_file"] = str(path)
            event["_source_line"] = line_number
            events.append(event)
    return events, schema_version


def read_merged_events(
    log_files: Sequence[str | Path],
    *,
    legacy: bool = False,
) -> list[dict[str, Any]]:
    """Read JSONL files line-by-line, discard frames, and merge by UTC time."""
    merged: list[dict[str, Any]] = []
    for raw_path in log_files:
        path = Path(raw_path)
        events, schema_version = _read_log_file(path)
        if not legacy and schema_version != 2:
            raise ValueError(
                f"{path}: schema v2 log_meta is required; use --legacy only for v1 logs"
            )
        merged.extend(events)
    merged.sort(
        key=lambda event: (
            event["_at"],
            str(event["_source_file"]),
            int(event["_source_line"]),
        )
    )
    return merged


def parse_sync_spec(value: str) -> tuple[float, str]:
    """Parse ``audio=<seconds>,log=<event-name>``."""
    fields: dict[str, str] = {}
    for part in value.split(","):
        key, separator, field_value = part.partition("=")
        if not separator:
            raise ValueError("--sync must be audio=<seconds>,log=<event-name>")
        fields[key.strip()] = field_value.strip()
    if set(fields) != {"audio", "log"} or not fields["log"]:
        raise ValueError("--sync must be audio=<seconds>,log=<event-name>")
    try:
        audio_sec = float(fields["audio"])
    except ValueError as exc:
        raise ValueError("--sync audio value must be a number") from exc
    if not math.isfinite(audio_sec) or audio_sec < 0:
        raise ValueError("--sync audio value must be a non-negative finite number")
    return audio_sec, fields["log"]


def _resolve_anchor(
    events: Sequence[dict[str, Any]],
    *,
    sync: str | None,
    recording_start: str | None,
) -> tuple[SyncAnchor, dict[str, Any] | None]:
    if bool(sync) == bool(recording_start):
        raise ValueError("Specify exactly one of --sync or --recording_start")
    if recording_start:
        log_time = parse_iso8601(recording_start)
        return (
            SyncAnchor(0.0, log_time, f"recording_start={recording_start}"),
            None,
        )

    audio_sec, log_event_name = parse_sync_spec(sync or "")
    anchor_event = next(
        (event for event in events if _event_name(event) == log_event_name),
        None,
    )
    if anchor_event is None:
        raise ValueError(f"--sync log event was not found: {log_event_name}")
    return (
        SyncAnchor(
            audio_sec,
            anchor_event["_at"],
            f"audio={audio_sec},log={log_event_name}",
        ),
        anchor_event,
    )


def _clip_interval(
    start: float,
    end: float,
    lower: float,
    upper: float,
) -> tuple[float, float] | None:
    clipped_start = max(start, lower)
    clipped_end = min(end, upper)
    if clipped_start >= clipped_end:
        return None
    return clipped_start, clipped_end


def _experiment_window(
    events: Sequence[dict[str, Any]],
    anchor: SyncAnchor,
    anchor_event: dict[str, Any] | None,
    duration_sec: float,
    *,
    legacy: bool,
) -> tuple[datetime, datetime, float, float]:
    if legacy:
        return (
            anchor.log_time,
            anchor.log_time + timedelta(seconds=duration_sec),
            0.0,
            duration_sec,
        )

    starts = [event for event in events if _event_name(event) == "experiment_start"]
    ends = [event for event in events if _event_name(event) == "experiment_end"]
    if not starts or not ends:
        raise ValueError("schema v2 logs require experiment_start and experiment_end")

    if anchor_event is not None and _event_name(anchor_event) == "experiment_start":
        start_event = anchor_event
    else:
        candidates = [
            event
            for event in starts
            if -duration_sec <= anchor.to_audio_sec(event["_at"]) <= duration_sec * 2
        ]
        start_event = candidates[0] if candidates else starts[0]
    end_event = next(
        (event for event in ends if event["_at"] > start_event["_at"]),
        None,
    )
    if end_event is None:
        raise ValueError("experiment_start has no later experiment_end")

    raw_start = anchor.to_audio_sec(start_event["_at"])
    raw_end = anchor.to_audio_sec(end_event["_at"])
    clipped = _clip_interval(raw_start, raw_end, 0.0, duration_sec)
    if clipped is None:
        raise ValueError("experiment bracket does not overlap the audio duration")
    return start_event["_at"], end_event["_at"], clipped[0], clipped[1]


def _extract_live_text(event: dict[str, Any]) -> str:
    raw_output = event.get("raw_output")
    if isinstance(raw_output, str):
        try:
            raw_output = json.loads(raw_output)
        except json.JSONDecodeError:
            return raw_output.strip()
    if not isinstance(raw_output, dict):
        return ""
    information = raw_output.get("new_information")
    if not isinstance(information, list):
        return ""
    texts = [
        str(item.get("text", "")).strip()
        for item in information
        if isinstance(item, dict) and item.get("text")
    ]
    return "\n".join(texts)


def _legacy_ai_utterances(
    events: Sequence[dict[str, Any]],
    anchor: SyncAnchor,
    lower: float,
    upper: float,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    utterances: list[dict[str, Any]] = []
    for event in events:
        name = _event_name(event)
        if name == "live_vlm_response":
            text = _extract_live_text(event)
            if text:
                candidates.append({"at": event["_at"], "text": text, "kind": "scene"})
            continue
        if name == "qa_vlm_response":
            text = str(event.get("speech_output", "")).strip()
            if text:
                candidates.append(
                    {"at": event["_at"], "text": text, "kind": "qa_answer"}
                )
            continue
        if name != "speech_start":
            continue

        text = str(event.get("text", "")).strip()
        kind = str(event.get("kind", "")).strip()
        if not text:
            match_index = next(
                (
                    index
                    for index in range(len(candidates) - 1, -1, -1)
                    if 0.0
                    <= (event["_at"] - candidates[index]["at"]).total_seconds()
                    <= LEGACY_RESPONSE_MATCH_SEC
                ),
                None,
            )
            if match_index is not None:
                matched = candidates.pop(match_index)
                text = matched["text"]
                kind = kind or matched["kind"]
        if not text:
            continue
        kind = kind or "system"
        start = anchor.to_audio_sec(event["_at"])
        end = start + len(text) / LEGACY_CHARACTERS_PER_SECOND
        clipped = _clip_interval(start, end, lower, upper)
        if clipped is None:
            continue
        utterances.append(
            {
                "start": clipped[0],
                "end": clipped[1],
                "kind": kind,
                "text": text,
                "end_reason": "estimated",
                "estimated_end": True,
            }
        )
    return utterances


def _v2_ai_utterances(
    events: Sequence[dict[str, Any]],
    anchor: SyncAnchor,
    lower: float,
    upper: float,
) -> list[dict[str, Any]]:
    active: dict[str, dict[str, Any]] = {}
    utterances: list[dict[str, Any]] = []
    for event in events:
        name = _event_name(event)
        speech_id = event.get("id")
        if name == "speech_start" and isinstance(speech_id, str):
            active[speech_id] = event
        elif name == "speech_end" and isinstance(speech_id, str):
            start_event = active.pop(speech_id, None)
            if start_event is None or event["_at"] <= start_event["_at"]:
                continue
            start = anchor.to_audio_sec(start_event["_at"])
            end = anchor.to_audio_sec(event["_at"])
            clipped = _clip_interval(start, end, lower, upper)
            if clipped is None:
                continue
            utterances.append(
                {
                    "start": clipped[0],
                    "end": clipped[1],
                    "kind": str(start_event.get("kind", "system")),
                    "text": str(start_event.get("text", "")),
                    "end_reason": str(event.get("reason", "finished")),
                    "estimated_end": False,
                }
            )
    return utterances


def _speech_yields(
    events: Sequence[dict[str, Any]],
    anchor: SyncAnchor,
    lower: float,
    upper: float,
) -> list[dict[str, float]]:
    active_at: datetime | None = None
    intervals: list[dict[str, float]] = []
    for event in events:
        if _event_name(event) != "speech_yield":
            continue
        if event.get("active") is True and active_at is None:
            active_at = event["_at"]
        elif event.get("active") is False and active_at is not None:
            clipped = _clip_interval(
                anchor.to_audio_sec(active_at),
                anchor.to_audio_sec(event["_at"]),
                lower,
                upper,
            )
            if clipped is not None:
                intervals.append({"start": clipped[0], "end": clipped[1]})
            active_at = None
    if active_at is not None:
        clipped = _clip_interval(
            anchor.to_audio_sec(active_at),
            upper,
            lower,
            upper,
        )
        if clipped is not None:
            intervals.append({"start": clipped[0], "end": clipped[1]})
    return intervals


def _system_stops(
    events: Sequence[dict[str, Any]],
    anchor: SyncAnchor,
    lower: float,
    upper: float,
) -> list[dict[str, float]]:
    stopped_at: datetime | None = None
    intervals: list[dict[str, float]] = []
    for event in events:
        name = _event_name(event)
        if name == "session_stop" and event.get("reason") == "user":
            if stopped_at is None:
                stopped_at = event["_at"]
        elif name == "session_start" and stopped_at is not None:
            clipped = _clip_interval(
                anchor.to_audio_sec(stopped_at),
                anchor.to_audio_sec(event["_at"]),
                lower,
                upper,
            )
            if clipped is not None:
                intervals.append({"start": clipped[0], "end": clipped[1]})
            stopped_at = None
    if stopped_at is not None:
        clipped = _clip_interval(
            anchor.to_audio_sec(stopped_at),
            upper,
            lower,
            upper,
        )
        if clipped is not None:
            intervals.append({"start": clipped[0], "end": clipped[1]})
    return intervals


def _qa_interactions(
    events: Sequence[dict[str, Any]],
    anchor: SyncAnchor,
    lower: float,
    upper: float,
) -> list[dict[str, Any]]:
    pending: dict[str, Any] | None = None
    completed: list[dict[str, Any]] = []
    for event in events:
        name = _event_name(event)
        if name == "qa_start":
            if pending is not None:
                completed.append(pending)
            pending = {"qa_start_at": event["_at"]}
        elif pending is None:
            continue
        elif name == "qa_heard":
            pending["question_heard_at"] = event["_at"]
        elif name == "qa_vlm_request":
            pending["question"] = str(event.get("question", ""))
        elif name == "qa_vlm_response":
            pending["answer_text"] = str(event.get("speech_output", ""))
        elif (
            name == "speech_start"
            and event.get("kind") in {"qa_answer", "deepdive"}
            and "answer_start_at" not in pending
        ):
            pending["answer_start_at"] = event["_at"]
        elif name == "qa_result":
            # Keep the interaction open until the next qa_start so a queued
            # speech_start logged just after qa_result can still be attached.
            pending["qa_result_at"] = event["_at"]
    if pending is not None:
        completed.append(pending)

    output: list[dict[str, Any]] = []
    for item in completed:
        qa_start = anchor.to_audio_sec(item["qa_start_at"])
        if not lower <= qa_start <= upper:
            continue
        output.append(
            {
                "qa_start": qa_start,
                "question_heard": (
                    anchor.to_audio_sec(item["question_heard_at"])
                    if "question_heard_at" in item
                    else None
                ),
                "question": item.get("question", ""),
                "answer_start": (
                    anchor.to_audio_sec(item["answer_start_at"])
                    if "answer_start_at" in item
                    else None
                ),
                "answer_text": item.get("answer_text", ""),
            }
        )
    return output


def _prompt_modes(
    events: Sequence[dict[str, Any]],
    anchor: SyncAnchor,
    bracket_start_at: datetime,
    bracket_end_at: datetime,
    lower: float,
) -> list[dict[str, Any]]:
    previous_mode: str | None = None
    changes: list[tuple[datetime, str]] = []
    for event in events:
        name = _event_name(event)
        raw_mode: Any = None
        if name == "session_start":
            raw_mode = event.get("prompt_mode")
        elif name == "prompt_mode_change":
            raw_mode = event.get("mode", event.get("prompt_mode"))
        if not isinstance(raw_mode, str) or not raw_mode:
            continue
        if event["_at"] < bracket_start_at:
            previous_mode = raw_mode
        elif event["_at"] <= bracket_end_at:
            changes.append((event["_at"], raw_mode))

    output: list[dict[str, Any]] = []
    if previous_mode is not None and (not changes or changes[0][0] > bracket_start_at):
        output.append({"time": lower, "mode": previous_mode})
    for changed_at, mode in changes:
        time = max(lower, anchor.to_audio_sec(changed_at))
        if output and output[-1]["mode"] == mode:
            continue
        output.append({"time": time, "mode": mode})
    return output


def prepare_ai_events(
    log_files: Sequence[str | Path],
    audio_file: str | Path,
    *,
    sync: str | None = None,
    recording_start: str | None = None,
    legacy: bool = False,
) -> dict[str, Any]:
    """Build deterministic, audio-relative events from application logs."""
    if not log_files:
        raise ValueError("At least one JSONL log file is required")
    audio_path = Path(audio_file)
    duration_sec = float(sf.info(audio_path).duration)
    events = read_merged_events(log_files, legacy=legacy)
    anchor, anchor_event = _resolve_anchor(
        events,
        sync=sync,
        recording_start=recording_start,
    )
    bracket_start_at, bracket_end_at, lower, upper = _experiment_window(
        events,
        anchor,
        anchor_event,
        duration_sec,
        legacy=legacy,
    )

    utterances = (
        _legacy_ai_utterances(events, anchor, lower, upper)
        if legacy
        else _v2_ai_utterances(events, anchor, lower, upper)
    )
    utterances.sort(key=lambda item: (item["start"], item["end"]))

    return {
        "meta": {
            "schema_version": 1 if legacy else 2,
            "sync": {
                "description": anchor.description,
                "audio_anchor_sec": anchor.audio_sec,
                "log_anchor_at": anchor.log_time.isoformat().replace("+00:00", "Z"),
            },
            "duration_sec": duration_sec,
            "log_files": [str(Path(path)) for path in log_files],
            "experiment": {"start": lower, "end": upper},
        },
        "ai_utterances": utterances,
        "speech_yields": _speech_yields(events, anchor, lower, upper),
        "qa_interactions": _qa_interactions(events, anchor, lower, upper),
        "system_stops": _system_stops(events, anchor, lower, upper),
        "prompt_modes": _prompt_modes(
            events,
            anchor,
            bracket_start_at,
            bracket_end_at,
            lower,
        ),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert sightseeing_AI JSONL logs to audio-relative AI events."
    )
    parser.add_argument("log_files", nargs="+", help="One or more JSONL log files")
    parser.add_argument(
        "--audio", required=True, help="WAV/audio file used for duration"
    )
    sync_group = parser.add_mutually_exclusive_group(required=True)
    sync_group.add_argument(
        "--sync",
        help='Protocol anchor, for example "audio=12.5,log=experiment_start"',
    )
    sync_group.add_argument(
        "--recording_start",
        help="Absolute ISO8601 timestamp for audio time zero",
    )
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="Explicitly enable schema v1 text matching and duration estimation",
    )
    parser.add_argument(
        "--output",
        help="Output path (default: outputs/coding/<audio-basename>/ai_events.json)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the AI-event preparation CLI."""
    args = _build_parser().parse_args(argv)
    result = prepare_ai_events(
        args.log_files,
        args.audio,
        sync=args.sync,
        recording_start=args.recording_start,
        legacy=args.legacy,
    )
    basename = Path(args.audio).stem
    output_path = (
        Path(args.output)
        if args.output
        else Path("outputs") / "coding" / basename / "ai_events.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
