"use client"

import type React from "react"
import { useRef, useEffect } from "react"
import type { TranscriptEntry } from "../types"

interface TranscriptViewerProps {
  transcript: TranscriptEntry[]
  currentTime: number
  onJumpToTime: (time: number) => void
}

const TranscriptViewer: React.FC<TranscriptViewerProps> = ({ transcript, currentTime, onJumpToTime }) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const activeEntryRef = useRef<HTMLDivElement>(null)

  // Find the currently active transcript entry
  const activeEntryIndex = transcript.findIndex((entry) => currentTime >= entry.start && currentTime <= entry.end)

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

  return (
    <div className="transcript-viewer" ref={containerRef}>
      {transcript.map((entry, index) => {
        const isActive = currentTime >= entry.start && currentTime <= entry.end

        return (
          <div
            key={index}
            ref={isActive ? activeEntryRef : null}
            className={`transcript-entry ${isActive ? "active" : ""}`}
            onClick={() => onJumpToTime(entry.start)}
          >
            <div className="transcript-time">{formatTime(entry.start)}</div>
            <div className="transcript-speaker">{entry.speaker || "null"}</div>
            <div className="transcript-text">{entry.text}</div>
          </div>
        )
      })}
    </div>
  )
}

export default TranscriptViewer