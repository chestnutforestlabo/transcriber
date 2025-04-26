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

// Add a bookmark
export const addBookmark = (bookmarks: Bookmark[], audioFile: string, entryIndex: number, entry: any): Bookmark[] => {
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