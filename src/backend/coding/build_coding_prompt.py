from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .schema import validate_coding_result
except ImportError:  # Direct script execution.
    from schema import validate_coding_result

REPO_ROOT = Path(__file__).resolve().parents[3]
CODING_SCHEME_PATH = REPO_ROOT / "docs" / "coding_scheme.md"
GAP_THRESHOLD_SEC = 3.0
CHUNK_OVERLAP_SEC = 60.0

KIND_TO_INTERVAL_LABEL = {
    "scene": "AI説明",
    "qa_answer": "AI応答",
    "deepdive": "AI応答",
}


def parse_speaker_roles(value: str) -> dict[str, str]:
    """Parse comma-separated ``speaker=role`` assignments."""
    mapping: dict[str, str] = {}
    for assignment in value.split(","):
        speaker, separator, role = assignment.partition("=")
        speaker = speaker.strip()
        role = role.strip()
        if not separator or not speaker or not role:
            raise ValueError(
                "--speaker_roles must look like "
                "'SPEAKER_00=視覚障害者,SPEAKER_01=同行者'"
            )
        if role not in {"視覚障害者", "同行者", "実験者"}:
            raise ValueError(
                f"Unsupported role {role!r}; use 視覚障害者 / 同行者 / 実験者"
            )
        mapping[speaker] = role
    if not mapping:
        raise ValueError("At least one speaker role mapping is required")
    return mapping


