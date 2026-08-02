"""コーディング結果の可視化 HTML を生成する。

各録音の区間ラベルの合計時間(録音時間比の%と絶対時間)と、イベントラベルの
件数ヒートマップを1枚の自己完結 HTML にまとめる。LLM を使わない決定論的処理。

使い方:
  uv run src/backend/coding/visualize_coding.py \
      --coding 調査1=outputs/coding/chosa1/coding.json 調査2=... \
      [--audio 調査1=audios/num_speakers_2/chosa1.wav ...] \
      --output outputs/coding/coding_summary.html

--audio を与えるとその wav の実長を録音時間に使う(soundfile が必要)。
無い場合は区間・イベントの最大終了時刻で近似する。
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

INTERVAL_ORDER = ["会話", "無言", "AI説明", "AI応答", "システム停止"]
EVENT_ORDER = [
    "視覚障害者からの話題提示",
    "同行者からの話題提示",
    "視覚障害者から同行者への質問",
    "同行者から視覚障害者への質問",
    "AI情報の共有",
    "同行者からの周囲説明",
    "応答なし発話",
    "ガイド発話",
]
TAG_ROW = "周囲の話題(タグ)"
CO_TOPIC_ROW = "併記: 話題提示"
CO_QUESTION_ROW = "併記: 質問"


def _fmt_mmss(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    return f"{seconds // 60}:{seconds % 60:02d}"


def _is_rejected(item: dict) -> bool:
    """ビューアで「✗要修正」にされた項目は集計から除外する。"""
    review = item.get("review")
    return isinstance(review, dict) and review.get("status") == "needs_correction"


def _load_one(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    durations: dict[str, float] = defaultdict(float)
    max_end = 0.0
    rejected = 0
    reviewed = 0
    for item in data.get("intervals", []) + data.get("events", []):
        review = item.get("review")
        if isinstance(review, dict) and review.get("status"):
            reviewed += 1
    kept_intervals = []
    for item in data.get("intervals", []):
        if _is_rejected(item):
            rejected += 1
            continue
        kept_intervals.append(item)
        start = float(item["start"])
        end = float(item["end"])
        if math.isfinite(start) and math.isfinite(end) and end > start:
            durations[item["label"]] += end - start
            max_end = max(max_end, end)
    kept_events = [e for e in data.get("events", []) if not _is_rejected(e)]
    rejected += sum(1 for e in data.get("events", []) if _is_rejected(e))
    events = Counter(item["label"] for item in kept_events)
    for item in data.get("events", []):
        max_end = max(max_end, float(item.get("end") or item.get("time") or 0.0))
    tag_count = sum(1 for item in kept_events if "周囲の話題" in (item.get("tags") or []))

    def _co_labels(event: dict) -> list:
        attrs = event.get("attrs") or {}
        co = attrs.get("co_labels")
        return co if isinstance(co, list) else []

    co_topic = sum(1 for item in kept_events if "話題提示" in _co_labels(item))
    co_question = sum(1 for item in kept_events if "質問" in _co_labels(item))
    human = sum(
        1 for item in kept_intervals + kept_events if item.get("source") == "human"
    )
    return {
        "intervals": dict(durations),
        "events": dict(events),
        "tags": tag_count,
        "co_topic": co_topic,
        "co_question": co_question,
        "human": human,
        "max_end": max_end,
        "rejected": rejected,
        "reviewed": reviewed,
    }


def _audio_duration(path: Path) -> float | None:
    try:
        import soundfile as sf

        return float(sf.info(path).duration)
    except Exception:
        return None


def build_dataset(
    coding: dict[str, Path], audio: dict[str, Path]
) -> dict:
    recordings = []
    for name, path in coding.items():
        one = _load_one(path)
        duration = None
        if name in audio:
            duration = _audio_duration(audio[name])
        if duration is None:
            duration = one["max_end"]
        recordings.append(
            {
                "name": name,
                "duration": duration,
                "intervals": one["intervals"],
                "events": one["events"],
                "tags": one["tags"],
                "co_topic": one["co_topic"],
                "co_question": one["co_question"],
                "human": one["human"],
                "rejected": one["rejected"],
                "reviewed": one["reviewed"],
            }
        )
    return {
        "recordings": recordings,
        "interval_order": INTERVAL_ORDER,
        "event_order": EVENT_ORDER,
        "tag_row": TAG_ROW,
        "co_topic_row": CO_TOPIC_ROW,
        "co_question_row": CO_QUESTION_ROW,
    }


HTML_TEMPLATE = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>コーディング結果サマリー</title>
<style>
  :root { color-scheme: light dark; }
  body { margin: 0; font-family: -apple-system, "Hiragino Sans", "Noto Sans JP", sans-serif; }
  .viz-root {
    color-scheme: light;
    --surface-1: #fcfcfb; --surface-2: #f2f1ee;
    --text-primary: #0b0b0b; --text-secondary: #52514e; --text-muted: #8a897f;
    --s1: #2a78d6; --s2: #eb6834; --s3: #1baf7a; --s4: #eda100; --s5: #e87ba4;
    --seq-lo: #eaf1fb; --seq-hi: #2a78d6; --grid: #e4e3de;
    background: var(--surface-1); color: var(--text-primary);
    padding: 24px; max-width: 1080px; margin: 0 auto;
  }
  @media (prefers-color-scheme: dark) {
    :root:where(:not([data-theme="light"])) .viz-root {
      color-scheme: dark;
      --surface-1: #1a1a19; --surface-2: #242422;
      --text-primary: #ffffff; --text-secondary: #c3c2b7; --text-muted: #8a897f;
      --s1: #3987e5; --s2: #d95926; --s3: #199e70; --s4: #c98500; --s5: #d55181;
      --seq-lo: #1d2c40; --seq-hi: #3987e5; --grid: #3a3a37;
    }
  }
  :root[data-theme="dark"] .viz-root {
    color-scheme: dark;
    --surface-1: #1a1a19; --surface-2: #242422;
    --text-primary: #ffffff; --text-secondary: #c3c2b7; --text-muted: #8a897f;
    --s1: #3987e5; --s2: #d95926; --s3: #199e70; --s4: #c98500; --s5: #d55181;
    --seq-lo: #1d2c40; --seq-hi: #3987e5; --grid: #3a3a37;
  }
  h1 { font-size: 20px; margin: 0 0 4px; }
  .sub { color: var(--text-secondary); font-size: 13px; margin-bottom: 24px; }
  h2 { font-size: 15px; margin: 28px 0 4px; }
  .note { color: var(--text-muted); font-size: 12px; margin: 0 0 12px; }
  .legend { display: flex; flex-wrap: wrap; gap: 14px; font-size: 12px;
            color: var(--text-secondary); margin: 8px 0 14px; }
  .legend .sw { display: inline-block; width: 10px; height: 10px; border-radius: 3px;
                margin-right: 5px; vertical-align: -1px; }
  .rec { margin-bottom: 18px; }
  .rec-name { font-size: 13px; font-weight: 600; margin-bottom: 4px; }
  .rec-name span { color: var(--text-muted); font-weight: 400; }
  .row { display: grid; grid-template-columns: 96px 1fr; align-items: center;
         gap: 8px; margin: 3px 0; font-size: 12px; }
  .row .lab { color: var(--text-secondary); text-align: right; }
  .track { position: relative; height: 16px; background: var(--surface-2);
           border-radius: 4px; overflow: visible; }
  .bar { position: absolute; left: 0; top: 0; bottom: 0; border-radius: 4px; min-width: 2px; }
  .val { position: absolute; left: 4px; top: -1px; font-size: 11px; line-height: 18px;
         color: var(--text-primary); white-space: nowrap; }
  .val.outside { color: var(--text-secondary); }
  table.heat { border-collapse: separate; border-spacing: 2px; font-size: 12px; width: 100%; }
  table.heat th { font-weight: 400; color: var(--text-secondary); padding: 4px 6px; }
  table.heat th.rowh { text-align: right; white-space: nowrap; }
  table.heat td { text-align: center; padding: 6px 4px; border-radius: 4px; min-width: 44px; }
  .foot { color: var(--text-muted); font-size: 11px; margin-top: 24px; }
  .tip { position: fixed; pointer-events: none; background: var(--text-primary);
         color: var(--surface-1); padding: 4px 8px; border-radius: 6px; font-size: 12px;
         opacity: 0; transition: opacity .08s; z-index: 10; white-space: nowrap; }
</style></head>
<body><div class="viz-root">
<h1>コーディング結果サマリー</h1>
<div class="sub">__SUBTITLE__</div>

<h2>区間ラベル — 録音時間に占める割合</h2>
<p class="note">バーは各録音の長さに対する%(ラベル併記は 実時間)。会話と AI 説明などのレーンは並行して成立するため、合計は100%になりません。</p>
<div class="legend" id="legend"></div>
<div id="intervals"></div>

<h2>イベントラベル — 件数</h2>
<p class="note">セルの濃さは件数(録音ごとの補正なし)。「周囲の話題」はイベントに併記されるタグの件数。
「併記: 話題提示 / 質問」は attrs.co_labels の集計(新話題を開く質問への話題提示併記、AI情報の共有への必須併記)。</p>
<div id="events" style="overflow-x:auto"></div>

<div class="foot">生成: transcriber visualize_coding.py(コーディング JSON から決定論的に集計)。
ラベル件数は LLM コーディングの実行ごとに数件変動しうる。確定値はレビュー UI での人間確認後の値を用いること。</div>
<div class="tip" id="tip"></div>
</div>
<script>
const DATA = __DATA__;
const SERIES = ["--s1","--s2","--s3","--s4","--s5"];
const css = getComputedStyle(document.querySelector(".viz-root"));
const tip = document.getElementById("tip");
function showTip(e, html) { tip.innerHTML = html; tip.style.opacity = 1;
  tip.style.left = (e.clientX + 12) + "px"; tip.style.top = (e.clientY + 12) + "px"; }
function hideTip() { tip.style.opacity = 0; }
function fmt(s) { s = Math.round(s); return Math.floor(s/60) + ":" + String(s%60).padStart(2,"0"); }

const legend = document.getElementById("legend");
DATA.interval_order.forEach((lab, i) => {
  const item = document.createElement("span");
  item.innerHTML = `<span class="sw" style="background:var(${SERIES[i]})"></span>${lab}`;
  legend.appendChild(item);
});

const ivRoot = document.getElementById("intervals");
DATA.recordings.forEach(rec => {
  const div = document.createElement("div"); div.className = "rec";
  let revNote = rec.reviewed > 0
    ? ` / レビュー済み${rec.reviewed}件` + (rec.rejected > 0 ? `・要修正除外${rec.rejected}件` : "")
    : "";
  if (rec.human > 0) revNote += `・手動追加${rec.human}件`;
  div.innerHTML = `<div class="rec-name">${rec.name} <span>(${fmt(rec.duration)}${revNote})</span></div>`;
  DATA.interval_order.forEach((lab, i) => {
    if (!(lab in rec.intervals)) return;
    const sec = rec.intervals[lab];
    const pct = rec.duration > 0 ? Math.min(100, sec / rec.duration * 100) : 0;
    const row = document.createElement("div"); row.className = "row";
    const inside = pct > 22;
    row.innerHTML = `<div class="lab">${lab}</div>
      <div class="track"><div class="bar" style="width:${pct}%;background:var(${SERIES[i]})"></div>
      <div class="val ${inside ? "" : "outside"}" style="left:${inside ? "4px" : `calc(${pct}% + 6px)`}">
      ${Math.round(pct)}%・${fmt(sec)}</div></div>`;
    row.addEventListener("mousemove", e => showTip(e, `${rec.name} / ${lab}: ${fmt(sec)}(${pct.toFixed(1)}%)`));
    row.addEventListener("mouseleave", hideTip);
    div.appendChild(row);
  });
  ivRoot.appendChild(div);
});

const evRoot = document.getElementById("events");
const names = DATA.recordings.map(r => r.name);
const rows = DATA.event_order.map(lab => ({lab, vals: DATA.recordings.map(r => r.events[lab] || 0)}));
rows.push({lab: DATA.tag_row, vals: DATA.recordings.map(r => r.tags)});
rows.push({lab: DATA.co_topic_row, vals: DATA.recordings.map(r => r.co_topic || 0)});
rows.push({lab: DATA.co_question_row, vals: DATA.recordings.map(r => r.co_question || 0)});
const maxVal = Math.max(1, ...rows.flatMap(r => r.vals));
function mix(hex1, hex2, t) {
  const a = hex1.match(/\\w\\w/g).map(x => parseInt(x, 16));
  const b = hex2.match(/\\w\\w/g).map(x => parseInt(x, 16));
  return "rgb(" + a.map((v, i) => Math.round(v + (b[i] - v) * t)).join(",") + ")";
}
const lo = css.getPropertyValue("--seq-lo").trim(), hi = css.getPropertyValue("--seq-hi").trim();
const darkText = css.getPropertyValue("--surface-1").trim();
let html = `<table class="heat"><tr><th></th>${names.map(n => `<th>${n}</th>`).join("")}</tr>`;
rows.forEach(r => {
  html += `<tr><th class="rowh">${r.lab}</th>` + r.vals.map((v, i) => {
    const t = v / maxVal;
    const bg = v === 0 ? "var(--surface-2)" : mix(lo.replace("#",""), hi.replace("#",""), 0.15 + 0.85 * t);
    const color = t > 0.55 ? darkText : "var(--text-primary)";
    return `<td style="background:${bg};color:${color}" data-tip="${names[i]} / ${r.lab}: ${v}件">${v || ""}</td>`;
  }).join("") + "</tr>";
});
html += "</table>";
evRoot.innerHTML = html;
evRoot.querySelectorAll("td[data-tip]").forEach(td => {
  td.addEventListener("mousemove", e => showTip(e, td.dataset.tip));
  td.addEventListener("mouseleave", hideTip);
});
</script></body></html>
"""


