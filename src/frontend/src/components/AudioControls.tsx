"use client"

import { useEffect, useRef, useState } from "react"
import type React from "react"
import type { TranscriptEntry } from "../types"

interface AudioControlsProps {
  currentTime: number
  duration: number
  isPlaying: boolean
  playbackRate: number
  audioSrc: string
  onTogglePlayPause: () => void
  onSkipBackward: () => void
  onSkipForward: () => void
  onChangePlaybackRate: (rate: number) => void
  onSeek: (time: number) => void
  onWaveformReady: (duration: number) => void
  onTimeUpdate: (time: number) => void
  onWaveformClick: (time: number) => void
  transcript: TranscriptEntry[]
  lastPlaybackPosition: number
}

const AudioControls: React.FC<AudioControlsProps> = ({
  currentTime,
  duration,
  isPlaying,
  playbackRate,
  audioSrc,
  onTogglePlayPause,
  onSkipBackward,
  onSkipForward,
  onChangePlaybackRate,
  onSeek,
  onWaveformReady,
  onTimeUpdate,
  onWaveformClick,
  transcript,
  lastPlaybackPosition,
}) => {
  const waveformRef = useRef<HTMLDivElement>(null)
  const wavesurferRef = useRef<any>(null)
  const [showPlaybackRates, setShowPlaybackRates] = useState(false)
  const playbackRates = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0]
  const [isWavesurferReady, setIsWavesurferReady] = useState(false)
  const playbackRateContainerRef = useRef<HTMLDivElement>(null)
  const audioSrcRef = useRef<string>(audioSrc)
  const isInitializedRef = useRef<boolean>(false)
  const lastPlayingStateRef = useRef<boolean>(isPlaying)

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, "0")}`
  }

  useEffect(() => {
    if (audioSrcRef.current !== audioSrc) {
      audioSrcRef.current = audioSrc
      isInitializedRef.current = false
    }

    if (isInitializedRef.current || !waveformRef.current) return

    const initWavesurfer = async () => {
      try {
        const WaveSurfer = (await import("wavesurfer.js")).default

        if (wavesurferRef.current) {
          wavesurferRef.current.destroy()
        }

        wavesurferRef.current = WaveSurfer.create({
          container: waveformRef.current,
          waveColor: "#4a83ff",
          progressColor: "#1a56e8",
          cursorColor: "#333",
          barWidth: 2,
          barGap: 1,
          barRadius: 3,
          height: 60,
          responsive: true,
        })

        wavesurferRef.current.on("ready", () => {
          console.log("Wavesurfer is ready")
          setIsWavesurferReady(true)
          const audioDuration = wavesurferRef.current.getDuration()
          onWaveformReady(audioDuration)
        })

        wavesurferRef.current.on("audioprocess", (time: number) => {
          onTimeUpdate(time)
        })

        wavesurferRef.current.on("seek", (progress: number) => {
          const seekTime = progress * wavesurferRef.current.getDuration()
          onSeek(seekTime)
        })

        wavesurferRef.current.on("click", (e: MouseEvent) => {
          if (!wavesurferRef.current) return

          const clickTime = wavesurferRef.current.getCurrentTime()
          console.log("Waveform clicked at time:", clickTime)

          onWaveformClick(clickTime)

          if (isPlaying) {
            wavesurferRef.current.play(clickTime)
          }
        })

        wavesurferRef.current.on("error", (error: any) => {
          console.error("Wavesurfer error:", error)
        })

        if (audioSrc) {
          console.log("Loading audio:", `/audios/${audioSrc}`)
          wavesurferRef.current.load(`/audios/${audioSrc}`)
        }

        isInitializedRef.current = true
      } catch (error) {
        console.error("Error initializing Wavesurfer:", error)
      }
    }

    initWavesurfer()

    return () => {
      if (wavesurferRef.current && !isInitializedRef.current) {
        wavesurferRef.current.destroy()
      }
    }
  }, [audioSrc, onWaveformClick, onWaveformReady, onSeek, onTimeUpdate, isPlaying])

  useEffect(() => {
    if (!wavesurferRef.current || !isWavesurferReady) return

    try {
      if (isPlaying !== lastPlayingStateRef.current) {
        lastPlayingStateRef.current = isPlaying

        if (isPlaying) {
          console.log("Playing audio with Wavesurfer from:", lastPlaybackPosition)
          wavesurferRef.current.play(lastPlaybackPosition)
        } else {
          console.log("Pausing audio with Wavesurfer")
          wavesurferRef.current.pause()
        }
      }
    } catch (error) {
      console.error("Error controlling playback:", error)
    }
  }, [isPlaying, isWavesurferReady, lastPlaybackPosition])

  useEffect(() => {
    if (!wavesurferRef.current || !isWavesurferReady) return

    try {
      wavesurferRef.current.setPlaybackRate(playbackRate)
    } catch (error) {
      console.error("Error setting playback rate:", error)
    }
  }, [playbackRate, isWavesurferReady])

  useEffect(() => {
    if (!wavesurferRef.current || !isWavesurferReady || wavesurferRef.current.isPlaying()) return

    try {
      const progress = duration > 0 ? currentTime / duration : 0
      wavesurferRef.current.seekTo(progress)
    } catch (error) {
      console.error("Error seeking:", error)
    }
  }, [currentTime, duration, isWavesurferReady])

  const handleSkipBackward = () => {
    if (!wavesurferRef.current || !isWavesurferReady) {
      onSkipBackward()
      return
    }

    try {
      const currentTime = wavesurferRef.current.getCurrentTime()
      wavesurferRef.current.seekTo(Math.max(0, currentTime - 5) / wavesurferRef.current.getDuration())
      onSkipBackward()
    } catch (error) {
      console.error("Error skipping backward:", error)
      onSkipBackward()
    }
  }

  const handleSkipForward = () => {
    if (!wavesurferRef.current || !isWavesurferReady) {
      onSkipForward()
      return
    }

    try {
      const currentTime = wavesurferRef.current.getCurrentTime()
      const duration = wavesurferRef.current.getDuration()
      wavesurferRef.current.seekTo(Math.min(duration, currentTime + 5) / duration)
      onSkipForward()
    } catch (error) {
      console.error("Error skipping forward:", error)
      onSkipForward()
    }
  }

  useEffect(() => {
    if (!wavesurferRef.current || !isWavesurferReady) return

    try {
      const wavesurferTime = wavesurferRef.current.getCurrentTime()
      if (Math.abs(wavesurferTime - currentTime) > 0.5) {
        console.log("Forced seek to:", currentTime)
        const progress = duration > 0 ? currentTime / duration : 0
        wavesurferRef.current.seekTo(progress)
      }
    } catch (error) {
      console.error("Error in forced seeking:", error)
    }
  }, [currentTime, duration, isWavesurferReady])

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (playbackRateContainerRef.current && !playbackRateContainerRef.current.contains(event.target as Node)) {
        setShowPlaybackRates(false)
      }
    }

    document.addEventListener("mousedown", handleClickOutside)
    return () => {
      document.removeEventListener("mousedown", handleClickOutside)
    }
  }, [])

  return (
    <div className="audio-controls">
      <div className="waveform-container" ref={waveformRef}></div>
      <div className="controls-container">
        <div className="playback-rate-container" ref={playbackRateContainerRef}>
          <button onClick={() => setShowPlaybackRates(!showPlaybackRates)} className="playback-rate-button">
            {playbackRate}x
          </button>
          {showPlaybackRates && (
            <div className="playback-rate-dropdown horizontal">
              {playbackRates.map((rate) => (
                <button
                  key={rate}
                  className={`playback-rate-option ${playbackRate === rate ? "active" : ""}`}
                  onClick={() => {
                    onChangePlaybackRate(rate)
                    setShowPlaybackRates(false)
                  }}
                >
                  {rate}x
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="playback-controls">
          <button onClick={handleSkipBackward} className="control-button">
            <span style={{ color: "#000" }}>-5</span>
          </button>
          <button onClick={onTogglePlayPause} className="control-button play-pause">
            {isPlaying ? (
              <span className="pause-icon" style={{ color: "#000" }}>
                &#10074;&#10074;
              </span>
            ) : (
              <span className="play-icon" style={{ color: "#000" }}>
                &#9654;
              </span>
            )}
          </button>
          <button onClick={handleSkipForward} className="control-button">
            <span style={{ color: "#000" }}>+5</span>
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