def load_transcript(
    path: str | Path,
    speaker_roles: Mapping[str, str],
) -> list[dict[str, Any]]:
    """Load and role-map the transcriber JSON format."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("transcripts"), list):
        # 擬似3chモードの出力は {meta, transcripts} 形式
        data = data["transcripts"]
    if not isinstance(data, list):
        raise ValueError("Transcript JSON must be an array")
    transcript: list[dict[str, Any]] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Transcript item {index} must be an object")
        try:
            start = float(item["start"])
            end = float(item["end"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"Transcript item {index} requires numeric start/end"
            ) from exc
        if not (math.isfinite(start) and math.isfinite(end) and start < end):
            raise ValueError(f"Transcript item {index} must satisfy start < end")
        speaker = item.get("speaker")
        if speaker not in speaker_roles:
            raise ValueError(
                f"Transcript speaker {speaker!r} has no --speaker_roles mapping"
            )
        text = item.get("text")
        if not isinstance(text, str):
            raise ValueError(f"Transcript item {index}.text must be a string")
        transcript.append(
            {
                "start": start,
                "end": end,
                "speaker": speaker_roles[str(speaker)],
                "speaker_id": speaker,
                "text": text,
            }
        )
    transcript.sort(key=lambda entry: (entry["start"], entry["end"]))
    return transcript


def _coding_window(ai_events: Mapping[str, Any]) -> tuple[float, float]:
    meta = ai_events.get("meta")
    if not isinstance(meta, dict):
        raise ValueError("ai_events.meta must be an object")
    duration = meta.get("duration_sec")
    if not isinstance(duration, (int, float)) or not math.isfinite(float(duration)):
        raise ValueError("ai_events.meta.duration_sec must be finite")
    experiment = meta.get("experiment", {})
    lower = float(experiment.get("start", 0.0))
    upper = float(experiment.get("end", duration))
    if lower < 0 or lower >= upper or upper > float(duration) + 1e-6:
        raise ValueError("ai_events.meta.experiment is outside the audio duration")
    return lower, upper


def _transcript_window(
    transcript: Sequence[Mapping[str, Any]],
) -> tuple[float, float]:
    """Derive the available coding window when there is no application log."""
    if not transcript:
        raise ValueError(
            "Cannot determine the coding window from an empty transcript "
            "without --ai_events"
        )
    upper = max(float(item["end"]) for item in transcript)
    if not math.isfinite(upper) or upper <= 0:
        raise ValueError("Transcript end times must define a positive coding window")
    return 0.0, upper


def _clip(
    start: float,
    end: float,
    lower: float,
    upper: float,
) -> tuple[float, float] | None:
    result = max(start, lower), min(end, upper)
    return result if result[0] < result[1] else None


def build_human_interval_candidates(
    transcript: Sequence[Mapping[str, Any]],
    duration_sec: float,
    *,
    start_sec: float = 0.0,
    check_ai_addressed_speech: bool = True,
) -> list[dict[str, Any]]:
    """Create conversation/silence candidates using the three-second gap rule."""
    if start_sec < 0 or duration_sec <= start_sec:
        raise ValueError("Candidate window must satisfy 0 <= start < end")
    utterances: list[tuple[float, float]] = []
    for item in transcript:
        clipped = _clip(
            float(item["start"]),
            float(item["end"]),
            start_sec,
            duration_sec,
        )
        if clipped is not None:
            utterances.append(clipped)
    utterances.sort()

    conversation: list[tuple[float, float]] = []
    if utterances:
        group_start, group_end = utterances[0]
        for start, end in utterances[1:]:
            if start - group_end < GAP_THRESHOLD_SEC:
                group_end = max(group_end, end)
                continue
            conversation.append(
                (group_start, min(group_end + GAP_THRESHOLD_SEC, duration_sec))
            )
            group_start, group_end = start, end
        conversation.append(
            (group_start, min(group_end + GAP_THRESHOLD_SEC, duration_sec))
        )

    silence: list[tuple[float, float]] = []
    cursor = start_sec
    for start, end in conversation:
        if cursor < start:
            silence.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < duration_sec:
        silence.append((cursor, duration_sec))

    output = [
        {
            "label": "会話",
            "start": start,
            "end": end,
            "source": "auto",
            "note": (
                "3秒ギャップ規則による候補。LLMが応答・相槌とAI宛発話を確認する"
                if check_ai_addressed_speech
                else "3秒ギャップ規則による候補。LLMが応答・相槌を確認する"
            ),
        }
        for start, end in conversation
        if start < end
    ]
    output.extend(
        {
            "label": "無言",
            "start": start,
            "end": end,
            "source": "auto",
            "note": "3秒ギャップ規則による候補。LLMが会話区間確定後に調整する",
        }
        for start, end in silence
        if start < end
    )
    return sorted(output, key=lambda item: (item["start"], item["end"], item["label"]))


def build_scaffold(
    transcript: Sequence[Mapping[str, Any]],
    ai_events: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build all deterministic interval labels and human interval candidates."""
    lower, upper = (
        _coding_window(ai_events)
        if ai_events is not None
        else _transcript_window(transcript)
    )
    intervals: list[dict[str, Any]] = []
    if ai_events is not None:
        for utterance in ai_events.get("ai_utterances", []):
            if not isinstance(utterance, dict):
                continue
            label = KIND_TO_INTERVAL_LABEL.get(utterance.get("kind"))
            if label is None:
                continue
            clipped = _clip(
                float(utterance["start"]),
                float(utterance["end"]),
                lower,
                upper,
            )
            if clipped is None:
                continue
            intervals.append(
                {
                    "label": label,
                    "start": clipped[0],
                    "end": clipped[1],
                    "source": "auto",
                    "note": (
                        f"アプリログ speech_start/speech_end"
                        f"（kind={utterance.get('kind')}）"
                    ),
                }
            )
        for stop in ai_events.get("system_stops", []):
            if not isinstance(stop, dict):
                continue
            clipped = _clip(float(stop["start"]), float(stop["end"]), lower, upper)
            if clipped is not None:
                intervals.append(
                    {
                        "label": "システム停止",
                        "start": clipped[0],
                        "end": clipped[1],
                        "source": "auto",
                        "note": "session_stop(reason=user)→session_start から自動導出",
                    }
                )
    intervals.extend(
        build_human_interval_candidates(
            transcript,
            upper,
            start_sec=lower,
            check_ai_addressed_speech=ai_events is not None,
        )
    )
    intervals.sort(key=lambda item: (item["start"], item["end"], item["label"]))
    for index, item in enumerate(intervals, start=1):
        item["id"] = f"iv-{index:04d}"
    return {"intervals": intervals, "events": []}


def _filter_transcript(
    transcript: Sequence[Mapping[str, Any]],
    lower: float,
    upper: float,
) -> list[dict[str, Any]]:
    return [
        dict(item)
        for item in transcript
        if float(item["end"]) > lower and float(item["start"]) < upper
    ]


