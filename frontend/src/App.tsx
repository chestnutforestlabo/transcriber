"use client"

import { useState, useEffect, useRef } from "react"
import "./App.css"
import AudioList from "./components/AudioList"
import TranscriptViewer from "./components/TranscriptViewer"
import SpeakerSettings from "./components/SpeakerSettings"
import AudioControls from "./components/AudioControls"
import type { TranscriptEntry } from "./types"

function App() {
  const [audioFiles, setAudioFiles] = useState<string[]>([])
  const [selectedAudio, setSelectedAudio] = useState<string>("")
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([])
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [playbackRate, setPlaybackRate] = useState(1)
  const audioRef = useRef<HTMLAudioElement>(null)

  // Load audio file list
  useEffect(() => {
    fetch("/audios/index.json")
      .then((response) => response.json())
      .then((data) => {
        setAudioFiles(data)
        if (data.length > 0) {
          setSelectedAudio(data[0])
        }
      })
      .catch((error) => console.error("Error loading audio files:", error))
  }, [])

  // Load transcript when audio file changes
  useEffect(() => {
    if (!selectedAudio) return

    const transcriptFile = selectedAudio.replace(".wav", ".json")
    fetch(`/transcripts/${transcriptFile}`)
      .then((response) => response.json())
      .then((data) => {
        setTranscript(data)
        // Find the last entry to determine duration
        if (data.length > 0) {
          setDuration(data[data.length - 1].end)
        }
      })
      .catch((error) => console.error("Error loading transcript:", error))
  }, [selectedAudio])

  // Update audio element when selected audio changes
  useEffect(() => {
    if (audioRef.current && selectedAudio) {
      audioRef.current.src = `/audios/${selectedAudio}`
      audioRef.current.load()
    }
  }, [selectedAudio])

  // Handle time update from audio player
  const handleTimeUpdate = () => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime)
    }
  }

  // Jump to specific time in the audio
  const jumpToTime = (time: number) => {
    if (audioRef.current) {
      audioRef.current.currentTime = time
      setCurrentTime(time)
    }
  }

  // Toggle play/pause
  const togglePlayPause = () => {
    if (audioRef.current) {
      if (isPlaying) {
        audioRef.current.pause()
      } else {
        audioRef.current.play()
      }
      setIsPlaying(!isPlaying)
    }
  }

  // Skip forward/backward
  const skipTime = (seconds: number) => {
    if (audioRef.current) {
      audioRef.current.currentTime += seconds
    }
  }

  // Change playback rate
  const changePlaybackRate = (rate: number) => {
    if (audioRef.current) {
      audioRef.current.playbackRate = rate
      setPlaybackRate(rate)
    }
  }

  return (
    <div className="transcriber-container">
      <div className="transcriber-header">
        <h1>Transcriber</h1>
      </div>
      <div className="transcriber-content">
        <div className="audio-list-container">
          <AudioList audioFiles={audioFiles} selectedAudio={selectedAudio} onSelectAudio={setSelectedAudio} />
        </div>
        <div className="transcript-container">
          <div className="transcript-header">
            <div>
              {selectedAudio}{" "}
              {duration
                ? `${Math.floor(duration / 60)}:${Math.floor(duration % 60)
                    .toString()
                    .padStart(2, "0")}`
                : ""}{" "}
              Speaker: 2人
            </div>
          </div>
          <TranscriptViewer transcript={transcript} currentTime={currentTime} onJumpToTime={jumpToTime} />
          <AudioControls
            currentTime={currentTime}
            duration={duration}
            isPlaying={isPlaying}
            playbackRate={playbackRate}
            onTogglePlayPause={togglePlayPause}
            onSkipBackward={() => skipTime(-5)}
            onSkipForward={() => skipTime(5)}
            onChangePlaybackRate={changePlaybackRate}
            onSeek={jumpToTime}
          />
        </div>
        <div className="speaker-settings-container">
          <SpeakerSettings />
        </div>
      </div>
      <audio
        ref={audioRef}
        onTimeUpdate={handleTimeUpdate}
        onEnded={() => setIsPlaying(false)}
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
      />
    </div>
  )
}

export default App