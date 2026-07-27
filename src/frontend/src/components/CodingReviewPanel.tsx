import { Download } from "lucide-react"
import type React from "react"
import { useMemo, useState } from "react"
import type {
  CodingData,
  CodingEvent,
  CodingEventLabel,
  CodingInterval,
  CodingIntervalLabel,
  CodingReview,
} from "../types"

interface CodingReviewPanelProps {
  coding: CodingData
  currentTime: number
  onSeek: (time: number) => void
  onChange: (coding: CodingData) => void
}

const intervalLabels: CodingIntervalLabel[] = ["会話", "無言", "AI説明", "AI応答", "システム停止"]
const eventLabels: CodingEventLabel[] = [
  "視覚障害者からの話題提示",
  "同行者からの話題提示",
  "視覚障害者から同行者への質問",
  "同行者から視覚障害者への質問",
  "AI情報の共有",
  "同行者からの周囲説明",
  "応答なし発話",
  "ガイド発話",
]

type ReviewStatus = CodingReview["status"]

interface ReviewRow {
  kind: "interval" | "event"
  index: number
  id: string
  label: CodingIntervalLabel | CodingEventLabel
  start: number
  end: number
  speaker?: string
  text?: string
  review: CodingReview
}

const formatTime = (seconds: number) => {
  const minutes = Math.floor(seconds / 60)
  const remainder = Math.floor(seconds % 60)
  return `${minutes}:${String(remainder).padStart(2, "0")}`
}

const CodingReviewPanel: React.FC<CodingReviewPanelProps> = ({ coding, currentTime, onSeek, onChange }) => {
  const [selectedLabel, setSelectedLabel] = useState("")

  const rows = useMemo<ReviewRow[]>(() => {
    const intervalRows = coding.intervals.map((interval, index) => ({
      kind: "interval" as const,
      index,
      id: interval.id,
      label: interval.label,
      start: interval.start,
      end: interval.end,
      review: interval.review,
    }))
    const eventRows = coding.events.map((event, index) => ({
      kind: "event" as const,
      index,
      id: event.id,
      label: event.label,
      start: event.time,
      end: event.end,
      speaker: event.speaker,
      text: event.text,
      review: event.review,
    }))
    return [...intervalRows, ...eventRows].sort((a, b) => a.start - b.start || a.end - b.end)
  }, [coding])

  const filteredRows = selectedLabel ? rows.filter((row) => row.label === selectedLabel) : rows
  const labels = [...new Set(rows.map((row) => row.label))]

  const updateInterval = (index: number, patch: Partial<CodingInterval>) => {
    onChange({
      ...coding,
      intervals: coding.intervals.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)),
    })
  }

  const updateEvent = (index: number, patch: Partial<CodingEvent>) => {
    onChange({
      ...coding,
      events: coding.events.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)),
    })
  }

  const updateReview = (row: ReviewRow, status: ReviewStatus | undefined, note?: string) => {
    const nextReview = {
      status: status === undefined ? row.review.status : status,
      note: note === undefined ? row.review.note : note,
    }
    if (row.kind === "interval") {
      updateInterval(row.index, { review: nextReview })
    } else {
      updateEvent(row.index, { review: nextReview })
    }
  }

  const updateNumber = (row: ReviewRow, field: "start" | "end", rawValue: string) => {
    const value = Number(rawValue)
    if (!Number.isFinite(value)) return
    if (row.kind === "interval") {
      updateInterval(row.index, field === "start" ? { start: value } : { end: value })
    } else {
      updateEvent(row.index, field === "start" ? { time: value } : { end: value })
    }
  }

  const exportReview = () => {
    const payload: CodingData = {
      ...coding,
      intervals: coding.intervals.map((item) => ({ ...item, review: { ...item.review } })),
      events: coding.events.map((item) => ({ ...item, review: { ...item.review } })),
    }
    const blob = new Blob([`${JSON.stringify(payload, null, 2)}\n`], { type: "application/json" })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = coding.audio.replace(/\.[^.]+$/, "") + ".review.json"
    anchor.click()
    URL.revokeObjectURL(url)
  }

  return (
    <section className="coding-review-panel" aria-label="コーディングレビュー">
      <div className="coding-review-header">
        <div>
          <strong>コーディングレビュー</strong>
          <span className="coding-review-count">{filteredRows.length}件</span>
        </div>
        <div className="coding-review-tools">
          <label>
            ラベル
            <select value={selectedLabel} onChange={(event) => setSelectedLabel(event.target.value)}>
              <option value="">すべて</option>
              {labels.map((label) => (
                <option value={label} key={label}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <button type="button" className="coding-export-button" onClick={exportReview}>
            <Download size={15} />
            エクスポート
          </button>
        </div>
      </div>
      <div className="coding-review-list">
        {filteredRows.map((row) => {
          const isActive = currentTime >= row.start && currentTime < row.end
          return (
            <article
              className={`coding-review-item ${isActive ? "active" : ""}`}
              key={`${row.kind}-${row.id}`}
              onClick={() => onSeek(row.start)}
            >
              <div className="coding-review-summary">
                <button type="button" className="coding-review-time" onClick={() => onSeek(row.start)}>
                  {formatTime(row.start)}
                </button>
                <select
                  aria-label="ラベル"
                  value={row.label}
                  onClick={(event) => event.stopPropagation()}
                  onChange={(event) => {
                    if (row.kind === "interval") {
                      updateInterval(row.index, { label: event.target.value as CodingIntervalLabel })
                    } else {
                      updateEvent(row.index, { label: event.target.value as CodingEventLabel })
                    }
                  }}
                >
                  {(row.kind === "interval" ? intervalLabels : eventLabels).map((label) => (
                    <option key={label} value={label}>
                      {label}
                    </option>
                  ))}
                </select>
                {row.speaker && <span className="coding-review-speaker">{row.speaker}</span>}
                {row.text && <span className="coding-review-text">{row.text}</span>}
              </div>
              <div className="coding-review-editors" onClick={(event) => event.stopPropagation()}>
                <label>
                  開始
                  <input
                    type="number"
                    min="0"
                    step="0.1"
                    value={row.start}
                    onChange={(event) => updateNumber(row, "start", event.target.value)}
                  />
                </label>
                <label>
                  終了
                  <input
                    type="number"
                    min="0"
                    step="0.1"
                    value={row.end}
                    onChange={(event) => updateNumber(row, "end", event.target.value)}
                  />
                </label>
                <div className="coding-review-status">
                  <button
                    type="button"
                    className={row.review.status === "confirmed" ? "selected confirmed" : ""}
                    aria-pressed={row.review.status === "confirmed"}
                    onClick={() =>
                      updateReview(row, row.review.status === "confirmed" ? null : "confirmed")
                    }
                  >
                    ✓確認
                  </button>
                  <button
                    type="button"
                    className={row.review.status === "needs_correction" ? "selected correction" : ""}
                    aria-pressed={row.review.status === "needs_correction"}
                    onClick={() =>
                      updateReview(
                        row,
                        row.review.status === "needs_correction" ? null : "needs_correction",
                      )
                    }
                  >
                    ✗要修正
                  </button>
                </div>
                <input
                  className="coding-review-note"
                  aria-label="レビューメモ"
                  placeholder="メモ"
                  value={row.review.note}
                  onChange={(event) => updateReview(row, undefined, event.target.value)}
                />
              </div>
            </article>
          )
        })}
      </div>
    </section>
  )
}

export default CodingReviewPanel
