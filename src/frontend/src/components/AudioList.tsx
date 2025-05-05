"use client"

import { Music, Menu, Tag, Plus, X } from "lucide-react"
import { useState, useEffect } from "react"
import type React from "react"

interface AudioListProps {
  audioFiles: string[]
  selectedAudio: string
  onSelectAudio: (audio: string) => void
  isCollapsed: boolean
  onToggleCollapse: () => void
  audioTags: Record<string, string[]>
  allTags: string[]
  onAddTagToAudio: (audio: string, tag: string) => void
  onRemoveTagFromAudio: (audio: string, tag: string) => void
  selectedTag: string | null
}

const AudioList: React.FC<AudioListProps> = ({
  audioFiles,
  selectedAudio,
  onSelectAudio,
  isCollapsed,
  onToggleCollapse,
  audioTags,
  allTags,
  onAddTagToAudio,
  onRemoveTagFromAudio,
  selectedTag,
}) => {
  const [showTagMenu, setShowTagMenu] = useState<string | null>(null)
  const [newTagInput, setNewTagInput] = useState("")
  const [tagMenuPosition, setTagMenuPosition] = useState<{ left: number; top: number }>({ left: 0, top: 0 })

  const getFilteredAudioFiles = () => {
    if (!selectedTag) return audioFiles

    const withTag = audioFiles.filter((audio) => audioTags[audio]?.includes(selectedTag))
    const withoutTag = audioFiles.filter((audio) => !audioTags[audio]?.includes(selectedTag))

    return [...withTag, ...withoutTag]
  }

  const filteredAudioFiles = getFilteredAudioFiles()

  const isAudioHighlighted = (audio: string) => {
    return selectedTag && audioTags[audio]?.includes(selectedTag)
  }

  const handleAddTag = (audio: string) => {
    if (newTagInput.trim() && !audioTags[audio]?.includes(newTagInput.trim())) {
      onAddTagToAudio(audio, newTagInput.trim())
      setNewTagInput("")
      setShowTagMenu(null)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent, audio: string) => {
    if (e.key === "Enter") {
      handleAddTag(audio)
    } else if (e.key === "Escape") {
      setShowTagMenu(null)
      setNewTagInput("")
    }
  }

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (showTagMenu && !event.target) return

      const tagMenuElement = document.querySelector(".tag-menu")
      const clickedElement = event.target as Node

      if (tagMenuElement && !tagMenuElement.contains(clickedElement)) {
        setShowTagMenu(null)
      }
    }

    document.addEventListener("mousedown", handleClickOutside)

    return () => {
      document.removeEventListener("mousedown", handleClickOutside)
    }
  }, [showTagMenu])

  const handleTagButtonClick = (e: React.MouseEvent, audio: string) => {
    e.stopPropagation()

    if (showTagMenu === audio) {
      setShowTagMenu(null)
      return
    }

    const buttonElement = e.currentTarget as HTMLElement
    const rect = buttonElement.getBoundingClientRect()

    const menuLeft = rect.left
    const menuTop = rect.bottom + 5

    setTagMenuPosition({ left: menuLeft, top: menuTop })

    setShowTagMenu(audio)
    setNewTagInput("")
  }

  return (
    <div className="audio-list">
      <div className="audio-list-header">
        {!isCollapsed && <h3>Audio Files</h3>}
        <button
          className="sidebar-toggle-btn"
          onClick={onToggleCollapse}
          aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <Menu size={20} />
        </button>
      </div>
      {audioFiles.length === 0 ? (
        !isCollapsed && <div className="no-audio-files">No audio files found</div>
      ) : (
        <div className="audio-items-container">
          {filteredAudioFiles.map((audio, index) => (
            <div
              key={index}
              className={`audio-item ${selectedAudio === audio ? "selected" : ""} ${
                isAudioHighlighted(audio) ? "highlighted" : ""
              }`}
              onClick={() => onSelectAudio(audio)}
              title={audio}
            >
              <div className="audio-item-content">{isCollapsed ? <Music size={16} /> : audio}</div>

              {!isCollapsed && (
                <div className="audio-item-tags">
                  {audioTags[audio]?.map((tag) => (
                    <span key={tag} className="audio-tag">
                      {tag}
                      <button
                        className="remove-audio-tag"
                        onClick={(e) => {
                          e.stopPropagation()
                          onRemoveTagFromAudio(audio, tag)
                        }}
                      >
                        <X size={12} />
                      </button>
                    </span>
                  ))}
                  <button className="add-tag-to-audio" onClick={(e) => handleTagButtonClick(e, audio)}>
                    <Tag size={14} />
                  </button>
                </div>
              )}

              {showTagMenu === audio && (
                <div
                  className="tag-menu"
                  onClick={(e) => e.stopPropagation()}
                  style={{
                    left: `${tagMenuPosition.left}px`,
                    top: `${tagMenuPosition.top}px`,
                  }}
                >
                  <div className="tag-menu-header">
                    <span>Add tag to {audio}</span>
                    <button className="tag-menu-close-btn" onClick={() => setShowTagMenu(null)}>
                      <X size={14} />
                    </button>
                  </div>
                  <div className="tag-menu-content">
                    {allTags
                      .filter((tag) => !audioTags[audio]?.includes(tag))
                      .map((tag) => (
                        <div
                          key={tag}
                          className="tag-menu-item"
                          onClick={() => {
                            onAddTagToAudio(audio, tag)
                            setShowTagMenu(null)
                          }}
                        >
                          {tag}
                        </div>
                      ))}
                  </div>
                  <div className="tag-menu-new">
                    <input
                      type="text"
                      placeholder="New tag..."
                      value={newTagInput}
                      onChange={(e) => setNewTagInput(e.target.value)}
                      onKeyDown={(e) => handleKeyDown(e, audio)}
                      autoFocus
                    />
                    <button onClick={() => handleAddTag(audio)}>
                      <Plus size={14} />
                    </button>
                  </div>
                  <div className="tag-menu-footer">
                    <button className="tag-menu-save-btn" onClick={() => setShowTagMenu(null)}>
                      Save
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default AudioList