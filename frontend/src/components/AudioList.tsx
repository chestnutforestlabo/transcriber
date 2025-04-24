"use client"

import { Music, Menu } from "lucide-react"
import type React from "react"

interface AudioListProps {
  audioFiles: string[]
  selectedAudio: string
  onSelectAudio: (audio: string) => void
  isCollapsed: boolean
  onToggleCollapse: () => void
}

const AudioList: React.FC<AudioListProps> = ({
  audioFiles,
  selectedAudio,
  onSelectAudio,
  isCollapsed,
  onToggleCollapse,
}) => {
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
          {audioFiles.map((audio, index) => (
            <div
              key={index}
              className={`audio-item ${selectedAudio === audio ? "selected" : ""} ${isCollapsed ? "collapsed" : ""}`}
              onClick={() => onSelectAudio(audio)}
              title={audio}
            >
              {isCollapsed ? <Music size={16} /> : audio}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default AudioList