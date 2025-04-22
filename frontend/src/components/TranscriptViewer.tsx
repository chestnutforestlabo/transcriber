"use client"

import { useRef, useEffect, useState } from "react"
import type React from "react"
import type { TranscriptEntry } from "../types"

interface TranscriptViewerProps {
  transcript: TranscriptEntry[]
  currentTime: number
  onJumpToTime: (time: number) => void
  speakerMapping: Record<string, string>
  onTranscriptEdit: (index: number, newText: string) => void
}

const TranscriptViewer: React.FC<TranscriptViewerProps> = ({
  transcript,
  currentTime,
  onJumpToTime,
  speakerMapping,
  onTranscriptEdit,
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const activeEntryRef = useRef<HTMLDivElement>(null)
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null)
  const [editingIndex, setEditingIndex] = useState<number | null>(null)
  const [editText, setEditText] = useState("")

  // Find the currently active transcript entry
  const activeEntryIndex = transcript.findIndex((entry) => currentTime > entry.start && currentTime < entry.end)

  // Scroll to active entry when it changes
  useEffect(() => {
    if (activeEntryRef.current && containerRef.current) {
      activeEntryRef.current.scrollIntoView({
        behavior: "smooth",
        block: "center",
      })
    }
  }, [activeEntryIndex])

  // Format time as MM:SS
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, "0")}`
  }

  // Handle copy to clipboard
  const handleCopy = (text: string) => {
    navigator.clipboard
      .writeText(text)
      .then(() => {
        console.log("Text copied to clipboard")
      })
      .catch((err) => {
        console.error("Failed to copy text: ", err)
      })
  }

  // Handle edit mode
  const handleEditStart = (index: number, text: string) => {
    setEditingIndex(index)
    setEditText(text)
  }

  // Handle edit save
  const handleEditSave = (index: number) => {
    onTranscriptEdit(index, editText)
    setEditingIndex(null)
  }

  // Handle edit cancel
  const handleEditCancel = () => {
    setEditingIndex(null)
  }

  return (
    <div className="transcript-viewer" ref={containerRef}>
      {transcript.map((entry, index) => {
        const isActive = currentTime >= entry.start && currentTime < entry.end
        const isHovered = hoveredIndex === index
        const isEditing = editingIndex === index
        const displaySpeaker = entry.speaker ? speakerMapping[entry.speaker] || entry.speaker : "null"

        return (
          <div
            key={index}
            ref={isActive ? activeEntryRef : null}
            className={`transcript-entry ${isActive ? "active" : ""}`}
            onMouseEnter={() => setHoveredIndex(index)}
            onMouseLeave={() => setHoveredIndex(null)}
            onClick={() => !isEditing && onJumpToTime(entry.start)}
          >
            {isHovered && !isEditing && (
              <div className="transcript-actions">
                <button
                  className="transcript-action-btn edit"
                  onClick={(e) => {
                    e.stopPropagation()
                    handleEditStart(index, entry.text)
                  }}
                >
                  Edit
                </button>
                <button
                  className="transcript-action-btn copy"
                  onClick={(e) => {
                    e.stopPropagation()
                    handleCopy(entry.text)
                  }}
                >
                  Copy
                </button>
              </div>
            )}
            <div className="transcript-time">{formatTime(entry.start)}</div>
            <div className="transcript-speaker">{displaySpeaker}</div>
            {isEditing ? (
              <div className="transcript-edit-container" onClick={(e) => e.stopPropagation()}>
                <textarea
                  className="transcript-edit-textarea"
                  value={editText}
                  onChange={(e) => setEditText(e.target.value)}
                  autoFocus
                />
                <div className="transcript-edit-actions">
                  <button className="transcript-edit-btn save" onClick={() => handleEditSave(index)}>
                    Save
                  </button>
                  <button className="transcript-edit-btn cancel" onClick={handleEditCancel}>
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div className="transcript-text">{entry.text}</div>
            )}
          </div>
        )
      })}
    </div>
  )
}

export default TranscriptViewer