DISPLAY_NAMES = {
    "chosa1": "調査1", "chosa2": "調査2", "chosa3": "調査3",
    "chosa4": "調査4", "chosa5": "調査5", "interview": "インタビュー",
}
AUTO_ORDER = ["chosa1", "chosa2", "chosa3", "chosa4", "chosa5", "interview"]


def _discover(auto_dir: Path, reviewed_dir: Path | None) -> dict[str, Path]:
    """outputs/coding を走査し、レビュー済みエクスポートがあれば優先する。

    レビューエクスポート(ビューアの「エクスポート」で保存した JSON)は
    reviewed_dir に置くだけでよい。ファイル名は任意で、中の "audio" フィールド
    (例 "chosa1.wav")から対応する録音を特定して coding.json を置き換える。
    """
    base: dict[str, Path] = {}
    aliases: dict[str, str] = {}
    for path in sorted(auto_dir.glob("*/coding.json")):
        key = path.parent.name
        base[key] = path
        aliases[key] = key
        if key in DISPLAY_NAMES:
            aliases[DISPLAY_NAMES[key]] = key
        try:
            own_audio = json.loads(path.read_text(encoding="utf-8")).get("audio", "")
            if own_audio:
                aliases[Path(str(own_audio)).stem] = key
        except (OSError, json.JSONDecodeError):
            pass
    if reviewed_dir and reviewed_dir.is_dir():
        for path in sorted(reviewed_dir.glob("*.json")):
            try:
                audio = json.loads(path.read_text(encoding="utf-8")).get("audio", "")
            except (OSError, json.JSONDecodeError):
                continue
            stem = Path(str(audio)).stem
            # ".review" などの付加サフィックスも許容する
            key = aliases.get(stem) or aliases.get(stem.split(".")[0])
            if key:
                base[key] = path
                print(f"レビュー反映: {key} ← {path.name}")
    ordered = [k for k in AUTO_ORDER if k in base]
    ordered += [k for k in sorted(base) if k not in ordered]
    return {DISPLAY_NAMES.get(k, k): base[k] for k in ordered}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="コーディング結果の可視化 HTML を生成")
    parser.add_argument(
        "--coding", nargs="+", metavar="名前=path",
        help="表示名=coding.json のペア(表示順どおりに)",
    )
    parser.add_argument(
        "--auto", metavar="DIR",
        help="DIR/*/coding.json を自動収集(chosaN→調査N の表示名で)",
    )
    parser.add_argument(
        "--reviewed", metavar="DIR",
        help="ビューアでエクスポートしたレビュー JSON を置くディレクトリ。"
             "audio 名で対応録音の集計元を置き換える(--auto と併用)",
    )
    parser.add_argument(
        "--audio", nargs="*", default=[], metavar="名前=path",
        help="表示名=音声ファイル(録音実長の取得用、省略可)",
    )
    parser.add_argument("--output", required=True)
    parser.add_argument("--subtitle", default="")
    args = parser.parse_args(argv)
    if bool(args.coding) == bool(args.auto):
        raise SystemExit("--coding か --auto のどちらか一方を指定してください")

    def parse_pairs(pairs: list[str]) -> dict[str, Path]:
        mapping: dict[str, Path] = {}
        for pair in pairs:
            name, sep, path = pair.partition("=")
            if not sep:
                raise SystemExit(f"名前=path の形式で指定してください: {pair!r}")
            mapping[name.strip()] = Path(path.strip())
        return mapping

    if args.auto:
        coding = _discover(
            Path(args.auto), Path(args.reviewed) if args.reviewed else None
        )
        if not coding:
            raise SystemExit(f"coding.json が見つかりません: {args.auto}")
    else:
        coding = parse_pairs(args.coding)
    audio = parse_pairs(args.audio)
    dataset = build_dataset(coding, audio)
    subtitle = args.subtitle or (
        f"{len(dataset['recordings'])} 録音 / 区間ラベルの時間と、イベントラベルの件数"
    )
    html = HTML_TEMPLATE.replace("__DATA__", json.dumps(dataset, ensure_ascii=False))
    html = html.replace("__SUBTITLE__", subtitle)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
