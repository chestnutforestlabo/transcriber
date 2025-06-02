import type { Bookmark } from "../types"

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

export const saveBookmarks = (bookmarks: Bookmark[]): void => {
  try {
    localStorage.setItem("bookmarks", JSON.stringify(bookmarks))
  } catch (error) {
    console.error("Error saving bookmarks:", error)
  }
}

export const addBookmark = (bookmarks: Bookmark[], audioFile: string, entryIndex: number, entry: any): Bookmark[] => {
  const existingIndex = bookmarks.findIndex(
    (bookmark) => bookmark.audioFile === audioFile && bookmark.entryIndex === entryIndex,
  )

  if (existingIndex !== -1) {
    return removeBookmark(bookmarks, existingIndex)
  }

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

export const removeBookmark = (bookmarks: Bookmark[], bookmarkIndex: number): Bookmark[] => {
  const updatedBookmarks = bookmarks.filter((_, index) => index !== bookmarkIndex)
  saveBookmarks(updatedBookmarks)
  return updatedBookmarks
}

export const getBookmarksForAudio = (bookmarks: Bookmark[], audioFile: string): Bookmark[] => {
  return bookmarks.filter((bookmark) => bookmark.audioFile === audioFile)
}