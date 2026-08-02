import type React from "react"
import type { CodingData, CodingEventLabel, CodingIntervalLabel } from "../types"

interface CodingTimelineProps {
  coding: CodingData
  duration: number
  currentTime?: number
  onSeek: (time: number) => void
}

// 区間・イベントとも「どのラベルか」が一目で分かるようラベルごとに固定色を割り当てる
const intervalColors: Record<CodingIntervalLabel, string> = {
  会話: "#2a78d6",
  無言: "#c2c9d0",
  AI説明: "#1baf7a",
  AI応答: "#eda100",
  システム停止: "#e87ba4",
}

const eventLabelOrder: CodingEventLabel[] = [
  "視覚障害者からの話題提示",
  "同行者からの話題提示",
  "視覚障害者から同行者への質問",
  "同行者から視覚障害者への質問",
  "AI情報の共有",
  "同行者からの周囲説明",
  "応答なし発話",
  "ガイド発話",
]

const eventColors: Record<CodingEventLabel, string> = {
  視覚障害者からの話題提示: "#1f77b4",
  同行者からの話題提示: "#9467bd",
  視覚障害者から同行者への質問: "#17becf",
  同行者から視覚障害者への質問: "#e377c2",
  AI情報の共有: "#d62728",
  同行者からの周囲説明: "#2ca02c",
  応答なし発話: "#7f7f7f",
  ガイド発話: "#bc9d22",
}

// .coding-lane の grid-template-columns 先頭(ラベル列)と揃えること
const LABEL_COLUMN_PX = 82

const percent = (value: number, duration: number) => {
  if (duration <= 0) return 0
  return Math.max(0, Math.min(100, (value / duration) * 100))
}

// 時間の重なる(または見た目上つぶれる)イベントを別の行へ振り分ける貪欲パッキング。
// 戻り値: イベントid→行番号 と 必要行数
const packEventRows = (events: CodingData["events"], duration: number) => {
  const minSpan = duration > 0 ? duration * 0.012 : 1
  const sorted = [...events].sort((a, b) => a.time - b.time || a.end - b.end)
  const rowEnds: number[] = []
  const rowById = new Map<string, number>()
  for (const event of sorted) {
    const visualEnd = Math.max(event.end, event.time + minSpan)
    let row = rowEnds.findIndex((end) => end <= event.time)
    if (row === -1) {
      row = rowEnds.length
      rowEnds.push(visualEnd)
    } else {
      rowEnds[row] = visualEnd
    }
    rowById.set(event.id, row)
  }
  return { rowById, rowCount: Math.max(1, rowEnds.length) }
}

const renderBand = (
  interval: CodingData["intervals"][number],
  duration: number,
  onSeek: (time: number) => void,
) => {
  const left = percent(interval.start, duration)
  const right = percent(interval.end, duration)
  return (
    <button
      type="button"
      key={interval.id}
      className="coding-band"
      style={{
        left: `${left}%`,
        width: `${Math.max(right - left, 0.15)}%`,
        background: intervalColors[interval.label],
      }}
      onClick={(clickEvent) => {
        clickEvent.stopPropagation()
        onSeek(interval.start)
      }}
      title={`${interval.label} ${interval.start.toFixed(1)}–${interval.end.toFixed(1)}秒`}
      aria-label={`${interval.label} ${interval.start.toFixed(1)}秒へ移動`}
    />
  )
}

// 相互排他な区間は1本のレーンにまとめる: 人間側(会話/無言)と AI側(説明/応答/停止)
const laneGroups: { key: string; title: string; labels: CodingIntervalLabel[] }[] = [
  { key: "human", title: "会話/無言", labels: ["会話", "無言"] },
  { key: "ai", title: "AI/停止", labels: ["AI説明", "AI応答", "システム停止"] },
]

const CodingTimeline: React.FC<CodingTimelineProps> = ({ coding, duration, currentTime, onSeek }) => {
  const visibleGroups = laneGroups
    .map((group) => ({
      ...group,
      presentLabels: group.labels.filter((label) =>
        coding.intervals.some((interval) => interval.label === label),
      ),
      intervals: coding.intervals.filter((interval) =>
        (group.labels as string[]).includes(interval.label),
      ),
    }))
    .filter((group) => group.intervals.length > 0)
  const visibleEventLabels = eventLabelOrder.filter((label) =>
    coding.events.some((event) => event.label === label),
  )

  // 波形を廃止したぶん、レーンの空白部クリックでシークできるようにする
  const seekFromTrackClick = (event: React.MouseEvent<HTMLDivElement>) => {
    if (duration <= 0) return
    const rect = event.currentTarget.getBoundingClientRect()
    const fraction = (event.clientX - rect.left - LABEL_COLUMN_PX) / (rect.width - LABEL_COLUMN_PX)
    if (fraction < 0 || fraction > 1) return
    onSeek(fraction * duration)
  }

  return (
    <div className="coding-timeline" aria-label="コーディングタイムライン">
      <div className="coding-timeline-lanes" onClick={seekFromTrackClick}>
        {visibleGroups.map((group) => (
          <div className="coding-lane" key={group.key}>
            <span className="coding-lane-label">
              {group.presentLabels.map((label) => (
                <i
                  key={label}
                  className="coding-legend-swatch"
                  style={{ background: intervalColors[label] }}
                />
              ))}
              {group.title}
            </span>
            <div className="coding-lane-track">
              {group.intervals.map((interval) => renderBand(interval, duration, onSeek))}
            </div>
          </div>
        ))}
        {coding.events.length > 0 &&
          (() => {
            const { rowById, rowCount } = packEventRows(coding.events, duration)
            const laneHeight = rowCount * 14 + 4
            return (
              <div
                className="coding-lane coding-event-lane"
                style={{ height: laneHeight, maxHeight: laneHeight }}
              >
                <span className="coding-lane-label">イベント</span>
                <div className="coding-lane-track">
                  {coding.events.map((event) => {
                    const row = rowById.get(event.id) ?? 0
                    const spanPct =
                      percent(event.end, duration) - percent(event.time, duration)
                    return (
                      <button
                        type="button"
                        key={event.id}
                        className="coding-event-marker"
                        style={{
                          left: `${percent(event.time, duration)}%`,
                          width: `max(9px, ${Math.max(spanPct, 0)}%)`,
                          top: `calc(${(row / rowCount) * 100}% + 1px)`,
                          height: `calc(${100 / rowCount}% - 2px)`,
                          minHeight: 0,
                          margin: 0,
                          transform: "none",
                          background: eventColors[event.label] ?? "#f0a92e",
                        }}
                        onClick={(clickEvent) => {
                          clickEvent.stopPropagation()
                          onSeek(event.time)
                        }}
                        title={`${event.label} ${event.time.toFixed(1)}–${event.end.toFixed(1)}秒${event.text ? ` ${event.text}` : ""}`}
                        aria-label={`${event.label} ${event.time.toFixed(1)}秒へ移動`}
                      />
                    )
                  })}
                </div>
              </div>
            )
          })()}
        {duration > 0 && currentTime !== undefined && (
          <div
            className="coding-playhead"
            style={{
              left: `calc(${LABEL_COLUMN_PX}px + (100% - ${LABEL_COLUMN_PX}px) * ${
                percent(currentTime, duration) / 100
              })`,
            }}
          />
        )}
      </div>
      {visibleEventLabels.length > 0 && (
        <div className="coding-legend">
          {visibleEventLabels.map((label) => (
            <span className="coding-legend-item" key={label}>
              <i className="coding-legend-swatch" style={{ background: eventColors[label] }} />
              {label}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

export default CodingTimeline
