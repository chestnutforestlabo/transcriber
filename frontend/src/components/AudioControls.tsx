"use client"

import type React from "react"

interface AudioControlsProps {
  currentTime: number
  duration: number
  isPlaying: boolean
  playbackRate: number
  onTogglePlayPause: () => void
  onSkipBackward: () => void
  onSkipForward: () => void
  onChangePlaybackRate: (rate: number) => void
  onSeek: (time: number) => void
}

const AudioControls: React.FC<AudioControlsProps> = ({
  currentTime,
  duration,
  isPlaying,
  playbackRate,
  onTogglePlayPause,
  onSkipBackward,
  onSkipForward,
  onChangePlaybackRate,
  onSeek,
}) => {
  // Format time as MM:SS
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, "0")}`
  }

  // Handle progress bar click
  const handleProgressClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const clickPosition = (e.clientX - rect.left) / rect.width
    onSeek(clickPosition * duration)
  }

  return (
    <div className="audio-controls">
      <div className="waveform-container">
        <div className="waveform">
          {/* Simple waveform visualization */}
          <svg width="100%" height="40" viewBox="0 0 1000 40">
            <path
              d="M0,20 Q25,5 50,20 T100,20 T150,20 T200,20 T250,20 T300,20 T350,20 T400,20 T450,20 T500,20 T550,20 T600,20 T650,20 T700,20 T750,20 T800,20 T850,20 T900,20 T950,20 T1000,20"
              fill="none"
              stroke="black"
              strokeWidth="1"
            />
          </svg>
          <div className="progress-bar" onClick={handleProgressClick}>
            <div className="progress-indicator" style={{ width: `${(currentTime / duration) * 100}%` }}></div>
          </div>
        </div>
      </div>
      <div className="controls-container">
        <div className="playback-rate">
          <button onClick={() => onChangePlaybackRate(playbackRate === 1 ? 1.5 : 1)}>{playbackRate}x</button>
        </div>
        <div className="playback-controls">
          <button onClick={onSkipBackward} className="control-button">
            ⟲5
          </button>
          <button onClick={onTogglePlayPause} className="control-button play-pause">
            {isPlaying ? "⏸" : "▶"}
          </button>
          <button onClick={onSkipForward} className="control-button">
            ⟳5
          </button>
        </div>
        <div className="time-display">
          {formatTime(currentTime)} / {formatTime(duration)}
        </div>
      </div>
    </div>
  )
}

export default AudioControls