import type React from "react"
import type { CodingData, CodingEventLabel, CodingIntervalLabel } from "../types"

interface CodingTimelineProps {
  coding: CodingData
  duration: number
  currentTime?: number
  onSeek: (time: number) => void
}

// 区間は「どのラベルか」が一目で分かるようラベルごとに固定色を割り当てる
const intervalColors: Record<CodingIntervalLabel, string> = {
  会話: "#2a78d6",
  無言: "#c2c9d0",
  AI説明: "#1baf7a",
  AI応答: "#eda100",
  システム停止: "#e87ba4",
}

// 相互排他な区間は1本のレーンにまとめる: 人間側(会話/無言)と Q&A使用窓/停止。
// AI説明(自発ナレーション)は録音に入らないため廃止(旧データにあっても表示しない)
const laneGroups: { key: string; title: string; labels: CodingIntervalLabel[] }[] = [
  { key: "human", title: "会話/無言", labels: ["会話", "無言"] },
  { key: "ai", title: "Q&A/停止", labels: ["AI応答", "システム停止"] },
]

// イベントは話者ごとのレーンに分かれるため、「誰から」はレーンで表現される。
// 色はラベルの種類(話題提示/質問/…)だけを表し、方向違いの同種ラベルは同色
const categoryByLabel: Record<CodingEventLabel, string> = {
  視覚障害者からの話題提示: "話題提示",
  同行者からの話題提示: "話題提示",
  視覚障害者から同行者への質問: "質問",
  同行者から視覚障害者への質問: "質問",
  AI情報の共有: "AI情報の共有",
  同行者からの周囲説明: "周囲説明",
  応答なし発話: "応答なし発話",
  ガイド発話: "ガイド発話",
}

const categoryOrder = ["話題提示", "質問", "AI情報の共有", "周囲説明", "応答なし発話", "ガイド発話"]

const categoryColors: Record<string, string> = {
  話題提示: "#1f77b4",
  質問: "#17becf",
  AI情報の共有: "#d62728",
  周囲説明: "#2ca02c",
  応答なし発話: "#7f7f7f",
  ガイド発話: "#bc9d22",
}

const speakerLaneOrder = ["視覚障害者", "同行者", "実験者"]

// .coding-lane の grid-template-columns 先頭(ラベル列)と揃えること
const LABEL_COLUMN_PX = 82

const percent = (value: number, duration: number) => {
  if (duration <= 0) return 0
  return Math.max(0, Math.min(100, (value / duration) * 100))
}

type EventCluster = {
  id: string
  start: number
  end: number
  events: CodingData["events"]
}

// 時間が重なる(または見た目上つぶれる)イベントを1つのピルへまとめる。
// ピル内は色セグメントに分かれ、重なりの内訳が一目で見える
const clusterEvents = (events: CodingData["events"], duration: number): EventCluster[] => {
  const minSpan = duration > 0 ? duration * 0.012 : 1
  const sorted = [...events].sort((a, b) => a.time - b.time || a.end - b.end)
  const clusters: EventCluster[] = []
  for (const event of sorted) {
    const visualEnd = Math.max(event.end, event.time + minSpan)
    const last = clusters[clusters.length - 1]
    if (last && event.time < last.end) {
      last.end = Math.max(last.end, visualEnd)
      last.events = [...last.events, event]
    } else {
      clusters.push({ id: event.id, start: event.time, end: visualEnd, events: [event] })
    }
  }
  return clusters
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
  const visibleSpeakers = speakerLaneOrder.filter((speaker) =>
    coding.events.some((event) => event.speaker === speaker),
  )
  const visibleCategories = categoryOrder.filter((category) =>
    coding.events.some((event) => categoryByLabel[event.label] === category),
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
        {visibleSpeakers.map((speaker) => (
          <div className="coding-lane coding-event-lane" key={speaker}>
            <span className="coding-lane-label">{speaker}</span>
            <div className="coding-lane-track">
              {clusterEvents(
                coding.events.filter((event) => event.speaker === speaker),
                duration,
              ).map((cluster) => {
                const left = percent(cluster.start, duration)
                const width = percent(cluster.end, duration) - left
                return (
                  <button
                    type="button"
                    key={cluster.id}
                    className="coding-event-pill"
                    style={{ left: `${left}%`, width: `max(9px, ${Math.max(width, 0)}%)` }}
                    onClick={(clickEvent) => {
                      clickEvent.stopPropagation()
                      onSeek(cluster.start)
                    }}
                    title={cluster.events
                      .map(
                        (event) =>
                          `${event.label} ${event.time.toFixed(1)}–${event.end.toFixed(1)}秒${
                            event.text ? ` ${event.text}` : ""
                          }`,
                      )
                      .join("\n")}
                    aria-label={`${cluster.events.length}件のイベント ${cluster.start.toFixed(1)}秒へ移動`}
                  >
                    {cluster.events.map((event) => (
                      <span
                        key={event.id}
                        className="coding-event-seg"
                        style={{
                          background:
                            categoryColors[categoryByLabel[event.label]] ?? "#f0a92e",
                        }}
                      />
                    ))}
                  </button>
                )
              })}
            </div>
          </div>
        ))}
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
      {visibleCategories.length > 0 && (
        <div className="coding-legend">
          {visibleCategories.map((category) => (
            <span className="coding-legend-item" key={category}>
              <i className="coding-legend-swatch" style={{ background: categoryColors[category] }} />
              {category}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

export default CodingTimeline
