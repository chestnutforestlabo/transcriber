"use client"

import { useState } from "react"
import type React from "react"
import type { TranscriptEntry } from "../types"

interface SpeakerSettingsProps {
  transcript: TranscriptEntry[]
  onSpeakerNameChange: (originalName: string, newName: string) => void
}

const SpeakerSettings: React.FC<SpeakerSettingsProps> = ({ transcript, onSpeakerNameChange }) => {
  const [speakerNames, setSpeakerNames] = useState<Record<string, string>>({})

  // Get unique speaker names from transcript
  const uniqueSpeakers = [...new Set(transcript.map((entry) => entry.speaker).filter(Boolean))] as string[]

  const handleNameChange = (speaker: string, newName: string) => {
    setSpeakerNames((prev) => ({ ...prev, [speaker]: newName }))
    onSpeakerNameChange(speaker, newName)
  }

  return (
    <div className="speaker-settings">
      <h3>Speaker Settings</h3>
      <div className="speaker-settings-content">
        {uniqueSpeakers.length === 0 ? (
          <div>No speakers found in the transcript.</div>
        ) : (
          <ul>
            {uniqueSpeakers.map((speaker) => (
              <li key={speaker}>
                <label htmlFor={`speaker-${speaker}`}>
                  {speaker}:
                  <input
                    type="text"
                    id={`speaker-${speaker}`}
                    value={speakerNames[speaker] || ""}
                    onChange={(e) => handleNameChange(speaker, e.target.value)}
                    placeholder="Enter new name"
                  />
                </label>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

export default SpeakerSettings