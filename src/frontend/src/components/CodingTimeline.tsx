import type React from "react"
import type { CodingData, CodingIntervalLabel } from "../types"

interface CodingTimelineProps {
  coding: CodingData
  duration: number
  onSeek: (time: number) => void
}

const intervalLabels: CodingIntervalLabel[] = ["会話", "無言", "AI説明", "AI応答", "システム停止"]

const percent = (value: number, duration: number) => {
  if (duration <= 0) return 0
  return Math.max(0, Math.min(100, (value / duration) * 100))
}

const CodingTimeline: React.FC<CodingTimelineProps> = ({ coding, duration, onSeek }) => {
  const visibleLabels = intervalLabels.filter((label) =>
    coding.intervals.some((interval) => interval.label === label),
  )

  return (
    <div className="coding-timeline" aria-label="コーディングタイムライン">
      {visibleLabels.map((label) => (
        <div className="coding-lane" key={label}>
          <span className="coding-lane-label">{label}</span>
          <div className="coding-lane-track">
            {coding.intervals
              .filter((interval) => interval.label === label)
              .map((interval) => {
                const left = percent(interval.start, duration)
                const right = percent(interval.end, duration)
                return (
                  <button
                    type="button"
                    key={interval.id}
                    className={`coding-band coding-band-${label}`}
                    style={{ left: `${left}%`, width: `${Math.max(right - left, 0.15)}%` }}
                    onClick={() => onSeek(interval.start)}
                    title={`${label} ${interval.start.toFixed(1)}–${interval.end.toFixed(1)}秒`}
                    aria-label={`${label} ${interval.start.toFixed(1)}秒へ移動`}
                  />
                )
              })}
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
                style={{ left: `${percent(event.time, duration)}%` }}
                onClick={() => onSeek(event.time)}
                title={`${event.label} ${event.time.toFixed(1)}秒`}
                aria-label={`${event.label} ${event.time.toFixed(1)}秒へ移動`}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default CodingTimeline
