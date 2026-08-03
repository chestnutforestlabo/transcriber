"""複数参加者のコーディング結果を条件(調査1〜5)ごとに箱ひげ図で比較する。

各参加者に対してパイプラインを実行した後、参加者ごとの outputs/coding を
アーカイブしたディレクトリ群を入力に取り、「同じ指標を条件間で比較する」
1枚の自己完結 HTML を生成する。箱=参加者間の四分位範囲、点=各参加者。

使い方:
  # 参加者ごとの実行後に outputs/coding を退避しておく:
  #   cp -r outputs/coding outputs/participants/P01
  uv run src/backend/coding/visualize_conditions.py \
      --auto outputs/participants \
      --output outputs/coding/conditions_summary.html
  # または個別指定:
  #   --participant P01=outputs/participants/P01 P02=...
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from visualize_coding import (  # type: ignore[import-not-found]
    EVENT_ORDER,
    _load_one,
)

CONDITION_KEYS = ["chosa1", "chosa2", "chosa3", "chosa4", "chosa5"]
CONDITION_NAMES = {
    "chosa1": "調査1", "chosa2": "調査2", "chosa3": "調査3",
    "chosa4": "調査4", "chosa5": "調査5",
}

# 比較できる指標: イベント件数(全ラベル+タグ)と区間時間
METRICS = (
    [{"key": f"ev:{label}", "label": f"{label}(件)", "unit": "件"} for label in EVENT_ORDER]
    + [
        {"key": "tag", "label": "周囲の話題タグ(件)", "unit": "件"},
        {"key": "iv:会話", "label": "会話時間(秒)", "unit": "秒"},
        {"key": "iv:無言", "label": "無言時間(秒)", "unit": "秒"},
        {"key": "iv:AI応答", "label": "AI応答=Q&A使用時間(秒)", "unit": "秒"},
        {"key": "pct:会話", "label": "会話時間の割合(%)", "unit": "%"},
    ]
)


def _metric_value(one: dict, key: str) -> float:
    if key.startswith("ev:"):
        return float(one["events"].get(key[3:], 0))
    if key == "tag":
        return float(one["tags"])
    if key.startswith("iv:"):
        return float(one["intervals"].get(key[3:], 0.0))
    if key == "pct:会話":
        duration = one["max_end"] or 0.0
        if duration <= 0:
            return 0.0
        return one["intervals"].get("会話", 0.0) / duration * 100.0
    raise ValueError(f"unknown metric {key}")


def collect(participants: dict[str, Path]) -> dict:
    values: dict[str, dict[str, list[dict]]] = {
        metric["key"]: {CONDITION_NAMES[c]: [] for c in CONDITION_KEYS} for metric in METRICS
    }
    loaded_names: list[str] = []
    for name, directory in participants.items():
        found_any = False
        for condition in CONDITION_KEYS:
            path = directory / condition / "coding.json"
            if not path.is_file():
                continue
            one = _load_one(path)
            found_any = True
            for metric in METRICS:
                values[metric["key"]][CONDITION_NAMES[condition]].append(
                    {"p": name, "v": round(_metric_value(one, metric["key"]), 3)}
                )
        if found_any:
            loaded_names.append(name)
        else:
            print(f"WARNING: {name}: {directory} に chosaN/coding.json が見つかりません")
    return {
        "participants": loaded_names,
        "conditions": [CONDITION_NAMES[c] for c in CONDITION_KEYS],
        "metrics": METRICS,
        "values": values,
    }


HTML_TEMPLATE = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>条件間比較 — 参加者横断箱ひげ図</title>
<style>
  :root { color-scheme: light dark; }
  body { margin: 0; font-family: -apple-system, "Hiragino Sans", "Noto Sans JP", sans-serif; }
  .viz-root {
    color-scheme: light;
    --surface-1: #fcfcfb; --surface-2: #f2f1ee;
    --text-primary: #0b0b0b; --text-secondary: #52514e; --text-muted: #8a897f;
    --s1: #2a78d6; --s2: #eb6834; --seq-lo: #eaf1fb; --grid: #e4e3de;
    background: var(--surface-1); color: var(--text-primary);
    padding: 24px; max-width: 980px; margin: 0 auto;
  }
  @media (prefers-color-scheme: dark) {
    :root:where(:not([data-theme="light"])) .viz-root {
      color-scheme: dark;
      --surface-1: #1a1a19; --surface-2: #242422;
      --text-primary: #ffffff; --text-secondary: #c3c2b7; --text-muted: #8a897f;
      --s1: #3987e5; --s2: #d95926; --seq-lo: #1d2c40; --grid: #3a3a37;
    }
  }
  :root[data-theme="dark"] .viz-root {
    color-scheme: dark;
    --surface-1: #1a1a19; --surface-2: #242422;
    --text-primary: #ffffff; --text-secondary: #c3c2b7; --text-muted: #8a897f;
    --s1: #3987e5; --s2: #d95926; --seq-lo: #1d2c40; --grid: #3a3a37;
  }
  h1 { font-size: 20px; margin: 0 0 4px; }
  .sub { color: var(--text-secondary); font-size: 13px; margin-bottom: 18px; }
  .note { color: var(--text-muted); font-size: 12px; margin: 0 0 14px; }
  select { padding: 5px 8px; font-size: 13px; border: 1px solid var(--grid);
           border-radius: 6px; background: var(--surface-2); color: var(--text-primary); }
  .chart { position: relative; display: grid;
           grid-template-columns: 56px repeat(5, 1fr); gap: 0 10px;
           align-items: start; margin-top: 18px; }
  .gline { position: absolute; left: 56px; right: 0; border-top: 1px dashed var(--grid); }
  .yaxis { position: relative; height: 260px; }
  .ytick { position: absolute; right: 6px; transform: translateY(50%);
           color: var(--text-muted); font-size: 11px; }
  .col { text-align: center; }
  .vtrack { position: relative; height: 260px; }
  .vwhisker { position: absolute; left: 50%; width: 0; border-left: 1px solid var(--text-muted); }
  .vcap { position: absolute; left: 35%; width: 30%; height: 0; border-top: 1px solid var(--text-muted); }
  .vbox { position: absolute; left: 28%; width: 44%; background: var(--seq-lo);
          border: 1px solid var(--s1); border-radius: 3px; min-height: 2px; }
  .vmedian { position: absolute; left: 28%; width: 44%; height: 0; border-top: 2px solid var(--s1); }
  .vmean { position: absolute; left: 50%; width: 8px; height: 8px; background: var(--s2);
           transform: translate(-50%, 50%) rotate(45deg); }
  .vpt { position: absolute; left: 50%; width: 6px; height: 6px; border-radius: 50%;
         background: var(--text-secondary); opacity: 0.7; transform: translate(-50%, 50%); }
  .cname { margin-top: 6px; font-size: 12px; color: var(--text-primary); }
  .cstat { font-size: 11px; color: var(--text-muted); }
  .tip { position: fixed; pointer-events: none; background: var(--text-primary);
         color: var(--surface-1); padding: 4px 8px; border-radius: 6px; font-size: 12px;
         opacity: 0; transition: opacity .08s; z-index: 10; white-space: pre; }
</style></head>
<body><div class="viz-root">
<h1>条件間比較 — 参加者横断箱ひげ図</h1>
<div class="sub">__SUBTITLE__</div>
<p class="note">同じ指標を条件(調査1〜5)間で比較する。箱=参加者間の四分位範囲(Q1〜Q3)、
横線=中央値、◆=平均、○=各参加者。下段は μ=平均 / σ²=不偏分散(参加者1名の場合は分散なし)。
✗要修正の項目は集計から除外済み。</p>
<label>指標:
<select id="metricSelect"></select>
</label>
<div class="chart" id="chart"></div>
<div class="tip" id="tip"></div>
</div>
<script>
const DATA = __DATA__;
const tip = document.getElementById("tip");
function showTip(e, text) { tip.textContent = text; tip.style.opacity = 1;
  tip.style.left = (e.clientX + 12) + "px"; tip.style.top = (e.clientY + 12) + "px"; }
function hideTip() { tip.style.opacity = 0; }
const metricSelect = document.getElementById("metricSelect");
DATA.metrics.forEach(m => {
  const opt = document.createElement("option");
  opt.value = m.key; opt.textContent = m.label;
  metricSelect.appendChild(opt);
});
function quantile(sorted, p) {
  if (sorted.length === 1) return sorted[0];
  const idx = (sorted.length - 1) * p;
  const lo = Math.floor(idx), hi = Math.ceil(idx);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (idx - lo);
}
function stats(vals) {
  const s = [...vals].sort((a, b) => a - b);
  const n = s.length;
  const mean = s.reduce((a, b) => a + b, 0) / n;
  const variance = n > 1 ? s.reduce((a, b) => a + (b - mean) ** 2, 0) / (n - 1) : null;
  return {min: s[0], q1: quantile(s, 0.25), med: quantile(s, 0.5),
          q3: quantile(s, 0.75), max: s[n - 1], mean, variance, n};
}
function niceMax(v) {
  if (v <= 0) return 1;
  const exp = Math.floor(Math.log10(v));
  const base = Math.pow(10, exp);
  for (const m of [1, 2, 2.5, 5, 10]) { if (v <= m * base) return m * base; }
  return 10 * base;
}
const chart = document.getElementById("chart");
function render() {
  const key = metricSelect.value;
  const metric = DATA.metrics.find(m => m.key === key);
  const perCondition = DATA.conditions.map(c => ({c, entries: DATA.values[key][c] || []}));
  const maxV = niceMax(Math.max(1e-9, ...perCondition.flatMap(x => x.entries.map(o => o.v))));
  const y = v => (v / maxV) * 100;
  chart.innerHTML = "";
  const yaxis = document.createElement("div");
  yaxis.className = "yaxis";
  [0, 0.25, 0.5, 0.75, 1].forEach(f => {
    const tick = document.createElement("span");
    tick.className = "ytick";
    tick.style.bottom = (f * 100) + "%";
    tick.textContent = (maxV * f).toLocaleString(undefined, {maximumFractionDigits: 1});
    yaxis.appendChild(tick);
    const line = document.createElement("div");
    line.className = "gline";
    line.style.top = ((1 - f) * 260) + "px";
    chart.appendChild(line);
  });
  chart.appendChild(yaxis);
  perCondition.forEach(({c, entries}) => {
    const col = document.createElement("div");
    col.className = "col";
    const track = document.createElement("div");
    track.className = "vtrack";
    if (entries.length > 0) {
      const st = stats(entries.map(o => o.v));
      track.innerHTML = `
        <div class="vwhisker" style="bottom:${y(st.min)}%; height:${y(st.max) - y(st.min)}%"></div>
        <div class="vcap" style="bottom:${y(st.min)}%"></div>
        <div class="vcap" style="bottom:${y(st.max)}%"></div>
        <div class="vbox" style="bottom:${y(st.q1)}%; height:${Math.max(y(st.q3) - y(st.q1), 0.4)}%"></div>
        <div class="vmedian" style="bottom:${y(st.med)}%"></div>
        <div class="vmean" style="bottom:${y(st.mean)}%"></div>` +
        entries.map(o => `<span class="vpt" style="bottom:${y(o.v)}%" data-tip="${o.p}: ${o.v}${metric.unit}"></span>`).join("");
      track.addEventListener("mousemove", e => {
        const target = e.target.closest("[data-tip]");
        showTip(e, target ? target.dataset.tip :
          `${c} (n=${st.n})\n最小${st.min} / Q1 ${st.q1.toFixed(1)} / 中央値${st.med.toFixed(1)} / Q3 ${st.q3.toFixed(1)} / 最大${st.max}`);
      });
      track.addEventListener("mouseleave", hideTip);
      col.appendChild(track);
      const name = document.createElement("div");
      name.className = "cname";
      name.textContent = c;
      col.appendChild(name);
      const stat = document.createElement("div");
      stat.className = "cstat";
      stat.textContent = `μ=${st.mean.toFixed(1)}` +
        (st.variance === null ? "" : ` σ²=${st.variance.toFixed(1)}`);
      col.appendChild(stat);
    } else {
      col.appendChild(track);
      const name = document.createElement("div");
      name.className = "cname";
      name.textContent = c + "(データなし)";
      col.appendChild(name);
    }
    chart.appendChild(col);
  });
}
metricSelect.addEventListener("change", render);
render();
</script></body></html>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="参加者横断の条件比較箱ひげ図を生成")
    parser.add_argument(
        "--auto", metavar="DIR",
        help="DIR/<参加者ID>/chosaN/coding.json を自動収集",
    )
    parser.add_argument(
        "--participant", nargs="*", default=[], metavar="名前=DIR",
        help="参加者名=コーディングディレクトリ(chosaN/coding.json を含む)",
    )
    parser.add_argument("--output", required=True)
    parser.add_argument("--subtitle", default="")
    args = parser.parse_args(argv)

    participants: dict[str, Path] = {}
    if args.auto:
        parent = Path(args.auto)
        for child in sorted(parent.iterdir()) if parent.is_dir() else []:
            if child.is_dir():
                participants[child.name] = child
    for pair in args.participant:
        name, sep, path = pair.partition("=")
        if not sep:
            raise SystemExit(f"名前=DIR の形式で指定してください: {pair!r}")
        participants[name.strip()] = Path(path.strip())
    if not participants:
        raise SystemExit("--auto か --participant で参加者を1人以上指定してください")

    dataset = collect(participants)
    if not dataset["participants"]:
        raise SystemExit("有効な参加者データがありません")
    subtitle = args.subtitle or (
        f"参加者 {len(dataset['participants'])} 名"
        f"({', '.join(dataset['participants'])})/ 条件 調査1〜5"
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
