// コンポーネント統合
"use client"

import { useState, useEffect, useRef } from "react"
import "./App.css"
import AudioList from "./components/AudioList"
import TranscriptViewer from "./components/TranscriptViewer"
import SpeakerSettings from "./components/SpeakerSettings"
import AudioControls from "./components/AudioControls"
import BookmarkList from "./components/BookmarkList"
import TagList from "./components/TagList"
import ImageModal from "./components/ImageModal"
import type { TranscriptEntry, SpeakerMapping, Bookmark } from "./types"
import {
  loadAudioTags,
  loadAllTags,
  addTagToAudio as addTagService,
  removeTagFromAudio as removeTagService,
} from "./services/tagService"
import {
  loadBookmarks,
  addBookmark as addBookmarkService,
  removeBookmark as removeBookmarkService,
} from "./services/bookmarkService"

function App() {
  const [isCollapsed, setIsCollapsed] = useState(false)
  const [audioTags, setAudioTags] = useState<Record<string, string[]>>({})
  const [allTags, setAllTags] = useState<string[]>([])
  const [selectedTag, setSelectedTag] = useState<string | null>(null)
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
  const [selectedEntryIndex, setSelectedEntryIndex] = useState<number | null>(null)
  const [lastPlaybackPosition, setLastPlaybackPosition] = useState<number>(0)
  const [isLogoModalOpen, setIsLogoModalOpen] = useState(false)
  const saveInProgressRef = useRef(false)
  const transcriptViewerRef = useRef<HTMLDivElement>(null)
  const [bookmarks, setBookmarks] = useState<Bookmark[]>([])

  const isInitialSpeakerSave = useRef(true)
  const isInitialTranscriptSave = useRef(true)

  // Load data from localStorage on component mount
  useEffect(() => {
    // Load tags data
    const loadedAudioTags = loadAudioTags()
    const loadedAllTags = loadAllTags()
    const loadedBookmarks = loadBookmarks()
    const savedIsCollapsed = localStorage.getItem("isCollapsed")

    setAudioTags(loadedAudioTags)
    setAllTags(loadedAllTags)
    setBookmarks(loadedBookmarks)

    if (savedIsCollapsed) {
      try {
        setIsCollapsed(JSON.parse(savedIsCollapsed))
      } catch (error) {
        console.error("Error parsing saved collapsed state:", error)
      }
    }
  }, [])

  // Save isCollapsed state to localStorage when changed
  useEffect(() => {
    localStorage.setItem("isCollapsed", JSON.stringify(isCollapsed))
  }, [isCollapsed])

  // Trigger save after speakerMapping changes (skip initial load)
  useEffect(() => {
    if (isInitialSpeakerSave.current) {
      isInitialSpeakerSave.current = false
      return
    }
    console.log("Speaker mapping changed, triggering save:", speakerMapping)
    saveTranscriptChanges()
  }, [speakerMapping])

  // Trigger save after transcript changes (skip initial load)
  useEffect(() => {
    if (isInitialTranscriptSave.current) {
      isInitialTranscriptSave.current = false
      return
    }
    console.log("Transcript changed, triggering save")
    saveTranscriptChanges()
  }, [transcript])

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

  // タグ関連の処理
  const handleAddTag = (tag: string) => {
    if (!allTags.includes(tag)) {
      const updatedTags = [...allTags, tag]
      setAllTags(updatedTags)
      localStorage.setItem("allTags", JSON.stringify(updatedTags))
    }
  }

  const handleRemoveTag = (tag: string) => {
    // タグを削除し、関連する音声ファイルからもタグを削除
    const updatedTags = allTags.filter((t) => t !== tag)
    setAllTags(updatedTags)
    localStorage.setItem("allTags", JSON.stringify(updatedTags))

    // すべての音声ファイルからこのタグを削除
    const updatedAudioTags = { ...audioTags }
    Object.keys(updatedAudioTags).forEach((audio) => {
      updatedAudioTags[audio] = updatedAudioTags[audio].filter((t) => t !== tag)
    })
    setAudioTags(updatedAudioTags)
    localStorage.setItem("audioTags", JSON.stringify(updatedAudioTags))

    // 選択中のタグが削除された場合、選択を解除
    if (selectedTag === tag) {
      setSelectedTag(null)
    }
  }

  const handleToggleCollapse = () => {
    setIsCollapsed(!isCollapsed)
  }

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

        // ローカルストレージから話者マッピング情報を読み込む
        try {
          const savedSpeakerMapping = localStorage.getItem(`speakerMapping_${transcriptFile}`)
          if (savedSpeakerMapping) {
            const parsedMapping = JSON.parse(savedSpeakerMapping)
            console.log("Loaded speaker mapping from localStorage:", parsedMapping)
            setSpeakerMapping(parsedMapping)
          } else {
            // 保存されたマッピングがない場合は空のオブジェクトを設定
            console.log("No saved speaker mapping found, using empty mapping")
            setSpeakerMapping({})
          }
        } catch (error) {
          console.warn("Failed to load speaker mapping from localStorage:", error)
          setSpeakerMapping({})
        }

        setSaveStatus("idle")
        setSaveError(null)
        isInitialTranscriptSave.current = true
        isInitialSpeakerSave.current = true
      })
      .catch((error) => console.error("Error loading transcript:", error))
  }, [selectedAudio])

  // Handle audio selection
  const handleSelectAudio = (audio: string) => {
    console.log("Selected audio:", audio)
    setIsPlaying(false) // Stop playback when changing  => {
    console.log("Selected audio:", audio)
    setIsPlaying(false) // Stop playback when changing audio
    setCurrentTime(0)
    setLastPlaybackPosition(0)
    setSelectedAudio(audio)
  }

  // Handle time update from wavesurfer
  const handleTimeUpdate = (time: number) => {
    setCurrentTime(time)
    // 再生中は最後の再生位置を更新
    if (isPlaying) {
      setLastPlaybackPosition(time)
    }
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
    setLastPlaybackPosition(time)
  }

  // Toggle play/pause
  const togglePlayPause = () => {
    console.log("Toggle play/pause, current state:", isPlaying)
    if (isPlaying) {
      // 停止時は現在の再生位置を保存
      setLastPlaybackPosition(currentTime)
    } else {
      // 再生開始時は最後に停止した位置から再生
      setCurrentTime(lastPlaybackPosition)
    }
    setIsPlaying(!isPlaying)
  }

  // Skip forward/backward
  const skipTime = (seconds: number) => {
    console.log("Skipping time by seconds:", seconds)
    const newTime = Math.max(0, Math.min(currentTime + seconds, duration))
    setCurrentTime(newTime)
    setLastPlaybackPosition(newTime)
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

      // 選択状態を更新
      setSelectedEntryIndex(entryIndex)

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

          // 時間を更新
          setCurrentTime(time)
          setLastPlaybackPosition(time)
        }
      }
    } else {
      // 対応するエントリがない場合は選択状態をクリア
      setSelectedEntryIndex(null)
      setCurrentTime(time)
      setLastPlaybackPosition(time)
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

  // Save transcript changes to file - 修正版
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

      // 重要: 保存前にトランスクリプトの状態をログ出力
      console.log("Current transcript before save:", transcriptToSave)
      console.log("Current speaker mapping:", speakerMapping)

      // サーバーAPIが期待する形式に合わせてデータを整形
      // APIは filename と data フィールドを期待している
      const requestData = {
        filename: transcriptFile,
        data: transcriptToSave, // トランスクリプトデータのみを送信
      }

      console.log("Sending data to server:", requestData)

      const response = await fetch("/api/save-transcript", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestData),
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

      // 話者マッピング情報をローカルストレージに保存
      // サーバーAPIが話者マッピングをサポートしていない場合の代替手段
      try {
        localStorage.setItem(`speakerMapping_${transcriptFile}`, JSON.stringify(speakerMapping))
        console.log("Speaker mapping saved to localStorage")
      } catch (error) {
        console.warn("Failed to save speaker mapping to localStorage:", error)
      }

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

  // Handle transcript edit - 修正版
  const handleTranscriptEdit = (index: number, patch: Partial<TranscriptEntry>) => {
    console.log(`Editing transcript at index ${index}:`, patch)

    // 話者が変更された場合、詳細なログを出力
    if (patch.speaker) {
      console.log(`Speaker changed at index ${index} from:`, transcript[index].speaker, "to:", patch.speaker)
    }

    // トランスクリプトの状態を更新
    setTranscript((prev) => {
      const updated = [...prev]
      updated[index] = { ...updated[index], ...patch }
      return updated
    })

    // 状態更新後に保存処理を実行するために少し遅延させる
    setTimeout(() => {
      console.log("Saving after transcript edit at index:", index)
      saveTranscriptChanges()
    }, 100)
  }

  // App.tsxに削除処理のハンドラーを追加

  // handleTranscriptEdit の後に以下の関数を追加
  const handleDeleteEntry = (index: number) => {
    console.log(`Deleting entry at index ${index}`)

    // トランスクリプトの状態を更新
    setTranscript((prev) => {
      const updated = [...prev]
      // 指定されたインデックスのエントリーを削除
      updated.splice(index, 1)
      return updated
    })

    // 選択状態をクリア
    if (selectedEntryIndex === index) {
      setSelectedEntryIndex(null)
    } else if (selectedEntryIndex !== null && selectedEntryIndex > index) {
      // 削除されたエントリーより後ろのエントリーが選択されていた場合、インデックスを調整
      setSelectedEntryIndex(selectedEntryIndex - 1)
    }

    // 変更を保存
    setTimeout(() => {
      console.log("Saving after deleting entry")
      saveTranscriptChanges()
    }, 100)
  }

  // 新しいトランスクリプトエントリーを追加
  const handleAddEntryBetween = (index: number) => {
    console.log(`Adding new entry after index ${index}`)

    // 新しいエントリーの開始時間と終了時間を計算
    let startTime = 0
    let endTime = 0

    if (index < transcript.length) {
      // 既存のエントリーの終了時間を新しいエントリーの開始時間として使用
      startTime = transcript[index].end

      if (index + 1 < transcript.length) {
        // 次のエントリーの開始時間を新しいエントリーの終了時間として使用
        endTime = transcript[index + 1].start
      } else {
        // 最後のエントリーの場合、終了時間を少し延長
        endTime = startTime + 2.0
      }
    }

    // 新しい空のエントリーを作成
    const newEntry: TranscriptEntry = {
      start: startTime,
      end: endTime,
      speaker: transcript[index]?.speaker || "",
      text: "",
    }

    // トランスクリプトの状態を更新
    setTranscript((prev) => {
      const updated = [...prev]
      // index+1 の位置に新しいエントリーを挿入
      updated.splice(index + 1, 0, newEntry)
      return updated
    })

    // 新しいエントリーを選択状態にする
    setSelectedEntryIndex(index + 1)

    // 変更を保存
    setTimeout(() => {
      console.log("Saving after adding new entry")
      saveTranscriptChanges()
    }, 100)
  }

  // ブックマーク関連の処理
  const handleBookmarkEntry = (index: number) => {
    if (index < 0 || index >= transcript.length) return

    const entry = transcript[index]

    // 既存のブックマークをチェック
    const existingBookmarkIndex = bookmarks.findIndex(
      (bookmark) => bookmark.audioFile === selectedAudio && bookmark.entryIndex === index,
    )

    if (existingBookmarkIndex !== -1) {
      // 既に存在する場合は削除（トグル機能）
      console.log("Removing existing bookmark at index:", existingBookmarkIndex)
      const updatedBookmarks = removeBookmarkService(bookmarks, existingBookmarkIndex)
      setBookmarks(updatedBookmarks)
    } else {
      // 存在しない場合は新規追加
      console.log("Adding new bookmark for entry at index:", index)
      const updatedBookmarks = addBookmarkService(bookmarks, selectedAudio, index, entry)
      setBookmarks(updatedBookmarks)
    }
  }

  const handleRemoveBookmark = (bookmarkIndex: number) => {
    console.log("Removing bookmark at index:", bookmarkIndex)
    const updatedBookmarks = removeBookmarkService(bookmarks, bookmarkIndex)
    setBookmarks(updatedBookmarks)
  }

  const handleJumpToBookmark = (audioFile: string, entryIndex: number, time: number) => {
    console.log("Jumping to bookmark:", audioFile, entryIndex, time)

    // 異なる音声ファイルの場合は、まずそのファイルを選択
    if (audioFile !== selectedAudio) {
      setSelectedAudio(audioFile)
      // 音声ファイルが変更されるとトランスクリプトも再読み込みされるため、
      // useEffectの後に実行されるようにタイマーを設定
      setTimeout(() => {
        setSelectedEntryIndex(entryIndex)
        jumpToTime(time)
      }, 500)
    } else {
      // 同じ音声ファイルの場合は直接ジャンプ
      setSelectedEntryIndex(entryIndex)
      jumpToTime(time)
    }
  }

  const handleAddTagToAudio = (audio: string, tag: string) => {
    // Use the service to add tag and get updated state
    const { updatedAudioTags, updatedAllTags } = addTagService(audioTags, allTags, audio, tag)
    setAudioTags(updatedAudioTags)
    setAllTags(updatedAllTags)
  }

  const handleRemoveTagFromAudio = (audio: string, tag: string) => {
    // Use the service to remove tag and get updated state
    const updatedAudioTags = removeTagService(audioTags, audio, tag)
    setAudioTags(updatedAudioTags)
  }

  return (
    <div className="transcriber-container">
      <div className="transcriber-header">
        <div className="header-content">
          <img src="/images/kuri.jpg" alt="Kuri" className="header-logo" onClick={() => setIsLogoModalOpen(true)} />
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
        <div className={`audio-list-container ${isCollapsed ? "collapsed" : ""}`}>
          <AudioList
            audioFiles={audioFiles}
            selectedAudio={selectedAudio}
            onSelectAudio={handleSelectAudio}
            isCollapsed={isCollapsed}
            onToggleCollapse={handleToggleCollapse}
            audioTags={audioTags}
            allTags={allTags}
            onAddTagToAudio={handleAddTagToAudio}
            onRemoveTagFromAudio={handleRemoveTagFromAudio}
            selectedTag={selectedTag}
          />
          {!isCollapsed && (
            <div className="tag-list-container">
              <TagList
                allTags={allTags}
                selectedTag={selectedTag}
                onSelectTag={setSelectedTag}
                onAddTag={handleAddTag}
                onRemoveTag={handleRemoveTag}
              />
            </div>
          )}
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
          {/* TranscriptViewerコンポーネントにonDeleteEntryプロパティを追加 */}
          {/* <TranscriptViewer の部分を以下のように修正 */}
          <TranscriptViewer
            transcript={transcript}
            currentTime={currentTime}
            onJumpToTime={jumpToTime}
            speakerMapping={speakerMapping}
            onTranscriptEdit={handleTranscriptEdit}
            selectedEntryIndex={selectedEntryIndex}
            onSelectEntry={setSelectedEntryIndex}
            onBookmarkEntry={handleBookmarkEntry}
            bookmarks={bookmarks}
            currentAudioFile={selectedAudio}
            onAddEntryBetween={handleAddEntryBetween}
            onDeleteEntry={handleDeleteEntry}
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
            lastPlaybackPosition={lastPlaybackPosition}
          />
        </div>
        <div className="speaker-settings-container">
          <div className="speaker-settings">
            <SpeakerSettings transcript={transcript} onSpeakerNameChange={handleSpeakerNameChange} />
          </div>
          <div className="bookmark-list-container">
            <BookmarkList
              bookmarks={bookmarks}
              onJumpToBookmark={handleJumpToBookmark}
              onRemoveBookmark={handleRemoveBookmark}
              currentAudioFile={selectedAudio}
            />
          </div>
        </div>
      </div>

      {/* ロゴ画像のモーダル */}
      <ImageModal
        src="/images/kuri.jpg"
        alt="Kuri"
        isOpen={isLogoModalOpen}
        onClose={() => setIsLogoModalOpen(false)}
      />
    </div>
  )
}

export default App