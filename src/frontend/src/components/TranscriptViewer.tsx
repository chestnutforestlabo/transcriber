"use client"

import React, { useRef, useEffect, useState } from "react"
import { Edit, Copy, Bookmark, Save, X, Plus, Trash2 } from "lucide-react"
import { createPortal } from "react-dom"

export interface TranscriptEntry {
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
  onTranscriptEdit: (index: number, patch: Partial<TranscriptEntry>) => void
  selectedEntryIndex: number | null
  onSelectEntry: (index: number | null) => void
  onAddEntryBetween: (index: number) => void
  onBookmarkEntry: (index: number) => void
  onDeleteEntry: (index: number) => void
  bookmarks: Bookmark[]
  currentAudioFile: string
}

const secToClock = (sec: number) => `${Math.floor(sec / 60)}:${String(Math.floor(sec % 60)).padStart(2, "0")}`

const clockToSec = (clock: string) => {
  const [m, s] = clock.split(":")
  return +m * 60 + +s
}

const TranscriptViewer: React.FC<TranscriptViewerProps> = ({
  transcript,
  currentTime,
  onJumpToTime,
  speakerMapping,
  onTranscriptEdit,
  selectedEntryIndex,
  onSelectEntry,
  onAddEntryBetween,
  onBookmarkEntry,
  onDeleteEntry,
  bookmarks,
  currentAudioFile,
}) => {
  console.log("TranscriptViewer received speakerMapping:", speakerMapping)

  const containerRef = useRef<HTMLDivElement>(null)
  const activeEntryRef = useRef<HTMLDivElement>(null)
  const editContainerRef = useRef<HTMLDivElement>(null)
  const speakerButtonRef = useRef<HTMLButtonElement>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null)
  const [hoveredBoundaryIndex, setHoveredBoundaryIndex] = useState<number | null>(null)

  const [editingIndex, setEditingIndex] = useState<number | null>(null)

  const [editText, setEditText] = useState("")
  const [editSpeaker, setEditSpeaker] = useState("")
  const [editStartClock, setEditStartClock] = useState("")

  const [autoScroll, setAutoScroll] = useState(true)
  const lastActiveIndexRef = useRef<number>(-1)

  const [speakerDropdownOpen, setSpeakerDropdownOpen] = useState(false)
  const [dropdownPosition, setDropdownPosition] = useState({ top: 0, left: 0, width: 0 })
  const [isDropdownItemClicked, setIsDropdownItemClicked] = useState(false)

  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleteIndex, setDeleteIndex] = useState<number | null>(null)

  const activeEntryIndex = transcript.findIndex((entry) => currentTime >= entry.start && currentTime < entry.end)

  useEffect(() => {
    if (activeEntryIndex !== -1 && activeEntryIndex !== lastActiveIndexRef.current) {
      lastActiveIndexRef.current = activeEntryIndex
      if (activeEntryRef.current && containerRef.current && autoScroll) {
        activeEntryRef.current.scrollIntoView({ behavior: "smooth", block: "center" })
      }
    }
  }, [activeEntryIndex, autoScroll])

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (speakerDropdownOpen) {
        const dropdownElement = document.getElementById("speaker-dropdown-portal")
        const speakerButtonElement = speakerButtonRef.current

        if (
          (!speakerButtonElement || !speakerButtonElement.contains(e.target as Node)) &&
          (!dropdownElement || !dropdownElement.contains(e.target as Node))
        ) {
          console.log("Click outside dropdown detected")
          setSpeakerDropdownOpen(false)
        }
      }

      if (editContainerRef.current && !editContainerRef.current.contains(e.target as Node) && !isDropdownItemClicked) {
        const dropdownElement = document.getElementById("speaker-dropdown-portal")

        if (!dropdownElement || !dropdownElement.contains(e.target as Node)) {
          console.log("Click outside edit container detected")
          setTimeout(() => {
            setEditingIndex(null)
          }, 100)
        }
      }

      setIsDropdownItemClicked(false)
    }

    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [speakerDropdownOpen, isDropdownItemClicked])

  useEffect(() => {
    if (speakerButtonRef.current) {
      const updatePosition = () => {
        const rect = speakerButtonRef.current?.getBoundingClientRect()
        if (rect) {
          setDropdownPosition({
            top: rect.bottom + window.scrollY,
            left: rect.left + window.scrollX,
            width: rect.width,
          })
          console.log("Button position:", {
            top: rect.bottom + window.scrollY,
            left: rect.left + window.scrollX,
            width: rect.width,
          })
        }
      }

      updatePosition()

      if (speakerDropdownOpen) {
        updatePosition()
        console.log("Dropdown opened, position updated")
      }

      window.addEventListener("scroll", updatePosition)
      window.addEventListener("resize", updatePosition)

      return () => {
        window.removeEventListener("scroll", updatePosition)
        window.removeEventListener("resize", updatePosition)
      }
    }
  }, [speakerDropdownOpen, speakerButtonRef.current])

  const enterEditMode = (idx: number, entry: TranscriptEntry) => {
    setEditingIndex(idx)
    setEditStartClock(secToClock(entry.start))
    setEditSpeaker(entry.speaker ?? "")
    setEditText(entry.text)
    setSpeakerDropdownOpen(false)
  }

  const handleEditClick = (idx: number, entry: TranscriptEntry, e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation()
    enterEditMode(idx, entry)
  }

  const handleDoubleClick = (idx: number, entry: TranscriptEntry, e: React.MouseEvent) => {
    e.stopPropagation()
    enterEditMode(idx, entry)
  }

  const handleEditSave = (idx: number, e: React.MouseEvent) => {
    e.stopPropagation()
    const newStart = clockToSec(editStartClock)
    if (!editText.trim() || !editSpeaker || isNaN(newStart)) return

    console.log("Saving edit with speaker:", editSpeaker, "text:", editText)

    onTranscriptEdit(idx, {
      start: newStart,
      speaker: editSpeaker,
      text: editText,
    })

    if (idx > 0) onTranscriptEdit(idx - 1, { end: newStart })

    setEditingIndex(null)
    setSpeakerDropdownOpen(false)
  }

  const handleEditCancel = (e: React.MouseEvent) => {
    e.stopPropagation()
    setEditingIndex(null)
    setSpeakerDropdownOpen(false)
  }

  const handleCopy = (text: string, e: React.MouseEvent) => {
    e.stopPropagation()
    navigator.clipboard.writeText(text)
  }

  const handleEntryClick = (entry: TranscriptEntry, index: number, e: React.MouseEvent<HTMLDivElement>) => {
    if (editingIndex !== null) return
    e.preventDefault()
    e.stopPropagation()
    onSelectEntry(index)
    onJumpToTime(entry.start)
    setAutoScroll(false)
    setTimeout(() => setAutoScroll(true), 2000)
  }

  const handleDeleteClick = (index: number, e: React.MouseEvent) => {
    e.stopPropagation()
    setDeleteIndex(index)
    setShowDeleteConfirm(true)
  }

  const handleConfirmDelete = () => {
    if (deleteIndex !== null) {
      onDeleteEntry(deleteIndex)
    }
    setShowDeleteConfirm(false)
    setDeleteIndex(null)
  }

  const handleCancelDelete = () => {
    setShowDeleteConfirm(false)
    setDeleteIndex(null)
  }

  const isBookmarked = (index: number) => {
    return bookmarks.some((bookmark) => bookmark.audioFile === currentAudioFile && bookmark.entryIndex === index)
  }

  const renderSpeakerDropdownPortal = () => {
    if (typeof document === "undefined") return null

    if (!speakerDropdownOpen) return null

    const uniqueSpeakerIds = [...new Set(transcript.map((entry) => entry.speaker).filter(Boolean))] as string[]

    console.log("Unique speaker IDs:", uniqueSpeakerIds)
    console.log("Speaker mapping:", speakerMapping)

    const availableSpeakers = uniqueSpeakerIds.map((id) => {
      const displayName = speakerMapping[id] || id
      return [id, displayName]
    })

    console.log("Available speakers for dropdown:", availableSpeakers)

    return createPortal(
      <div
        id="speaker-dropdown-portal"
        ref={dropdownRef}
        style={{
          position: "absolute",
          top: `${dropdownPosition.top}px`,
          left: `${dropdownPosition.left}px`,
          zIndex: 200,
          background: "#222222",
          border: "1px solid #444444",
          borderRadius: "4px",
          boxShadow: "0 4px 8px rgba(0,0,0,0.3)",
          maxHeight: "200px",
          overflowY: "auto",
          minWidth: `${Math.max(dropdownPosition.width, 120)}px`,
          width: "auto",
          padding: "4px 0",
          display: "block",
          visibility: "visible",
          opacity: 1,
        }}
        onClick={(e) => {
          e.preventDefault()
          e.stopPropagation()
        }}
      >
        {availableSpeakers.length > 0 ? (
          availableSpeakers.map(([id, label]) => (
            <div
              key={id}
              style={{
                padding: "8px 12px",
                cursor: "pointer",
                backgroundColor: editSpeaker === id ? "rgba(74, 131, 255, 0.2)" : "transparent",
                color: "#ffffff",
                fontSize: "14px",
                textAlign: "left",
                margin: "2px 0",
                borderBottom: "1px solid #333333",
              }}
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
                setIsDropdownItemClicked(true)

                console.log("Selected speaker:", id, "with label:", label)
                setEditSpeaker(id)
                setSpeakerDropdownOpen(false)

                console.log("Editing mode maintained after speaker selection")
              }}
              onMouseOver={(e) => {
                e.currentTarget.style.backgroundColor = "rgba(74, 131, 255, 0.1)"
              }}
              onMouseOut={(e) => {
                e.currentTarget.style.backgroundColor = editSpeaker === id ? "rgba(74, 131, 255, 0.2)" : "transparent"
              }}
            >
              {typeof label === "string" && label.trim() ? label : id}
            </div>
          ))
        ) : (
          <div style={{ padding: "8px 12px", color: "#aaaaaa", fontStyle: "italic" }}>話者が定義されていません</div>
        )}
      </div>,
      document.body,
    )
  }

  const renderDeleteConfirmDialog = () => {
    if (!showDeleteConfirm) return null

    return createPortal(
      <div
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: "rgba(0, 0, 0, 0.5)",
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          zIndex: 2147483647,
        }}
      >
        <div
          style={{
            backgroundColor: "#222222",
            padding: "20px",
            borderRadius: "8px",
            boxShadow: "0 4px 8px rgba(0, 0, 0, 0.2)",
            width: "400px",
            maxWidth: "90%",
          }}
        >
          <h3 style={{ color: "#ffffff", marginTop: 0 }}>Confirm Deletion</h3>
          <p style={{ color: "#dddddd" }}>Do you really want to delete this transcript?</p>
          <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "20px" }}>
            <button
              onClick={handleCancelDelete}
              style={{
                padding: "8px 16px",
                backgroundColor: "transparent",
                color: "#ffffff",
                border: "1px solid #444444",
                borderRadius: "4px",
                cursor: "pointer",
              }}
            >
              NO
            </button>
            <button
              onClick={handleConfirmDelete}
              style={{
                padding: "8px 16px",
                backgroundColor: "#e53935",
                color: "#ffffff",
                border: "none",
                borderRadius: "4px",
                cursor: "pointer",
              }}
            >
              YES
            </button>
          </div>
        </div>
      </div>,
      document.body,
    )
  }

  return (
    <div className="transcript-viewer" ref={containerRef}>
      {renderSpeakerDropdownPortal()}
      {renderDeleteConfirmDialog()}
      {transcript.map((entry, index) => {
        const isActive = currentTime >= entry.start && currentTime < entry.end
        const isHighlighted = selectedEntryIndex === index || (isActive && selectedEntryIndex === null)
        const isEditing = editingIndex === index
        const displaySpeaker = entry.speaker ? speakerMapping[entry.speaker] || entry.speaker : "null"
        const entryIsBookmarked = isBookmarked(index)
        const rowStyle: React.CSSProperties | undefined = isEditing
          ? { overflow: "visible", position: "relative", zIndex: 20 }
          : undefined

        return (
          <React.Fragment key={`entry-group-${index}`}>
            {index > 0 && (
              <div
                className={`transcript-entry-boundary ${hoveredBoundaryIndex === index ? "active" : ""}`}
                onMouseEnter={() => setHoveredBoundaryIndex(index)}
                onMouseLeave={() => setHoveredBoundaryIndex(null)}
                onClick={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  onAddEntryBetween(index)
                }}
              >
                <div className="add-entry-btn-container">
                  <Plus size={16} className="add-entry-icon" />
                  <span className="add-entry-text">新しいエントリーを追加</span>
                </div>
              </div>
            )}
            <div
              key={`entry-${index}`}
              ref={isEditing ? editContainerRef : isActive ? activeEntryRef : null}
              className={`transcript-entry${isHighlighted ? " active" : ""}${isEditing ? " editing" : ""}`}
              style={rowStyle}
              onMouseEnter={() => setHoveredIndex(index)}
              onMouseLeave={() => setHoveredIndex(null)}
              onClick={(e) => !isEditing && handleEntryClick(entry, index, e)}
              onDoubleClick={(e) => handleDoubleClick(index, entry, e)}
            >
              {isEditing ? (
                <input
                  type="text"
                  className="edit-time"
                  value={editStartClock}
                  onChange={(e) => setEditStartClock(e.target.value)}
                />
              ) : (
                <div className="transcript-time">{secToClock(entry.start)}</div>
              )}
              {isEditing ? (
                <div className="edit-speaker-container">
                  <button
                    ref={speakerButtonRef}
                    className="edit-speaker-display"
                    style={{
                      padding: "4px 8px",
                      background: "#222222",
                      color: "#ffffff",
                      border: "1px solid #444444",
                      borderRadius: "4px",
                      cursor: "pointer",
                      fontSize: "14px",
                      textAlign: "left",
                      minWidth: "120px",
                    }}
                    onClick={(e) => {
                      e.preventDefault()
                      e.stopPropagation()
                      setSpeakerDropdownOpen(!speakerDropdownOpen)
                      console.log("Speaker dropdown toggled:", !speakerDropdownOpen, "Current speaker:", editSpeaker)
                    }}
                  >
                    {speakerMapping[editSpeaker] || editSpeaker || "Select"}
                  </button>
                </div>
              ) : (
                <div className="transcript-speaker">{displaySpeaker}</div>
              )}
              {isEditing ? (
                <textarea className="edit-text" value={editText} onChange={(e) => setEditText(e.target.value)} />
              ) : (
                <div className="transcript-text">{entry.text}</div>
              )}
              {!isEditing && hoveredIndex === index && (
                <div className="transcript-actions grid-layout">
                  <button
                    className="transcript-action-btn"
                    onClick={(e) => handleEditClick(index, entry, e)}
                    title="Edit"
                  >
                    <Edit size={16} />
                  </button>
                  <button className="transcript-action-btn" onClick={(e) => handleCopy(entry.text, e)} title="Copy">
                    <Copy size={16} />
                  </button>
                  <button
                    className={`transcript-action-btn bookmark ${entryIsBookmarked ? "active" : ""}`}
                    onClick={() => onBookmarkEntry(index)}
                    title={entryIsBookmarked ? "Remove bookmark" : "Add bookmark"}
                  >
                    <Bookmark size={16} />
                  </button>
                  <button
                    className="transcript-action-btn delete"
                    onClick={(e) => handleDeleteClick(index, e)}
                    title="Delete"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              )}
              {isEditing && (
                <div className="edit-buttons">
                  <button
                    className="save-btn"
                    onClick={(e) => handleEditSave(index, e)}
                    disabled={!editText.trim() || !editSpeaker || !editStartClock}
                    title="Save"
                  >
                    <Save size={16} />
                  </button>
                  <button className="cancel-btn" onClick={handleEditCancel} title="Cancel">
                    <X size={16} />
                  </button>
                </div>
              )}
            </div>
          </React.Fragment>
        )
      })}
    </div>
  )
}

export default TranscriptViewer