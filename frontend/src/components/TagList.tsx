"use client"

import { useState } from "react"
import type React from "react"
import { Tag, Plus, X } from "lucide-react"

interface TagListProps {
  allTags: string[]
  selectedTag: string | null
  onSelectTag: (tag: string | null) => void
  onAddTag: (tag: string) => void
  onRemoveTag: (tag: string) => void
}

const TagList: React.FC<TagListProps> = ({ allTags, selectedTag, onSelectTag, onAddTag, onRemoveTag }) => {
  const [newTagInput, setNewTagInput] = useState("")
  const [isAddingTag, setIsAddingTag] = useState(false)

  const handleAddTag = () => {
    if (newTagInput.trim()) {
      onAddTag(newTagInput.trim())
      setNewTagInput("")
      setIsAddingTag(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleAddTag()
    } else if (e.key === "Escape") {
      setIsAddingTag(false)
      setNewTagInput("")
    }
  }

  return (
    <div className="tag-list">
      <div className="tag-list-header">
        <h3>
          <Tag size={16} className="tag-icon" /> Tags
        </h3>
        <button className="add-tag-button" onClick={() => setIsAddingTag(true)} title="Add new tag">
          <Plus size={16} />
        </button>
      </div>

      {isAddingTag && (
        <div className="add-tag-form">
          <input
            type="text"
            value={newTagInput}
            onChange={(e) => setNewTagInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="New tag name..."
            autoFocus
            className="add-tag-input"
          />
          <button className="add-tag-submit" onClick={handleAddTag}>
            Add
          </button>
          <button
            className="add-tag-cancel"
            onClick={() => {
              setIsAddingTag(false)
              setNewTagInput("")
            }}
          >
            Cancel
          </button>
        </div>
      )}

      <div className="tag-items">
        <div className={`tag-item ${selectedTag === null ? "selected" : ""}`} onClick={() => onSelectTag(null)}>
          All Files
        </div>
        {allTags.map((tag) => (
          <div
            key={tag}
            className={`tag-item ${selectedTag === tag ? "selected" : ""}`}
            onClick={() => onSelectTag(tag)}
          >
            <span className="tag-name">{tag}</span>
            <button
              className="remove-tag-button"
              onClick={(e) => {
                e.stopPropagation()
                onRemoveTag(tag)
              }}
              title="Remove tag"
            >
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}

export default TagList