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
import SearchBar from "./components/SearchBar"
import CodingReviewPanel from "./components/CodingReviewPanel"
import CodingTimeline from "./components/CodingTimeline"
import type { TranscriptEntry, SpeakerMapping, Bookmark, CodingData } from "./types"
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

const withReviewState = (data: CodingData): CodingData => ({
  ...data,
  intervals: data.intervals.map((item) => ({
    ...item,
    review: {
      status: item.review?.status ?? null,
      note: item.review?.note ?? "",
    },
  })),
  events: data.events.map((item) => ({
    ...item,
    review: {
      status: item.review?.status ?? null,
      note: item.review?.note ?? "",
    },
  })),
})

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
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "success" | "error">("idle")
  const [saveError, setSaveError] = useState<string | null>(null)
  const [selectedEntryIndex, setSelectedEntryIndex] = useState<number | null>(null)
  const [lastPlaybackPosition, setLastPlaybackPosition] = useState<number>(0)
  const [isLogoModalOpen, setIsLogoModalOpen] = useState(false)
  const saveInProgressRef = useRef(false)
  const [bookmarks, setBookmarks] = useState<Bookmark[]>([])
  const [coding, setCoding] = useState<CodingData | null>(null)
  // レビューパネルの高さ。仕切りバーのドラッグで変更し再訪時も保持する
  const [codingPanelHeight, setCodingPanelHeight] = useState<number | null>(() => {
    const saved = localStorage.getItem("codingPanelHeight")
    return saved ? Number(saved) : null
  })
  // タイムラインは「レーン1本の太さ」を記憶する。ファイルごとにレーン数が
  // 違っても(実験者レーンの有無など)ピルの太さが変わらないようにするため
  const [codingLaneHeight, setCodingLaneHeight] = useState<number | null>(() => {
    const saved = localStorage.getItem("codingLaneHeight")
    return saved ? Number(saved) : null
  })

  const isInitialSpeakerSave = useRef(true)
  const isInitialTranscriptSave = useRef(true)

  useEffect(() => {
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

  useEffect(() => {
    localStorage.setItem("isCollapsed", JSON.stringify(isCollapsed))
  }, [isCollapsed])

  useEffect(() => {
    if (isInitialSpeakerSave.current) {
      isInitialSpeakerSave.current = false
      return
    }
    console.log("Speaker mapping changed, triggering save:", speakerMapping)
    saveTranscriptChanges()
  }, [speakerMapping])

  useEffect(() => {
    if (isInitialTranscriptSave.current) {
      isInitialTranscriptSave.current = false
      return
    }
    console.log("Transcript changed, triggering save")
    saveTranscriptChanges()
  }, [transcript])

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

  const handleAddTag = (tag: string) => {
    if (!allTags.includes(tag)) {
      const updatedTags = [...allTags, tag]
      setAllTags(updatedTags)
      localStorage.setItem("allTags", JSON.stringify(updatedTags))
    }
  }

  const handleRemoveTag = (tag: string) => {
    const updatedTags = allTags.filter((t) => t !== tag)
    setAllTags(updatedTags)
    localStorage.setItem("allTags", JSON.stringify(updatedTags))

    const updatedAudioTags = { ...audioTags }
    Object.keys(updatedAudioTags).forEach((audio) => {
      updatedAudioTags[audio] = updatedAudioTags[audio].filter((t) => t !== tag)
    })
    setAudioTags(updatedAudioTags)
    localStorage.setItem("audioTags", JSON.stringify(updatedAudioTags))

    if (selectedTag === tag) {
      setSelectedTag(null)
    }
  }

  const handleToggleCollapse = () => {
    setIsCollapsed(!isCollapsed)
  }

  useEffect(() => {
    if (!selectedAudio) return

    const transcriptFile = selectedAudio.replace(".wav", ".json")
    console.log("Loading transcript:", transcriptFile)

    fetch(`/transcripts/${transcriptFile}`)
      .then((response) => response.json())
      .then((data) => {
        console.log("Loaded transcript data:", data)
        const entries: TranscriptEntry[] = Array.isArray(data)
          ? data
          : Array.isArray(data?.transcripts)
            ? data.transcripts
            : []
        setTranscript(entries)

        if (entries.length > 0) {
          setDuration(entries[entries.length - 1].end)
        }

        try {
          const savedSpeakerMapping = localStorage.getItem(`speakerMapping_${transcriptFile}`)
          if (savedSpeakerMapping) {
            const parsedMapping = JSON.parse(savedSpeakerMapping)
            console.log("Loaded speaker mapping from localStorage:", parsedMapping)
            setSpeakerMapping(parsedMapping)
          } else {
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

  useEffect(() => {
    if (!selectedAudio) {
      setCoding(null)
      return
    }
    const controller = new AbortController()
    const codingFile = selectedAudio.replace(/\.[^.]+$/, ".json")
    setCoding(null)

    fetch(`/coding/${codingFile}`, { signal: controller.signal })
      .then((response) => {
        if (response.status === 404) return null
        if (!response.ok) {
          throw new Error(`Failed to load coding JSON: ${response.statusText}`)
        }
        return response.json()
      })
      .then((data: CodingData | null) => {
        if (data) setCoding(withReviewState(data))
      })
      .catch((error) => {
        if ((error as Error).name !== "AbortError") {
          console.error("Error loading coding data:", error)
        }
      })

    return () => controller.abort()
  }, [selectedAudio])

  const handleSelectAudio = (audio: string) => {
    console.log("Selected audio:", audio)
    setIsPlaying(false)
    console.log("Selected audio:", audio)
    setIsPlaying(false)
    setCurrentTime(0)
    setLastPlaybackPosition(0)
    setSelectedAudio(audio)
  }

  // 仕切りバーのドラッグでレビューパネルの高さを変える。仕切りはパネルの上辺に
  // あるので上へドラッグ=拡大。開始時の実測高さを基準に差分を適用する
  const startPaneDrag = (event: React.MouseEvent) => {
    event.preventDefault()
    const element = document.querySelector(".coding-review-panel")
    if (!element) return
    const startHeight = element.getBoundingClientRect().height
    const startY = event.clientY
    const onMove = (moveEvent: MouseEvent) => {
      const next = Math.round(startHeight - (moveEvent.clientY - startY))
      const clamped = Math.max(120, Math.min(Math.round(window.innerHeight * 0.75), next))
      setCodingPanelHeight(clamped)
      localStorage.setItem("codingPanelHeight", String(clamped))
    }
    const onUp = () => {
      document.removeEventListener("mousemove", onMove)
      document.removeEventListener("mouseup", onUp)
    }
    document.addEventListener("mousemove", onMove)
    document.addEventListener("mouseup", onUp)
  }

  // タイムライン下辺の仕切り: 下へドラッグ=拡大。実測レーン高さを基準に、
  // ドラッグ量をレーン数で割ってレーン1本の太さへ換算する
  const startTimelineDrag = (event: React.MouseEvent) => {
    event.preventDefault()
    const lanes = document.querySelectorAll(".coding-timeline .coding-lane")
    if (lanes.length === 0) return
    const startLaneHeight = lanes[0].getBoundingClientRect().height
    const startY = event.clientY
    const onMove = (moveEvent: MouseEvent) => {
      const perLane = (moveEvent.clientY - startY) / lanes.length
      const clamped = Math.round(Math.max(14, Math.min(64, startLaneHeight + perLane)))
      setCodingLaneHeight(clamped)
      localStorage.setItem("codingLaneHeight", String(clamped))
    }
    const onUp = () => {
      document.removeEventListener("mousemove", onMove)
      document.removeEventListener("mouseup", onUp)
    }
    document.addEventListener("mousemove", onMove)
    document.addEventListener("mouseup", onUp)
  }

  const handleTimeUpdate = (time: number) => {
    setCurrentTime(time)
    if (isPlaying) {
      setLastPlaybackPosition(time)
    }
  }

  const handleWaveformReady = (audioDuration: number) => {
    console.log("Waveform ready, duration:", audioDuration)
    setDuration(audioDuration)
  }

  const jumpToTime = (time: number) => {
    console.log("Jumping to time:", time)
    setCurrentTime(time)
    setLastPlaybackPosition(time)
  }

  const togglePlayPause = () => {
    console.log("Toggle play/pause, current state:", isPlaying)
    if (isPlaying) {
      setLastPlaybackPosition(currentTime)
    } else {
      setCurrentTime(lastPlaybackPosition)
    }
    setIsPlaying(!isPlaying)
  }

  const skipTime = (seconds: number) => {
    console.log("Skipping time by seconds:", seconds)
    const newTime = Math.max(0, Math.min(currentTime + seconds, duration))
    setCurrentTime(newTime)
    setLastPlaybackPosition(newTime)
  }

  const changePlaybackRate = (rate: number) => {
    console.log("Changing playback rate to:", rate)
    setPlaybackRate(rate)
  }

  const handleWaveformClick = (time: number) => {
    console.log("Waveform clicked, time:", time);

    setCurrentTime(time);
    setLastPlaybackPosition(time);

    const entries = document.querySelectorAll<HTMLElement>(".transcript-entry");
    for (let i = 0; i < entries.length; i++) {
      const entryEl = entries[i];
      const startAttr = entryEl.dataset.start;
      const endAttr = entryEl.dataset.end;
      if (!startAttr || !endAttr) continue;

      const start = parseFloat(startAttr);
      const end = parseFloat(endAttr);
      if (time >= start && time < end) {
        setSelectedEntryIndex(i);
        entryEl.scrollIntoView({ behavior: "smooth", block: "center" });
        return;
      }
    }
    setSelectedEntryIndex(null);
  };

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

  const saveTranscriptChanges = async (transcriptToSave: TranscriptEntry[] = transcript) => {
    if (!selectedAudio || saveInProgressRef.current) {
      console.log("Save already in progress or no audio selected, skipping")
      return
    }
    const transcriptFile = selectedAudio.replace(".wav", ".json")
    console.log("Saving transcript changes to:", transcriptFile)
    saveInProgressRef.current = true
    setSaveStatus("saving")
    setSaveError(null)
    try {
      await checkServerStatus()

      const requestData = {
        filename: transcriptFile,
        data: transcriptToSave,
      }

      const response = await fetch("/api/save-transcript", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestData),
      })

      const responseData = await response.json()

      if (!response.ok) {
        throw new Error(`Failed to save transcript: ${responseData.error || response.statusText}`)
      }

      console.log("Transcript saved successfully:", responseData)

      localStorage.setItem(`speakerMapping_${transcriptFile}`, JSON.stringify(speakerMapping))
      setSaveStatus("success")
      setTimeout(() => setSaveStatus("idle"), 3000)
    } catch (error) {
      console.error("Error saving transcript:", error)
      setSaveStatus("error")
      setSaveError((error as Error).message)
      setTimeout(() => {
        setSaveStatus("idle")
        setSaveError(null)
      }, 5000)
    } finally {
      saveInProgressRef.current = false
    }
  }

  const handleSpeakerNameChange = (originalName: string, newName: string) => {
    console.log(`Changing speaker name from ${originalName} to ${newName}`)
    setSpeakerMapping((prev) => ({
      ...prev,
      [originalName]: newName,
    }))

    requestAnimationFrame(() => {
      console.log("Saving after speaker name change")
      saveTranscriptChanges()
    })
  }

  const handleTranscriptEdit = (index: number, patch: Partial<TranscriptEntry>) => {
    console.log(`Editing transcript at index ${index}:`, patch)

    if (patch.speaker) {
      console.log(`Speaker changed at index ${index} from:`, transcript[index].speaker, "to:", patch.speaker)
    }

    setTranscript((prev) => {
      const updated = [...prev]
      updated[index] = { ...updated[index], ...patch }
      return updated
    })

    setTimeout(() => {
      console.log("Saving after transcript edit at index:", index)
      saveTranscriptChanges()
    }, 100)
  }

  const handleDeleteEntry = (index: number) => {
    console.log(`Deleting entry at index ${index}`)
  
    setTranscript((prev) => {
      const updated = [...prev]
      updated.splice(index, 1)
      setTimeout(() => {
        console.log("Saving after deleting entry")
        saveTranscriptChanges(updated)
      }, 100)
      return updated
    })
  
    if (selectedEntryIndex === index) {
      setSelectedEntryIndex(null)
    } else if (selectedEntryIndex !== null && selectedEntryIndex > index) {
      setSelectedEntryIndex(selectedEntryIndex - 1)
    }
  }

  const handleAddEntryBetween = (index: number) => {
    console.log(`Adding new entry after index ${index}`)
  
    let startTime = 0
    let endTime = 0
  
    const prev = transcript[index - 1]
  
    if (prev) {
      startTime = prev.end
    }
  
    if (index < transcript.length) {
      endTime = transcript[index].start
    } else {
      endTime = startTime + 2.0
    }
  
    const newEntry: TranscriptEntry = {
      start: startTime,
      end: endTime,
      speaker: prev?.speaker || "",
      text: "",
    }
  
    setTranscript((prev) => {
      const updated = [...prev]
      updated.splice(index, 0, newEntry)
      
      setTimeout(() => {
        console.log("Saving after adding new entry")
        saveTranscriptChanges(updated)
      }, 100)
    
      return updated
    })
  
    setSelectedEntryIndex(index)
    setTimeout(() => {
      console.log("Saving after adding new entry")
      saveTranscriptChanges()
    }, 100)
  }

  const handleBookmarkEntry = (index: number) => {
    if (index < 0 || index >= transcript.length) return

    const entry = transcript[index]

    const existingBookmarkIndex = bookmarks.findIndex(
      (bookmark) => bookmark.audioFile === selectedAudio && bookmark.entryIndex === index,
    )

    if (existingBookmarkIndex !== -1) {
      console.log("Removing existing bookmark at index:", existingBookmarkIndex)
      const updatedBookmarks = removeBookmarkService(bookmarks, existingBookmarkIndex)
      setBookmarks(updatedBookmarks)
    } else {
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

    if (audioFile !== selectedAudio) {
      setSelectedAudio(audioFile)
      setTimeout(() => {
        setSelectedEntryIndex(entryIndex)
        jumpToTime(time)
      }, 500)
    } else {
      setSelectedEntryIndex(entryIndex)
      jumpToTime(time)
    }
  }

  const handleSearchResultSelect = (audioFile: string, entryIndex: number, time: number) => {
    console.log("Jumping to search result:", audioFile, entryIndex, time)

    if (audioFile !== selectedAudio) {
      setSelectedAudio(audioFile)
      setTimeout(() => {
        setSelectedEntryIndex(entryIndex)
        jumpToTime(time)
      }, 500)
    } else {
      setSelectedEntryIndex(entryIndex)
      jumpToTime(time)
    }
  }

  const handleAddTagToAudio = (audio: string, tag: string) => {
    const { updatedAudioTags, updatedAllTags } = addTagService(audioTags, allTags, audio, tag)
    setAudioTags(updatedAudioTags)
    setAllTags(updatedAllTags)
  }

  const handleRemoveTagFromAudio = (audio: string, tag: string) => {
    const updatedAudioTags = removeTagService(audioTags, audio, tag)
    setAudioTags(updatedAudioTags)
  }

  return (
    <div className="transcriber-container">
      <div className="transcriber-header">
        <div className="header-content">
          <div className="header-left">
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
          <div className="header-right">
            <SearchBar audioFiles={audioFiles} onJumpToResult={handleSearchResultSelect} />
          </div>
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
        <div
          className="transcript-container"
          style={
            {
              ...(codingPanelHeight ? { "--coding-panel-height": `${codingPanelHeight}px` } : {}),
              ...(codingLaneHeight ? { "--coding-lane-height": `${codingLaneHeight}px` } : {}),
            } as React.CSSProperties
          }
        >
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
          {coding && (
            <CodingTimeline
              coding={coding}
              duration={duration}
              currentTime={currentTime}
              onSeek={jumpToTime}
            />
          )}
          {coding && (
            <div
              className="pane-divider"
              role="separator"
              aria-orientation="horizontal"
              title="ドラッグでタイムラインの太さを変更"
              onMouseDown={startTimelineDrag}
            />
          )}
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
          {coding && (
            <div
              className="pane-divider"
              role="separator"
              aria-orientation="horizontal"
              title="ドラッグで文字起こしとレビューの高さを変更"
              onMouseDown={startPaneDrag}
            />
          )}
          {coding && (
            <CodingReviewPanel
              coding={coding}
              currentTime={currentTime}
              duration={duration}
              onSeek={jumpToTime}
              onChange={setCoding}
            />
          )}
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
