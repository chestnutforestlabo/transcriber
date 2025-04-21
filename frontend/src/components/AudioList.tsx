"use client"

import type React from "react"

interface AudioListProps {
  audioFiles: string[]
  selectedAudio: string
  onSelectAudio: (audio: string) => void
}

const AudioList: React.FC<AudioListProps> = ({ audioFiles, selectedAudio, onSelectAudio }) => {
  return (
    <div className="audio-list">
      {audioFiles.map((audio, index) => (
        <div
          key={index}
          className={`audio-item ${selectedAudio === audio ? "selected" : ""}`}
          onClick={() => onSelectAudio(audio)}
        >
          {audio}
        </div>
      ))}
    </div>
  )
}

export default AudioList