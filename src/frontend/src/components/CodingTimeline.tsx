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

// 会話と無言は相互排他の区間なので1本のレーンにまとめて表示する
const mergedLaneLabels: CodingIntervalLabel[] = ["会話", "無言"]
const separateLaneLabels: CodingIntervalLabel[] = ["AI説明", "AI応答", "システム停止"]

const CodingTimeline: React.FC<CodingTimelineProps> = ({ coding, duration, currentTime, onSeek }) => {
  const mergedIntervals = coding.intervals.filter((interval) =>
    (mergedLaneLabels as string[]).includes(interval.label),
  )
  const visibleSeparateLabels = separateLaneLabels.filter((label) =>
    coding.intervals.some((interval) => interval.label === label),
  )
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
        {mergedIntervals.length > 0 && (
          <div className="coding-lane" key="会話無言">
            <span className="coding-lane-label">
              <i className="coding-legend-swatch" style={{ background: intervalColors["会話"] }} />
              <i className="coding-legend-swatch" style={{ background: intervalColors["無言"] }} />
              会話/無言
            </span>
            <div className="coding-lane-track">
              {mergedIntervals.map((interval) => renderBand(interval, duration, onSeek))}
            </div>
          </div>
        )}
        {visibleSeparateLabels.map((label) => (
          <div className="coding-lane" key={label}>
            <span className="coding-lane-label">
              <i className="coding-legend-swatch" style={{ background: intervalColors[label] }} />
              {label}
            </span>
            <div className="coding-lane-track">
              {coding.intervals
                .filter((interval) => interval.label === label)
                .map((interval) => renderBand(interval, duration, onSeek))}
            </div>
          </div>
        ))}
        {coding.events.length > 0 && (
          <div className="coding-lane coding-event-lane">
            <span className="coding-lane-label">イベント</span>
            <div className="coding-lane-track">
              {coding.events.map((event) => (
                <button
                  type="button"
                  key={event.id}
                  className="coding-event-marker"
                  style={{
                    left: `${percent(event.time, duration)}%`,
                    background: eventColors[event.label] ?? "#f0a92e",
                  }}
                  onClick={(clickEvent) => {
                    clickEvent.stopPropagation()
                    onSeek(event.time)
                  }}
                  title={`${event.label} ${event.time.toFixed(1)}秒`}
                  aria-label={`${event.label} ${event.time.toFixed(1)}秒へ移動`}
                />
              ))}
            </div>
          </div>
        )}
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
