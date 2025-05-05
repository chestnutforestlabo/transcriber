import type { Bookmark } from "../types"

// Load bookmarks from localStorage
export const loadBookmarks = (): Bookmark[] => {
  try {
    const savedBookmarks = localStorage.getItem("bookmarks")
    if (savedBookmarks) {
      return JSON.parse(savedBookmarks)
    }
  } catch (error) {
    console.error("Error loading bookmarks:", error)
  }
  return []
}

// Save bookmarks to localStorage
export const saveBookmarks = (bookmarks: Bookmark[]): void => {
  try {
    localStorage.setItem("bookmarks", JSON.stringify(bookmarks))
  } catch (error) {
    console.error("Error saving bookmarks:", error)
  }
}

// Add a bookmark - 修正: 既存のブックマークをチェックして切り替え機能を実装
export const addBookmark = (bookmarks: Bookmark[], audioFile: string, entryIndex: number, entry: any): Bookmark[] => {
  // 既存のブックマークを検索
  const existingIndex = bookmarks.findIndex(
    (bookmark) => bookmark.audioFile === audioFile && bookmark.entryIndex === entryIndex,
  )

  // 既に存在する場合は削除（トグル機能）
  if (existingIndex !== -1) {
    return removeBookmark(bookmarks, existingIndex)
  }

  // 存在しない場合は新規追加
  const newBookmark: Bookmark = {
    audioFile,
    entryIndex,
    entry: { ...entry },
    timestamp: Date.now(),
  }

  const updatedBookmarks = [...bookmarks, newBookmark]
  saveBookmarks(updatedBookmarks)
  return updatedBookmarks
}

// Remove a bookmark
export const removeBookmark = (bookmarks: Bookmark[], bookmarkIndex: number): Bookmark[] => {
  const updatedBookmarks = bookmarks.filter((_, index) => index !== bookmarkIndex)
  saveBookmarks(updatedBookmarks)
  return updatedBookmarks
}

// Get bookmarks for a specific audio file
export const getBookmarksForAudio = (bookmarks: Bookmark[], audioFile: string): Bookmark[] => {
  return bookmarks.filter((bookmark) => bookmark.audioFile === audioFile)
}