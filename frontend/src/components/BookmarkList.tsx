"use client"

import { useState } from "react"
import type React from "react"
import type { Bookmark } from "../types"

interface BookmarkListProps {
  bookmarks: Bookmark[]
  onJumpToBookmark: (audioFile: string, entryIndex: number, time: number) => void
  onRemoveBookmark: (bookmarkIndex: number) => void
  currentAudioFile: string
}

const BookmarkList: React.FC<BookmarkListProps> = ({
  bookmarks,
  onJumpToBookmark,
  onRemoveBookmark,
  currentAudioFile,
}) => {
  const [expandedBookmark, setExpandedBookmark] = useState<number | null>(null)

  // Format time as MM:SS
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, "0")}`
  }

  // Format date as YYYY-MM-DD HH:MM
  const formatDate = (timestamp: number) => {
    const date = new Date(timestamp)
    return `${date.toLocaleDateString()} ${date.toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
    })}`
  }

  // Toggle expanded state for a bookmark
  const toggleExpand = (index: number) => {
    setExpandedBookmark(expandedBookmark === index ? null : index)
  }

  return (
    <div className="bookmark-list">
      <h3>Bookmarks</h3>
      <div className="bookmark-items">
        {bookmarks.length === 0 ? (
          <div className="no-bookmarks">No bookmarks yet</div>
        ) : (
          bookmarks.map((bookmark, index) => (
            <div
              key={index}
              className={`bookmark-item ${bookmark.audioFile === currentAudioFile ? "current-file" : ""}`}
            >
              <div className="bookmark-header" onClick={() => toggleExpand(index)}>
                <div className="bookmark-file">{bookmark.audioFile}</div>
                <div className="bookmark-time">{formatTime(bookmark.entry.start)}</div>
                <div className="bookmark-actions">
                  <button
                    className="bookmark-jump-btn"
                    onClick={(e) => {
                      e.stopPropagation()
                      onJumpToBookmark(bookmark.audioFile, bookmark.entryIndex, bookmark.entry.start)
                    }}
                    title="Jump to this bookmark"
                  >
                    Jump
                  </button>
                  <button
                    className="bookmark-remove-btn"
                    onClick={(e) => {
                      e.stopPropagation()
                      onRemoveBookmark(index)
                    }}
                    title="Remove bookmark"
                  >
                    &times;
                  </button>
                </div>
              </div>
              {expandedBookmark === index && (
                <div className="bookmark-details">
                  <div className="bookmark-speaker">
                    <strong>Speaker:</strong> {bookmark.entry.speaker || "Unknown"}
                  </div>
                  <div className="bookmark-text">{bookmark.entry.text}</div>
                  <div className="bookmark-timestamp">
                    <small>Bookmarked: {formatDate(bookmark.timestamp)}</small>
                  </div>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}

export default BookmarkList