def _filter_ai_events(
    ai_events: Mapping[str, Any],
    lower: float,
    upper: float,
) -> dict[str, Any]:
    filtered = copy.deepcopy(dict(ai_events))
    for key in ("ai_utterances", "speech_yields", "system_stops"):
        filtered[key] = [
            item
            for item in ai_events.get(key, [])
            if isinstance(item, dict)
            and float(item.get("end", -1)) > lower
            and float(item.get("start", math.inf)) < upper
        ]
    filtered["qa_interactions"] = [
        item
        for item in ai_events.get("qa_interactions", [])
        if isinstance(item, dict) and lower <= float(item.get("qa_start", -1)) < upper
    ]
    filtered["prompt_modes"] = [
        item
        for item in ai_events.get("prompt_modes", [])
        if isinstance(item, dict) and lower <= float(item.get("time", -1)) < upper
    ]
    return filtered


def _filter_scaffold(
    scaffold: Mapping[str, Any],
    lower: float,
    upper: float,
) -> dict[str, Any]:
    intervals: list[dict[str, Any]] = []
    for item in scaffold["intervals"]:
        clipped = _clip(float(item["start"]), float(item["end"]), lower, upper)
        if clipped is None:
            continue
        copied = dict(item)
        copied["start"], copied["end"] = clipped
        intervals.append(copied)
    return {"intervals": intervals, "events": []}


def build_prompt_text(
    *,
    audio_name: str,
    transcript: Sequence[Mapping[str, Any]],
    ai_events: Mapping[str, Any] | None = None,
    scaffold: Mapping[str, Any],
    coding_scheme: str,
    window: tuple[float, float] | None = None,
    core_window: tuple[float, float] | None = None,
) -> str:
    """Build the complete prompt consumed by ``codex exec``."""
    lower, upper = window or (
        _coding_window(ai_events)
        if ai_events is not None
        else _transcript_window(transcript)
    )
    visible_transcript = _filter_transcript(transcript, lower, upper)
    visible_scaffold = _filter_scaffold(scaffold, lower, upper)
    chunk_instruction = ""
    if core_window is not None:
        chunk_instruction = (
            f"\nこのチャンクの参照窓は {lower:.3f}〜{upper:.3f} 秒、"
            f"マージ時の中核窓は {core_window[0]:.3f}〜"
            f"{core_window[1]:.3f} 秒です。境界判断には重複部分も使い、"
            "参照窓内の完全な結果を返してください。"
        )

    schema_example = {
        "version": 1,
        "audio": audio_name,
        "intervals": [
            {
                "id": "iv-0001",
                "label": "会話",
                "start": 12.3,
                "end": 45.6,
                "source": "llm",
                "note": "",
            }
        ],
        "events": [
            {
                "id": "ev-0001",
                "label": "視覚障害者からの話題提示",
                "time": 34.5,
                "end": 37.2,
                "speaker": "視覚障害者",
                "tags": ["周囲の話題"],
                "attrs": {
                    "co_labels": ["話題提示"],
                    **(
                        {"ai_reference": "within_30s"}
                        if ai_events is not None
                        else {}
                    ),
                },
                "text": "該当発話テキスト",
                "note": "",
            }
        ],
    }
    if ai_events is None:
        return f"""あなたは会話コーディング担当です。
以下の定義、決定論的スキャフォールド、役割変換済み文字起こしを突き合わせ、
指定スキーマに適合する最終コーディングを作成してください。
対象音声は {audio_name}、対象時間窓は {lower:.3f}〜{upper:.3f} 秒です。{chunk_instruction}

重要な指示:
- 出力は有効なJSONオブジェクトのみとし、Markdown、コードフェンス、説明文を付けない。
- intervals と events はそれぞれ時刻順に並べ、全idを一意にする。
- この録音に AI は関与しない。AI説明/AI応答/システム停止/AI情報の共有 は付与対象外。
- 会話・無言は候補である。応答と相槌を意味的に確認して境界を確定し、確定・修正した
  会話/無言は source="llm" とする。
- 人間側ラベル（話題提示、質問、周囲説明、応答なし発話、ガイド発話、
  周囲の話題タグ、相槌判定による会話区間確定）に集中する。
- 質問が新しい話題を開始する場合も attrs.co_labels に "話題提示" を入れる。
- 同行者からの周囲説明には attrs.response_type を "自発" または "質問応答" で
  必ず入れる。
- attrs の未使用属性は省略してよいが attrs 自体は必ずオブジェクトにする。
- tags は該当時だけ "周囲の話題" を含め、それ以外は空配列にする。
- イベントの time/end/text は根拠となる1発話の範囲と本文に合わせる。

## コーディングスキーム
{coding_scheme}

## 出力スキーマ例（ラベルは定義に従って置き換える）
{json.dumps(schema_example, ensure_ascii=False, indent=2)}

## 決定論的スキャフォールド
{json.dumps(visible_scaffold, ensure_ascii=False, indent=2)}

## 文字起こし（話者役割変換済み）
{json.dumps(visible_transcript, ensure_ascii=False, indent=2)}
"""

    visible_ai_events = _filter_ai_events(ai_events, lower, upper)
    return f"""あなたは観光実験の会話コーディング担当です。
以下の定義、決定論的スキャフォールド、役割変換済み文字起こし、アプリログを
突き合わせ、指定スキーマに適合する最終コーディングを作成してください。
対象音声は {audio_name}、対象時間窓は {lower:.3f}〜{upper:.3f} 秒です。{chunk_instruction}

重要な指示:
- 出力は有効なJSONオブジェクトのみとし、Markdown、コードフェンス、説明文を付けない。
- intervals と events はそれぞれ時刻順に並べ、全idを一意にする。
- ログ由来の AI説明・AI応答・システム停止は時刻と source="auto" を維持する。
- 会話・無言は候補である。応答と相槌を意味的に確認して境界を確定し、確定・修正した
  会話/無言は source="llm" とする。
- AI宛のQ&A発話は人間同士の会話区間から除外する。qa_interactions の question と
  文字起こしを照合する。
- 話題提示、質問、AI情報の共有、周囲の話題、周囲説明、ガイド発話、
  応答なし発話を定義どおり意味判断して付与する。
- AI情報の共有には attrs.co_labels に "話題提示" または "質問" を必ず入れる。
- 質問が新しい話題を開始する場合も attrs.co_labels に "話題提示" を入れる。
- 同行者からの周囲説明には attrs.response_type を "自発" または "質問応答" で
  必ず入れる。
- attrs の未使用属性は省略してよいが attrs 自体は必ずオブジェクトにする。
- tags は該当時だけ "周囲の話題" を含め、それ以外は空配列にする。
- イベントの time/end/text は根拠となる1発話の範囲と本文に合わせる。
- system/tsunagi のAI発話は参考情報であり、AI説明・AI応答にはしない。

## コーディングスキーム
{coding_scheme}

## 出力スキーマ例（ラベルは定義に従って置き換える）
{json.dumps(schema_example, ensure_ascii=False, indent=2)}

## 決定論的スキャフォールド
{json.dumps(visible_scaffold, ensure_ascii=False, indent=2)}

## 文字起こし（話者役割変換済み）
{json.dumps(visible_transcript, ensure_ascii=False, indent=2)}

## AIイベント（音声相対秒）
{json.dumps(visible_ai_events, ensure_ascii=False, indent=2)}
"""


