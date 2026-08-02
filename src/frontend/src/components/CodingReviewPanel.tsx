import { Download, Plus, Trash2 } from "lucide-react"
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
  duration?: number
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
// スキーム表の併記ルール: 質問が新話題を開く場合は「話題提示」を、
// AI情報の共有には「話題提示」か「質問」を必ず併記する
const coLabelValues = ["話題提示", "質問"]
const surroundTag = "周囲の話題"
// スキーム表: 同行者からの周囲説明は 自発/質問応答 の属性記録が必須
const responseTypes = ["自発", "質問応答"]
const eventSpeakers: CodingEvent["speaker"][] = ["視覚障害者", "同行者", "実験者"]

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
  source?: string
  coLabels?: string[]
  tags?: string[]
  responseType?: string
  review: CodingReview
}

const formatTime = (seconds: number) => {
  const minutes = Math.floor(seconds / 60)
  const remainder = Math.floor(seconds % 60)
  return `${minutes}:${String(remainder).padStart(2, "0")}`
}

const eventCoLabels = (event: CodingEvent): string[] => {
  const raw = event.attrs?.co_labels
  return Array.isArray(raw) ? raw.filter((value): value is string => typeof value === "string") : []
}

const newRowId = (prefix: string) =>
  `${prefix}-hm-${Date.now().toString(36)}-${Math.floor(Math.random() * 46656).toString(36)}`

