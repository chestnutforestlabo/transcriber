"use client"

import type React from "react"
import { useRef, useEffect, useState } from "react"
import { Edit, Copy, Bookmark, Save, X } from "lucide-react"

interface TranscriptEntry {
  time?: string
  start: number
  end: number
  speaker: string
  text: string
}

interface TranscriptViewerProps {
  transcript: TranscriptEntry[]
  currentTime: number
  onJumpToTime: (time: number) => void
  speakerMapping: Record<string, string>
  onTranscriptEdit: (index: number, newText: string) => void
  selectedEntryIndex: number | null
  onSelectEntry: (index: number | null) => void
  onBookmarkEntry: (index: number) => void
}

const TranscriptViewer: React.FC<TranscriptViewerProps> = ({
  transcript,
  currentTime,
  onJumpToTime,
  speakerMapping,
  onTranscriptEdit,
  selectedEntryIndex,
  onSelectEntry,
  onBookmarkEntry,
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const activeEntryRef = useRef<HTMLDivElement>(null)
  const editContainerRef = useRef<HTMLDivElement>(null)
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null)
  const [editingIndex, setEditingIndex] = useState<number | null>(null)
  const [editText, setEditText] = useState("")
  const [autoScroll, setAutoScroll] = useState(true)
  const lastActiveIndexRef = useRef<number>(-1)

  // Find the currently active transcript entry based on current time
  const activeEntryIndex = transcript.findIndex((entry) => currentTime >= entry.start && currentTime < entry.end)

  // Scroll to active entry when it changes
  useEffect(() => {
    if (activeEntryIndex !== -1 && activeEntryIndex !== lastActiveIndexRef.current) {
      lastActiveIndexRef.current = activeEntryIndex

      if (activeEntryRef.current && containerRef.current && autoScroll) {
        activeEntryRef.current.scrollIntoView({
          behavior: "smooth",
          block: "center",
        })
      }
    }
  }, [activeEntryIndex, autoScroll])

  // Add click outside listener when in edit mode
  useEffect(() => {
    if (editingIndex !== null) {
      const handleClickOutside = (event: MouseEvent) => {
        if (editContainerRef.current && !editContainerRef.current.contains(event.target as Node)) {
          // Click was outside the edit container, exit edit mode
          setEditingIndex(null)
        }
      }

      // Add the event listener
      document.addEventListener("mousedown", handleClickOutside)

      // Clean up
      return () => {
        document.removeEventListener("mousedown", handleClickOutside)
      }
    }
  }, [editingIndex])

  // Format time as MM:SS
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, "0")}`
  }

  // Handle copy to clipboard
  const handleCopy = (text: string, e: React.MouseEvent) => {
    e.stopPropagation()
    navigator.clipboard.writeText(text)
  }

  // Handle double click to edit
  const handleDoubleClick = (index: number, text: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setEditingIndex(index)
    setEditText(text)
  }

  // Handle edit button click
  const handleEditClick = (index: number, text: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setEditingIndex(index)
    setEditText(text)
  }

  // Handle edit save
  const handleEditSave = (index: number, e: React.MouseEvent) => {
    e.stopPropagation()
    onTranscriptEdit(index, editText)
    setEditingIndex(null)
  }

  // Handle edit cancel
  const handleEditCancel = (e: React.MouseEvent) => {
    e.stopPropagation()
    setEditingIndex(null)
  }

  // トランスクリプトエントリをクリックしたときのハンドラ
  const handleEntryClick = (entry: TranscriptEntry, index: number, e: React.MouseEvent) => {
    if (editingIndex !== null) return // 編集中は何もしない

    e.preventDefault()
    e.stopPropagation()

    console.log("Transcript entry clicked, jumping to time:", entry.start)

    // クリックしたエントリを選択状態にする
    onSelectEntry(index)

    // 該当時間にジャンプ - 正確に開始時刻から再生するために少しだけ前にする（0.01秒）
    // 直前のトランスクリプトが含まれないように、厳密に開始時刻を設定
    onJumpToTime(entry.start)

    // 一時的に自動スクロールを無効化（ユーザーが手動でクリックしたため）
    setAutoScroll(false)

    // 少し遅延して自動スクロールを再度有効化
    setTimeout(() => {
      setAutoScroll(true)
    }, 2000)
  }

  return (
    <div className="transcript-viewer" ref={containerRef}>
      {transcript.map((entry, index) => {
        // Only highlight the entry if it's the selected entry (from clicking)
        // OR if it's the active entry (from playback) AND there's no selected entry
        const isActive = currentTime >= entry.start && currentTime < entry.end
        const isHighlighted = selectedEntryIndex === index || (isActive && selectedEntryIndex === null)
        const isHovered = hoveredIndex === index
        const isEditing = editingIndex === index
        const displaySpeaker = entry.speaker ? speakerMapping[entry.speaker] || entry.speaker : "null"

        return (
          <div
            key={index}
            ref={isActive ? activeEntryRef : null}
            className={`transcript-entry ${isHighlighted ? "active" : ""} ${isEditing ? "editing" : ""}`}
            onMouseEnter={() => setHoveredIndex(index)}
            onMouseLeave={() => setHoveredIndex(null)}
            onClick={(e) => !isEditing && handleEntryClick(entry, index, e)}
            onDoubleClick={(e) => handleDoubleClick(index, entry.text, e)}
          >
            <div className="transcript-time">{formatTime(entry.start)}</div>
            <div className="transcript-speaker">{displaySpeaker}</div>

            {isEditing ? (
              <div className="transcript-edit-container" onClick={(e) => e.stopPropagation()} ref={editContainerRef}>
                <textarea
                  className="transcript-edit-textarea"
                  value={editText}
                  onChange={(e) => setEditText(e.target.value)}
                  autoFocus
                />
                <div className="transcript-edit-actions">
                  <button
                    className="transcript-action-btn save-btn"
                    onClick={(e) => handleEditSave(index, e)}
                    title="Save"
                  >
                    <Save size={16} />
                  </button>
                  <button className="transcript-action-btn cancel-btn" onClick={handleEditCancel} title="Cancel">
                    <X size={16} />
                  </button>
                </div>
              </div>
            ) : (
              <div className="transcript-text">{entry.text}</div>
            )}

            {isHovered && !isEditing && (
              <div className="transcript-actions">
                <button
                  className="transcript-action-btn"
                  onClick={(e) => handleEditClick(index, entry.text, e)}
                  title="Edit"
                >
                  <Edit size={16} />
                </button>
                <button className="transcript-action-btn" onClick={(e) => handleCopy(entry.text, e)} title="Copy">
                  <Copy size={16} />
                </button>
                <button className="transcript-action-btn" onClick={(e) => onBookmarkEntry(index)} title="Bookmark">
                  <Bookmark size={16} />
                </button>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

export default TranscriptViewer