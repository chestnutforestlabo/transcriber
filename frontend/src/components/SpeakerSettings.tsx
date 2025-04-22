"use client"

import { useState, useEffect } from "react"
import type React from "react"

interface TranscriptEntry {
  speaker: string
  text: string
}

interface SpeakerSettingsProps {
  transcript: TranscriptEntry[]
  onSpeakerNameChange: (originalName: string, newName: string) => void
}

const SpeakerSettings: React.FC<SpeakerSettingsProps> = ({ transcript, onSpeakerNameChange }) => {
  const [speakers, setSpeakers] = useState<{ id: string; name: string }[]>([])

  // Extract unique speakers from transcript and filter out null/empty speakers
  useEffect(() => {
    if (!transcript.length) return

    const uniqueSpeakers = Array.from(new Set(transcript.map((entry) => entry.speaker)))
      .filter((speaker) => !!speaker) // null や空文字など falsy な値を除外する
      .map((speaker) => ({
        id: speaker,
        name: "",
      }))

    setSpeakers(uniqueSpeakers)
  }, [transcript])

  const handleNameChange = (speakerId: string, newName: string) => {
    setSpeakers((prev) =>
      prev.map((speaker) => (speaker.id === speakerId ? { ...speaker, name: newName } : speaker))
    )
  }

  const handleNameBlur = (speakerId: string, newName: string) => {
    if (newName.trim()) {
      onSpeakerNameChange(speakerId, newName.trim())
    }
  }

  return (
    <div className="speaker-settings">
      <h3>Speaker Setting</h3>
      {speakers.map((speaker) => (
        <div key={speaker.id} className="speaker-setting">
          <label>{speaker.id}</label>
          <input
            type="text"
            className="speaker-input"
            placeholder="話者名を入力"
            value={speakers.find((s) => s.id === speaker.id)?.name || ""}
            onChange={(e) => handleNameChange(speaker.id, e.target.value)}
            onBlur={(e) => handleNameBlur(speaker.id, e.target.value)}
          />
        </div>
      ))}
    </div>
  )
}

export default SpeakerSettings