def _chunk_windows(
    lower: float,
    upper: float,
    chunk_sec: float,
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    windows = []
    context_sec = CHUNK_OVERLAP_SEC / 2.0
    core_start = lower
    while core_start < upper:
        core_end = min(core_start + chunk_sec, upper)
        window = (
            max(lower, core_start - context_sec),
            min(upper, core_end + context_sec),
        )
        windows.append((window, (core_start, core_end)))
        core_start = core_end
    return windows


def write_prompts(
    *,
    transcript_path: str | Path,
    ai_events_path: str | Path | None = None,
    speaker_roles: Mapping[str, str],
    output_path: str | Path,
    chunk_minutes: float | None = None,
) -> Path:
    """Write one prompt, or chunk prompts plus a machine-readable manifest."""
    transcript = load_transcript(transcript_path, speaker_roles)
    ai_events = (
        json.loads(Path(ai_events_path).read_text(encoding="utf-8"))
        if ai_events_path is not None
        else None
    )
    scaffold = build_scaffold(transcript, ai_events)
    scheme = CODING_SCHEME_PATH.read_text(encoding="utf-8")
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    audio_name = f"{Path(transcript_path).stem}.wav"

    if chunk_minutes is None:
        output.write_text(
            build_prompt_text(
                audio_name=audio_name,
                transcript=transcript,
                ai_events=ai_events,
                scaffold=scaffold,
                coding_scheme=scheme,
            ),
            encoding="utf-8",
        )
        return output
    if not math.isfinite(chunk_minutes) or chunk_minutes <= 0:
        raise ValueError("--chunk_minutes must be a positive number")

    chunks_dir = output.parent / f"{output.stem}_chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    lower, upper = (
        _coding_window(ai_events)
        if ai_events is not None
        else _transcript_window(transcript)
    )
    manifest: dict[str, Any] = {
        "version": 1,
        "audio": audio_name,
        "duration_sec": (
            float(ai_events["meta"]["duration_sec"])
            if ai_events is not None
            else upper
        ),
        "chunks": [],
    }
    for index, (window, core) in enumerate(
        _chunk_windows(lower, upper, chunk_minutes * 60.0),
        start=1,
    ):
        prompt_path = chunks_dir / f"chunk-{index:04d}.prompt.txt"
        result_path = chunks_dir / f"chunk-{index:04d}.json"
        prompt_path.write_text(
            build_prompt_text(
                audio_name=audio_name,
                transcript=transcript,
                ai_events=ai_events,
                scaffold=scaffold,
                coding_scheme=scheme,
                window=window,
                core_window=core,
            ),
            encoding="utf-8",
        )
        manifest["chunks"].append(
            {
                "prompt": str(prompt_path),
                "result": str(result_path),
                "window_start": window[0],
                "window_end": window[1],
                "core_start": core[0],
                "core_end": core[1],
            }
        )
    manifest_path = chunks_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def _merge_adjacent_intervals(
    intervals: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for item in intervals:
        if (
            merged
            and merged[-1]["label"] == item["label"]
            and merged[-1]["source"] == item["source"]
            and merged[-1].get("note", "") == item.get("note", "")
            and abs(float(merged[-1]["end"]) - float(item["start"])) <= 1e-6
        ):
            merged[-1]["end"] = item["end"]
        else:
            merged.append(dict(item))
    return merged


def merge_chunk_results(
    manifest_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    """Merge validated overlapping chunk results by their non-overlap core windows."""
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    chunks = manifest.get("chunks")
    if not isinstance(chunks, list) or not chunks:
        raise ValueError("Chunk manifest has no chunks")

    intervals: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks):
        result_path = Path(chunk["result"])
        result = json.loads(result_path.read_text(encoding="utf-8"))
        validate_coding_result(result, duration_sec=float(manifest["duration_sec"]))
        core_start = float(chunk["core_start"])
        core_end = float(chunk["core_end"])
        for item in result["intervals"]:
            clipped = _clip(
                float(item["start"]),
                float(item["end"]),
                core_start,
                core_end,
            )
            if clipped is None:
                continue
            copied = dict(item)
            copied["start"], copied["end"] = clipped
            intervals.append(copied)
        for item in result["events"]:
            event_time = float(item["time"])
            is_last = index == len(chunks) - 1
            if core_start <= event_time < core_end or (
                is_last and event_time == core_end
            ):
                events.append(dict(item))

    intervals.sort(key=lambda item: (item["start"], item["end"], item["label"]))
    events.sort(key=lambda item: (item["time"], item["end"], item["label"]))
    intervals = _merge_adjacent_intervals(intervals)
    for index, item in enumerate(intervals, start=1):
        item["id"] = f"iv-{index:04d}"
    for index, item in enumerate(events, start=1):
        item["id"] = f"ev-{index:04d}"
    output = {
        "version": 1,
        "audio": manifest["audio"],
        "intervals": intervals,
        "events": events,
    }
    validate_coding_result(output, duration_sec=float(manifest["duration_sec"]))
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build Codex prompts or merge chunked coding results."
    )
    parser.add_argument("--transcript")
    parser.add_argument("--ai_events")
    parser.add_argument("--speaker_roles")
    parser.add_argument("--output", required=True)
    parser.add_argument("--chunk_minutes", type=float)
    parser.add_argument("--merge_manifest")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run prompt generation or chunk-result merging."""
    args = _build_parser().parse_args(argv)
    if args.merge_manifest:
        merge_chunk_results(args.merge_manifest, args.output)
        print(args.output)
        return 0
    if not (args.transcript and args.speaker_roles):
        raise SystemExit(
            "--transcript and --speaker_roles are required when building prompts"
        )
    path = write_prompts(
        transcript_path=args.transcript,
        ai_events_path=args.ai_events,
        speaker_roles=parse_speaker_roles(args.speaker_roles),
        output_path=args.output,
        chunk_minutes=args.chunk_minutes,
    )
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
