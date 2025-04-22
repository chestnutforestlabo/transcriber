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
      <h3>Audio Files</h3>
      {audioFiles.length === 0 ? (
        <div className="no-audio-files">No audio files found</div>
      ) : (
        audioFiles.map((audio, index) => (
          <div
            key={index}
            className={`audio-item ${selectedAudio === audio ? "selected" : ""}`}
            onClick={() => onSelectAudio(audio)}
          >
            {audio}
          </div>
        ))
      )}
    </div>
  )
}

export default AudioList