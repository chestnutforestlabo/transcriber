// TranscriptViewer.tsx - 話者プルダウンと選択肢のスタイルを黒背景・白文字に変更
"use client"

import type React from "react"
import { useRef, useEffect, useState } from "react"
import { Edit, Copy, Bookmark, Save, X } from "lucide-react"
import { createPortal } from "react-dom" // Portalをインポート

/* =============================================================
 * 型定義
 * ===========================================================*/
export interface TranscriptEntry {
  time?: string // フォーマット済み文字列（任意）
  start: number // 開始時刻 [sec]
  end: number // 終了時刻 [sec]
  speaker: string // 話者 ID
  text: string // 本文
}

interface TranscriptViewerProps {
  transcript: TranscriptEntry[]
  currentTime: number
  onJumpToTime: (time: number) => void
  speakerMapping: Record<string, string>
  onTranscriptEdit: (index: number, patch: Partial<TranscriptEntry>) => void
  selectedEntryIndex: number | null
  onSelectEntry: (index: number | null) => void
  onBookmarkEntry: (index: number) => void
  bookmarks: Bookmark[] // 追加: ブックマークリスト
  currentAudioFile: string // 追加: 現在の音声ファイル
}

/* =============================================================
 * Helper
 * ===========================================================*/
const secToClock = (sec: number) => `${Math.floor(sec / 60)}:${String(Math.floor(sec % 60)).padStart(2, "0")}`

const clockToSec = (clock: string) => {
  const [m, s] = clock.split(":")
  return +m * 60 + +s
}

/* =============================================================
 * Component
 * ===========================================================*/