const CodingReviewPanel: React.FC<CodingReviewPanelProps> = ({
  coding,
  currentTime,
  duration,
  onSeek,
  onChange,
}) => {
  const [selectedLabel, setSelectedLabel] = useState("")
  const [addKind, setAddKind] = useState<"interval" | "event">("event")
  const [addIntervalLabel, setAddIntervalLabel] = useState<CodingIntervalLabel>("会話")
  const [addEventLabel, setAddEventLabel] = useState<CodingEventLabel>(eventLabels[0])
  const [addSpeaker, setAddSpeaker] = useState<CodingEvent["speaker"]>("視覚障害者")

  const rows = useMemo<ReviewRow[]>(() => {
    const intervalRows = coding.intervals.map((interval, index) => ({
      kind: "interval" as const,
      index,
      id: interval.id,
      label: interval.label,
      start: interval.start,
      end: interval.end,
      source: interval.source,
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
      source: event.source,
      coLabels: eventCoLabels(event),
      tags: event.tags ?? [],
      responseType:
        typeof event.attrs?.response_type === "string" ? event.attrs.response_type : undefined,
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
    // Number("") は 0 になる: 入力欄を消しただけで時刻が 0 に飛ばないよう空は無視
    if (rawValue.trim() === "") return
    const value = Number(rawValue)
    if (!Number.isFinite(value)) return
    if (row.kind === "interval") {
      updateInterval(row.index, field === "start" ? { start: value } : { end: value })
    } else {
      updateEvent(row.index, field === "start" ? { time: value } : { end: value })
    }
  }

  const toggleCoLabel = (row: ReviewRow, value: string) => {
    const event = coding.events[row.index]
    const current = eventCoLabels(event)
    const next = current.includes(value)
      ? current.filter((item) => item !== value)
      : [...current, value]
    updateEvent(row.index, { attrs: { ...event.attrs, co_labels: next } })
  }

  const toggleTag = (row: ReviewRow) => {
    const event = coding.events[row.index]
    const current = event.tags ?? []
    const next = current.includes(surroundTag)
      ? current.filter((item) => item !== surroundTag)
      : [...current, surroundTag]
    updateEvent(row.index, { tags: next })
  }

  const setResponseType = (row: ReviewRow, value: string) => {
    const event = coding.events[row.index]
    updateEvent(row.index, { attrs: { ...event.attrs, response_type: value } })
  }

  const addRow = () => {
    // 録音末尾でも start < end ≤ duration を満たすよう丸め込む(schemaの要求)
    const clampEnd = (value: number) =>
      duration && duration > 0 ? Math.min(value, duration) : value
    let start = Number(currentTime.toFixed(1))
    if (duration && duration > 0) {
      start = Math.min(start, Math.max(0, Number((duration - 0.5).toFixed(1))))
    }
    const review: CodingReview = { status: null, note: "" }
    if (addKind === "interval") {
      const interval: CodingInterval = {
        id: newRowId("iv"),
        label: addIntervalLabel,
        start,
        end: Number(clampEnd(start + 5).toFixed(1)),
        source: "human",
        note: "",
        review,
      }
      onChange({ ...coding, intervals: [...coding.intervals, interval] })
    } else {
      const event: CodingEvent = {
        id: newRowId("ev"),
        label: addEventLabel,
        time: start,
        end: Number(clampEnd(start + 3).toFixed(1)),
        speaker: addSpeaker,
        tags: [],
        attrs: {},
        text: "",
        note: "",
        source: "human",
        review,
      }
      onChange({ ...coding, events: [...coding.events, event] })
    }
    // ラベルフィルタ中でも追加した行がすぐ見えるようにフィルタを解除する
    setSelectedLabel("")
  }

  const removeRow = (row: ReviewRow) => {
    if (row.kind === "interval") {
      onChange({
        ...coding,
        intervals: coding.intervals.filter((_, itemIndex) => itemIndex !== row.index),
      })
    } else {
      onChange({
        ...coding,
        events: coding.events.filter((_, itemIndex) => itemIndex !== row.index),
      })
    }
  }

  const exportReview = () => {
    // schema は (start/time, end) の昇順を要求する。手動追加や時刻修正で
    // 順序が崩れていてもエクスポート時に整列して常に検証に通る形にする
    const payload: CodingData = {
      ...coding,
      intervals: [...coding.intervals]
        .sort((a, b) => a.start - b.start || a.end - b.end)
        .map((item) => ({ ...item, review: { ...item.review } })),
      events: [...coding.events]
        .sort((a, b) => a.time - b.time || a.end - b.end)
        .map((item) => ({ ...item, review: { ...item.review } })),
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
      <div className="coding-review-add">
        <span className="coding-review-add-title">ラベル追加</span>
        <select
          aria-label="追加する種別"
          value={addKind}
          onChange={(event) => setAddKind(event.target.value as "interval" | "event")}
        >
          <option value="event">イベント</option>
          <option value="interval">区間</option>
        </select>
        {addKind === "interval" ? (
          <select
            aria-label="追加するラベル"
            value={addIntervalLabel}
            onChange={(event) => setAddIntervalLabel(event.target.value as CodingIntervalLabel)}
          >
            {intervalLabels.map((label) => (
              <option key={label} value={label}>
                {label}
              </option>
            ))}
          </select>
        ) : (
          <>
            <select
              aria-label="追加するラベル"
              value={addEventLabel}
              onChange={(event) => setAddEventLabel(event.target.value as CodingEventLabel)}
            >
              {eventLabels.map((label) => (
                <option key={label} value={label}>
                  {label}
                </option>
              ))}
            </select>
            <select
              aria-label="話者"
              value={addSpeaker}
              onChange={(event) => setAddSpeaker(event.target.value as CodingEvent["speaker"])}
            >
              {eventSpeakers.map((speaker) => (
                <option key={speaker} value={speaker}>
                  {speaker}
                </option>
              ))}
            </select>
          </>
        )}
        <button type="button" className="coding-add-button" onClick={addRow}>
          <Plus size={14} />
          {formatTime(currentTime)} に追加
        </button>
      </div>
      <div className="coding-review-list">
        {filteredRows.map((row) => {
          const isActive = currentTime >= row.start && currentTime < row.end
          const isHuman = row.source === "human"
          const needsCoLabel =
            row.kind === "event" && row.label === "AI情報の共有" && (row.coLabels ?? []).length === 0
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
                <span className="coding-review-label-cell">
                  <span className={`coding-kind-badge ${row.kind}`}>
                    {row.kind === "interval" ? "区間" : "イベント"}
                  </span>
                  {isHuman && <span className="coding-kind-badge human">手動</span>}
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
                </span>
                {row.speaker && <span className="coding-review-speaker">{row.speaker}</span>}
                {row.kind === "event" && isHuman ? (
                  <input
                    className="coding-review-text-input"
                    aria-label="発話内容"
                    placeholder="発話内容"
                    value={row.text ?? ""}
                    onClick={(event) => event.stopPropagation()}
                    onChange={(event) => updateEvent(row.index, { text: event.target.value })}
                  />
                ) : (
                  row.text && <span className="coding-review-text">{row.text}</span>
                )}
              </div>
              {row.kind === "event" && (
                <div className="coding-review-chips" onClick={(event) => event.stopPropagation()}>
                  {coLabelValues.map((value) => (
                    <button
                      key={value}
                      type="button"
                      className={`coding-chip ${(row.coLabels ?? []).includes(value) ? "on" : ""}`}
                      aria-pressed={(row.coLabels ?? []).includes(value)}
                      onClick={() => toggleCoLabel(row, value)}
                    >
                      併記: {value}
                    </button>
                  ))}
                  <button
                    type="button"
                    className={`coding-chip tag ${(row.tags ?? []).includes(surroundTag) ? "on" : ""}`}
                    aria-pressed={(row.tags ?? []).includes(surroundTag)}
                    onClick={() => toggleTag(row)}
                  >
                    タグ: {surroundTag}
                  </button>
                  {row.label === "同行者からの周囲説明" && (
                    <>
                      {responseTypes.map((value) => (
                        <button
                          key={value}
                          type="button"
                          className={`coding-chip ${row.responseType === value ? "on" : ""}`}
                          aria-pressed={row.responseType === value}
                          onClick={() => setResponseType(row, value)}
                        >
                          属性: {value}
                        </button>
                      ))}
                      {!row.responseType && (
                        <span className="coding-chip-warning">属性必須(自発か質問応答)</span>
                      )}
                    </>
                  )}
                  {needsCoLabel && <span className="coding-chip-warning">併記必須(話題提示か質問)</span>}
                </div>
              )}
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
                  {isHuman && (
                    <button
                      type="button"
                      className="coding-row-delete"
                      aria-label="この行を削除"
                      onClick={() => removeRow(row)}
                    >
                      <Trash2 size={13} />
                    </button>
                  )}
                </div>
                <input
                  className="coding-review-note"
                  aria-label="レビューメモ"
                  placeholder="メモ"
                  value={row.review.note}
                  onChange={(event) => updateReview(row, undefined, event.target.value)}
                />
                {row.end <= row.start && (
                  <span className="coding-chip-warning coding-time-warning">
                    時刻が逆転しています(終了は開始より後にする)
                  </span>
                )}
              </div>
            </article>
          )
        })}
      </div>
    </section>
  )
}

export default CodingReviewPanel
