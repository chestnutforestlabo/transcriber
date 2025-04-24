"use client"

import { Music, Menu, Tag, Plus, X } from "lucide-react"
import { useState } from "react"
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

  // タグでフィルタリングされた音声ファイルを取得
  const getFilteredAudioFiles = () => {
    if (!selectedTag) return audioFiles

    // 選択されたタグを持つ音声ファイルを先頭に
    const withTag = audioFiles.filter((audio) => audioTags[audio]?.includes(selectedTag))
    const withoutTag = audioFiles.filter((audio) => !audioTags[audio]?.includes(selectedTag))

    return [...withTag, ...withoutTag]
  }

  const filteredAudioFiles = getFilteredAudioFiles()

  // 音声ファイルがタグでフィルタリングされているかどうかを判定
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
                  <button
                    className="add-tag-to-audio"
                    onClick={(e) => {
                      e.stopPropagation()
                      setShowTagMenu(showTagMenu === audio ? null : audio)
                      setNewTagInput("")
                    }}
                  >
                    <Tag size={14} />
                  </button>
                </div>
              )}

              {showTagMenu === audio && (
                <div className="tag-menu" onClick={(e) => e.stopPropagation()}>
                  <div className="tag-menu-header">Add tag to {audio}</div>
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