const TranscriptViewer: React.FC<TranscriptViewerProps> = ({
  transcript,
  currentTime,
  onJumpToTime,
  speakerMapping,
  onTranscriptEdit,
  selectedEntryIndex,
  onSelectEntry,
  onBookmarkEntry,
  bookmarks, // 追加
  currentAudioFile, // 追加
}) => {
  // speakerMappingの内容をログ出力
  console.log("TranscriptViewer received speakerMapping:", speakerMapping)

  /* -------------------- refs & state -------------------- */
  const containerRef = useRef<HTMLDivElement>(null)
  const activeEntryRef = useRef<HTMLDivElement>(null)
  const editContainerRef = useRef<HTMLDivElement>(null)
  const speakerButtonRef = useRef<HTMLButtonElement>(null) // 話者ボタンの参照を追加
  const dropdownRef = useRef<HTMLDivElement>(null) // ドロップダウン要素のref

  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null)
  const [editingIndex, setEditingIndex] = useState<number | null>(null)

  const [editText, setEditText] = useState("")
  const [editSpeaker, setEditSpeaker] = useState("")
  const [editStartClock, setEditStartClock] = useState("")

  const [autoScroll, setAutoScroll] = useState(true)
  const lastActiveIndexRef = useRef<number>(-1)

  /* speaker dropdown popover */
  const [speakerDropdownOpen, setSpeakerDropdownOpen] = useState(false)
  const [dropdownPosition, setDropdownPosition] = useState({ top: 0, left: 0, width: 0 }) // 幅も追加
  const [isDropdownItemClicked, setIsDropdownItemClicked] = useState(false) // ドロップダウンアイテムがクリックされたかのフラグ

  /* -------------------- active entry auto‑scroll -------------------- */
  const activeEntryIndex = transcript.findIndex((entry) => currentTime >= entry.start && currentTime < entry.end)

  useEffect(() => {
    if (activeEntryIndex !== -1 && activeEntryIndex !== lastActiveIndexRef.current) {
      lastActiveIndexRef.current = activeEntryIndex
      if (activeEntryRef.current && containerRef.current && autoScroll) {
        activeEntryRef.current.scrollIntoView({ behavior: "smooth", block: "center" })
      }
    }
  }, [activeEntryIndex, autoScroll])

  /* -------------------- click‑outside to exit edit / close dropdown -------------------- */
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      // ドロップダウンの外側をクリックした場合のみ処理
      if (speakerDropdownOpen) {
        const dropdownElement = document.getElementById("speaker-dropdown-portal")
        const speakerButtonElement = speakerButtonRef.current

        // ドロップダウンとボタン以外の場所をクリックした場合にのみドロップダウンを閉じる
        if (
          (!speakerButtonElement || !speakerButtonElement.contains(e.target as Node)) &&
          (!dropdownElement || !dropdownElement.contains(e.target as Node))
        ) {
          console.log("Click outside dropdown detected")
          setSpeakerDropdownOpen(false)
        }
      }

      // 編集コンテナの外側をクリックした場合のみ処理
      // ドロップダウンアイテムがクリックされた場合は編集モードを終了しない
      if (editContainerRef.current && !editContainerRef.current.contains(e.target as Node) && !isDropdownItemClicked) {
        const dropdownElement = document.getElementById("speaker-dropdown-portal")

        // ドロップダウン内のクリックでなければ編集モードを終了
        if (!dropdownElement || !dropdownElement.contains(e.target as Node)) {
          console.log("Click outside edit container detected")
          setTimeout(() => {
            setEditingIndex(null)
          }, 100)
        }
      }

      // フラグをリセット
      setIsDropdownItemClicked(false)
    }

    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [speakerDropdownOpen, isDropdownItemClicked])

  /* -------------------- update dropdown position when button is clicked -------------------- */
  useEffect(() => {
    if (speakerButtonRef.current) {
      const updatePosition = () => {
        const rect = speakerButtonRef.current?.getBoundingClientRect()
        if (rect) {
          setDropdownPosition({
            top: rect.bottom + window.scrollY,
            left: rect.left + window.scrollX,
            width: rect.width, // ボタンの幅を取得
          })
          console.log("Button position:", {
            top: rect.bottom + window.scrollY,
            left: rect.left + window.scrollX,
            width: rect.width,
          })
        }
      }

      // 初期位置を設定
      updatePosition()

      // ドロップダウンが開かれたときに位置を更新
      if (speakerDropdownOpen) {
        updatePosition()
        console.log("Dropdown opened, position updated")
      }

      // スクロールやリサイズ時にも位置を更新
      window.addEventListener("scroll", updatePosition)
      window.addEventListener("resize", updatePosition)

      return () => {
        window.removeEventListener("scroll", updatePosition)
        window.removeEventListener("resize", updatePosition)
      }
    }
  }, [speakerDropdownOpen, speakerButtonRef.current])

  /* -------------------- interactions -------------------- */
  const enterEditMode = (idx: number, entry: TranscriptEntry) => {
    setEditingIndex(idx)
    setEditStartClock(secToClock(entry.start))
    setEditSpeaker(entry.speaker ?? "")
    setEditText(entry.text)
    setSpeakerDropdownOpen(false)
  }

  const handleEditClick = (idx: number, entry: TranscriptEntry, e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation()
    enterEditMode(idx, entry)
  }

  const handleDoubleClick = (idx: number, entry: TranscriptEntry, e: React.MouseEvent) => {
    e.stopPropagation()
    enterEditMode(idx, entry)
  }

  const handleEditSave = (idx: number, e: React.MouseEvent) => {
    e.stopPropagation()
    const newStart = clockToSec(editStartClock)
    if (!editText.trim() || !editSpeaker || isNaN(newStart)) return

    console.log("Saving edit with speaker:", editSpeaker, "text:", editText)

    // 変更内容をまとめて適用
    onTranscriptEdit(idx, {
      start: newStart,
      speaker: editSpeaker,
      text: editText,
    })

    // 前のエントリの終了時間も更新
    if (idx > 0) onTranscriptEdit(idx - 1, { end: newStart })

    setEditingIndex(null)
    setSpeakerDropdownOpen(false)
  }

  const handleEditCancel = (e: React.MouseEvent) => {
    e.stopPropagation()
    setEditingIndex(null)
    setSpeakerDropdownOpen(false)
  }

  const handleCopy = (text: string, e: React.MouseEvent) => {
    e.stopPropagation()
    navigator.clipboard.writeText(text)
  }

  const handleEntryClick = (entry: TranscriptEntry, index: number, e: React.MouseEvent<HTMLDivElement>) => {
    if (editingIndex !== null) return
    e.preventDefault()
    e.stopPropagation()
    onSelectEntry(index)
    onJumpToTime(entry.start)
    setAutoScroll(false)
    setTimeout(() => setAutoScroll(true), 2000)
  }

  // エントリがブックマークされているかチェックする関数
  const isBookmarked = (index: number) => {
    return bookmarks.some((bookmark) => bookmark.audioFile === currentAudioFile && bookmark.entryIndex === index)
  }

  // renderSpeakerDropdownPortal関数を修正して、話者選択後も編集モードが維持されるようにします
  const renderSpeakerDropdownPortal = () => {
    // クライアントサイドでのみ実行
    if (typeof document === "undefined") return null

    // ドロップダウンが閉じている場合は何もレンダリングしない
    if (!speakerDropdownOpen) return null

    // トランスクリプトから一意の話者IDを抽出
    const uniqueSpeakerIds = [...new Set(transcript.map((entry) => entry.speaker).filter(Boolean))] as string[]

    console.log("Unique speaker IDs:", uniqueSpeakerIds)
    console.log("Speaker mapping:", speakerMapping)

    // 話者リストを作成
    // speakerMappingに登録されている話者名を表示名として使用
    const availableSpeakers = uniqueSpeakerIds.map((id) => {
      const displayName = speakerMapping[id] || id
      return [id, displayName]
    })

    console.log("Available speakers for dropdown:", availableSpeakers)

    return createPortal(
      <div
        id="speaker-dropdown-portal"
        ref={dropdownRef}
        style={{
          position: "absolute",
          top: `${dropdownPosition.top}px`,
          left: `${dropdownPosition.left}px`,
          zIndex: 2147483647, // 最大値
          background: "#222222", // 黒背景に変更
          border: "1px solid #444444", // ボーダーも暗めに
          borderRadius: "4px",
          boxShadow: "0 4px 8px rgba(0,0,0,0.3)",
          maxHeight: "200px",
          overflowY: "auto",
          minWidth: `${Math.max(dropdownPosition.width, 120)}px`, // ボタンの幅か120pxの大きい方
          width: "auto",
          padding: "4px 0",
          display: "block", // 明示的に表示
          visibility: "visible", // 明示的に可視化
          opacity: 1, // 完全に不透明
        }}
        onClick={(e) => {
          e.preventDefault()
          e.stopPropagation()
        }}
      >
        {/* 話者リスト */}
        {availableSpeakers.length > 0 ? (
          availableSpeakers.map(([id, label]) => (
            <div
              key={id}
              style={{
                padding: "8px 12px",
                cursor: "pointer",
                backgroundColor: editSpeaker === id ? "rgba(74, 131, 255, 0.2)" : "transparent", // 選択項目のハイライトを調整
                color: "#ffffff", // 文字色を白に変更
                fontSize: "14px",
                textAlign: "left",
                margin: "2px 0",
                borderBottom: "1px solid #333333", // 区切り線も暗めに
              }}
              onClick={(e) => {
                // ドロップダウンアイテムがクリックされたフラグを設定
                e.preventDefault()
                e.stopPropagation()
                setIsDropdownItemClicked(true)

                console.log("Selected speaker:", id, "with label:", label)
                setEditSpeaker(id)
                setSpeakerDropdownOpen(false)

                // 編集モードは継続
                console.log("Editing mode maintained after speaker selection")
              }}
              onMouseOver={(e) => {
                e.currentTarget.style.backgroundColor = "rgba(74, 131, 255, 0.1)" // ホバー時の背景色
              }}
              onMouseOut={(e) => {
                e.currentTarget.style.backgroundColor = editSpeaker === id ? "rgba(74, 131, 255, 0.2)" : "transparent"
              }}
            >
              {typeof label === "string" && label.trim() ? label : id}
            </div>
          ))
        ) : (
          // 話者がない場合のフォールバック
          <div style={{ padding: "8px 12px", color: "#aaaaaa", fontStyle: "italic" }}>話者が定義されていません</div>
        )}
      </div>,
      document.body,
    )
  }

  /* -------------------- render -------------------- */
  return (
    <div className="transcript-viewer" ref={containerRef}>
      {/* ポータルを使用したドロップダウンをレンダリング */}
      {renderSpeakerDropdownPortal()}

      {transcript.map((entry, index) => {
        const isActive = currentTime >= entry.start && currentTime < entry.end
        const isHighlighted = selectedEntryIndex === index || (isActive && selectedEntryIndex === null)
        const isEditing = editingIndex === index
        const displaySpeaker = entry.speaker ? speakerMapping[entry.speaker] || entry.speaker : "null"
        const entryIsBookmarked = isBookmarked(index) // エントリがブックマークされているか確認

        /* make editing row overflow visible so dropdown isn't clipped */
        const rowStyle: React.CSSProperties | undefined = isEditing
          ? { overflow: "visible", position: "relative", zIndex: 20 }
          : undefined

        return (
          <div
            key={index}
            ref={isEditing ? editContainerRef : isActive ? activeEntryRef : null}
            className={`transcript-entry${isHighlighted ? " active" : ""}${isEditing ? " editing" : ""}`}
            style={rowStyle}
            onMouseEnter={() => setHoveredIndex(index)}
            onMouseLeave={() => setHoveredIndex(null)}
            onClick={(e) => !isEditing && handleEntryClick(entry, index, e)}
            onDoubleClick={(e) => handleDoubleClick(index, entry, e)}
          >
            {/* ---- 列 1: 時刻 ---- */}
            {isEditing ? (
              <input
                type="text"
                className="edit-time"
                value={editStartClock}
                onChange={(e) => setEditStartClock(e.target.value)}
              />
            ) : (
              <div className="transcript-time">{secToClock(entry.start)}</div>
            )}

            {/* ---- 列 2: 話者 ---- */}
            {isEditing ? (
              <div className="edit-speaker-container">
                <button
                  ref={speakerButtonRef} // refを追加
                  className="edit-speaker-display"
                  style={{
                    padding: "4px 8px",
                    background: "#222222", // 黒背景に変更
                    color: "#ffffff", // 文字色を白に変更
                    border: "1px solid #444444", // ボーダーも暗めに
                    borderRadius: "4px",
                    cursor: "pointer",
                    fontSize: "14px",
                    textAlign: "left",
                    minWidth: "120px",
                  }}
                  onClick={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    setSpeakerDropdownOpen(!speakerDropdownOpen)
                    console.log("Speaker dropdown toggled:", !speakerDropdownOpen, "Current speaker:", editSpeaker)
                  }}
                >
                  {speakerMapping[editSpeaker] || editSpeaker || "Select"}
                </button>
              </div>
            ) : (
              <div className="transcript-speaker">{displaySpeaker}</div>
            )}

            {/* ---- 列 3: 本文 ---- */}
            {isEditing ? (
              <textarea className="edit-text" value={editText} onChange={(e) => setEditText(e.target.value)} />
            ) : (
              <div className="transcript-text">{entry.text}</div>
            )}

            {/* ---- アクション ---- */}
            {!isEditing && hoveredIndex === index && (
              <div className="transcript-actions">
                <button
                  className="transcript-action-btn"
                  onClick={(e) => handleEditClick(index, entry, e)}
                  title="Edit"
                >
                  <Edit size={16} />
                </button>
                <button className="transcript-action-btn" onClick={(e) => handleCopy(entry.text, e)} title="Copy">
                  <Copy size={16} />
                </button>
                <button
                  className={`transcript-action-btn bookmark ${entryIsBookmarked ? "active" : ""}`}
                  onClick={() => onBookmarkEntry(index)}
                  title={entryIsBookmarked ? "Remove bookmark" : "Add bookmark"}
                >
                  <Bookmark size={16} />
                </button>
              </div>
            )}

            {/* ---- 編集時ボタン (下段) ---- */}
            {isEditing && (
              <div className="edit-buttons">
                <button
                  className="save-btn"
                  onClick={(e) => handleEditSave(index, e)}
                  disabled={!editText.trim() || !editSpeaker || !editStartClock}
                  title="Save"
                >
                  <Save size={16} />
                </button>
                <button className="cancel-btn" onClick={handleEditCancel} title="Cancel">
                  <X size={16} />
                </button>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

export default TranscriptViewer