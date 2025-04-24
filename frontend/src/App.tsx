"use client"

import { useState, useEffect, useRef } from "react"
import "./App.css"
import AudioList from "./components/AudioList"
import TranscriptViewer from "./components/TranscriptViewer"
import SpeakerSettings from "./components/SpeakerSettings"
import AudioControls from "./components/AudioControls"
import type { TranscriptEntry, SpeakerMapping } from "./types"

function App() {
  const [audioFiles, setAudioFiles] = useState<string[]>([])
  const [selectedAudio, setSelectedAudio] = useState<string>("")
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([])
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [playbackRate, setPlaybackRate] = useState(1.0)
  const [speakerMapping, setSpeakerMapping] = useState<SpeakerMapping>({})
  const [isSaving, setIsSaving] = useState(false)
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "success" | "error">("idle")
  const [saveError, setSaveError] = useState<string | null>(null)
  const saveInProgressRef = useRef(false)
  const transcriptViewerRef = useRef<HTMLDivElement>(null)

  // Load audio file list
  useEffect(() => {
    fetch("/audios/index.json")
      .then((response) => response.json())
      .then((data) => {
        console.log("Loaded audio files:", data)
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
    console.log("Loading transcript:", transcriptFile)

    fetch(`/transcripts/${transcriptFile}`)
      .then((response) => response.json())
      .then((data) => {
        console.log("Loaded transcript data:", data)
        setTranscript(data)
        // Find the last entry to determine duration
        if (data.length > 0) {
          setDuration(data[data.length - 1].end)
        }
        // Reset speaker mapping when loading a new transcript
        setSpeakerMapping({})
        setSaveStatus("idle")
        setSaveError(null)
      })
      .catch((error) => console.error("Error loading transcript:", error))
  }, [selectedAudio])

  // Handle audio selection
  const handleSelectAudio = (audio: string) => {
    console.log("Selected audio:", audio)
    setIsPlaying(false) // Stop playback when changing audio
    setCurrentTime(0)
    setSelectedAudio(audio)
  }

  // Handle time update from wavesurfer
  const handleTimeUpdate = (time: number) => {
    setCurrentTime(time)
  }

  // Handle waveform ready event
  const handleWaveformReady = (audioDuration: number) => {
    console.log("Waveform ready, duration:", audioDuration)
    setDuration(audioDuration)
  }

  // Jump to specific time in the audio
  const jumpToTime = (time: number) => {
    console.log("Jumping to time:", time)
    setCurrentTime(time)
  }

  // Toggle play/pause
  const togglePlayPause = () => {
    console.log("Toggle play/pause, current state:", isPlaying)
    setIsPlaying(!isPlaying)
  }

  // Skip forward/backward
  const skipTime = (seconds: number) => {
    console.log("Skipping time by seconds:", seconds)
    setCurrentTime((prev) => Math.max(0, Math.min(prev + seconds, duration)))
  }

  // Change playback rate
  const changePlaybackRate = (rate: number) => {
    console.log("Changing playback rate to:", rate)
    setPlaybackRate(rate)
  }

  // 波形クリック時に対応するトランスクリプトを見つけてスクロール
  const handleWaveformClick = (time: number) => {
    console.log("Waveform clicked, finding transcript at time:", time)

    // 対応するトランスクリプトエントリを見つける
    const entryIndex = transcript.findIndex((entry) => time >= entry.start && time < entry.end)

    if (entryIndex !== -1) {
      console.log("Found transcript entry at index:", entryIndex)

      // トランスクリプトビューアー内の該当要素を取得
      const transcriptViewer = document.querySelector(".transcript-viewer")
      if (transcriptViewer) {
        const entryElement = transcriptViewer.children[entryIndex] as HTMLElement
        if (entryElement) {
          // スクロールして表示
          entryElement.scrollIntoView({
            behavior: "smooth",
            block: "center",
          })

          // 時間を更新して選択状態を変更
          setCurrentTime(time)
        }
      }
    }
  }

  // Check server status
  const checkServerStatus = async () => {
    try {
      const response = await fetch("/api/debug")
      if (!response.ok) {
        throw new Error(`Server status check failed: ${response.statusText}`)
      }
      const data = await response.json()
      console.log("Server status:", data)
      return data
    } catch (error) {
      console.error("Error checking server status:", error)
      return null
    }
  }

  // Save transcript changes to file
  const saveTranscriptChanges = async () => {
    // 保存処理が既に進行中の場合は重複実行を防止
    if (!selectedAudio || saveInProgressRef.current) {
      console.log("Save already in progress or no audio selected, skipping")
      return
    }

    const transcriptFile = selectedAudio.replace(".wav", ".json")
    console.log("Saving transcript changes to:", transcriptFile)

    // 保存中フラグを設定
    saveInProgressRef.current = true
    setIsSaving(true)
    setSaveStatus("saving")
    setSaveError(null)

    try {
      // Check server status first
      await checkServerStatus()

      // ディープコピーを作成して参照の問題を回避
      const transcriptToSave = JSON.parse(JSON.stringify(transcript))

      // Apply speaker mappings to transcript before saving
      const updatedTranscript = transcriptToSave.map((entry: TranscriptEntry) => {
        // speakerMappingに登録されている場合は、表示用のspeaker名を使用
        const updatedEntry = { ...entry }
        if (entry.speaker && speakerMapping[entry.speaker]) {
          updatedEntry.speaker = speakerMapping[entry.speaker]
        }
        // textはそのまま保持（すでに編集済みの場合はその値が使われる）
        return updatedEntry
      })

      console.log("Sending transcript data to server:", updatedTranscript.length, "entries")

      const response = await fetch("/api/save-transcript", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          filename: transcriptFile,
          data: updatedTranscript,
        }),
      })

      let responseData
      try {
        responseData = await response.json()
      } catch (error) {
        throw new Error(`Failed to parse response: ${await response.text()}`)
      }

      if (!response.ok) {
        throw new Error(`Failed to save transcript: ${responseData.error || response.statusText}`)
      }

      console.log("Transcript saved successfully:", responseData)
      setSaveStatus("success")

      // Reset success status after 3 seconds
      setTimeout(() => {
        setSaveStatus("idle")
        setSaveError(null)
      }, 3000)
    } catch (error) {
      console.error("Error saving transcript:", error)
      setSaveStatus("error")
      setSaveError((error as Error).message)

      // Reset error status after 5 seconds
      setTimeout(() => {
        setSaveStatus("idle")
        setSaveError(null)
      }, 5000)
    } finally {
      setIsSaving(false)
      // 保存中フラグをリセット
      saveInProgressRef.current = false
    }
  }

  // Handle speaker name change
  const handleSpeakerNameChange = (originalName: string, newName: string) => {
    console.log(`Changing speaker name from ${originalName} to ${newName}`)
    setSpeakerMapping((prev) => ({
      ...prev,
      [originalName]: newName,
    }))

    // Save changes after updating speaker mapping
    // requestAnimationFrameを使用して状態更新後に保存処理を実行
    requestAnimationFrame(() => {
      console.log("Saving after speaker name change")
      saveTranscriptChanges()
    })
  }

  // Handle transcript edit
  const handleTranscriptEdit = (index: number, newText: string) => {
    console.log(`Editing transcript at index ${index}:`, newText)

    // トランスクリプトの状態を更新
    setTranscript((prev) => {
      const updated = [...prev]
      updated[index] = { ...updated[index], text: newText }
      return updated
    })

    // requestAnimationFrameを使用して状態更新後に保存処理を実行
    requestAnimationFrame(() => {
      console.log("Saving after transcript edit at index:", index)
      saveTranscriptChanges()
    })
  }

  return (
    <div className="transcriber-container">
      <div className="transcriber-header">
        <div className="header-content">
          <img src="/images/kuri.jpg" alt="Kuri" className="header-logo" />
          <h1>Transcriber</h1>
          {saveStatus !== "idle" && (
            <div className={`save-status ${saveStatus}`}>
              {saveStatus === "saving" && "Now Saving..."}
              {saveStatus === "success" && "Saved Successfully"}
              {saveStatus === "error" && (
                <>
                  Save Failed
                  {saveError && <div className="save-error-details">{saveError}</div>}
                </>
              )}
            </div>
          )}
        </div>
      </div>
      <div className="transcriber-content">
        <div className="audio-list-container">
          <AudioList audioFiles={audioFiles} selectedAudio={selectedAudio} onSelectAudio={handleSelectAudio} />
        </div>
        <div className="transcript-container">
          <div className="transcript-header">
            <div>
              {selectedAudio} {"("}
              {duration
                ? `${Math.floor(duration / 60)}:${Math.floor(duration % 60)
                    .toString()
                    .padStart(2, "0")}`
                : ""}
              {")"}
            </div>
          </div>
          <TranscriptViewer
            transcript={transcript}
            currentTime={currentTime}
            onJumpToTime={jumpToTime}
            speakerMapping={speakerMapping}
            onTranscriptEdit={handleTranscriptEdit}
          />
          <AudioControls
            currentTime={currentTime}
            duration={duration}
            isPlaying={isPlaying}
            playbackRate={playbackRate}
            audioSrc={selectedAudio}
            onTogglePlayPause={togglePlayPause}
            onSkipBackward={() => skipTime(-5)}
            onSkipForward={() => skipTime(5)}
            onChangePlaybackRate={changePlaybackRate}
            onSeek={jumpToTime}
            onWaveformReady={handleWaveformReady}
            onTimeUpdate={handleTimeUpdate}
            onWaveformClick={handleWaveformClick}
            transcript={transcript}
          />
        </div>
        <div className="speaker-settings-container">
          <SpeakerSettings transcript={transcript} onSpeakerNameChange={handleSpeakerNameChange} />
        </div>
      </div>
    </div>
  )
}

export default App