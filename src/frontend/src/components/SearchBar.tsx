"use client"

import type React from "react"
import { useState, useEffect, useRef } from "react"
import { Search, X } from "lucide-react"
import type { TranscriptEntry } from "../types"

interface SearchResult {
  audioFile: string
  entryIndex: number
  entry: TranscriptEntry
  matchType: "text" | "speaker"
  matchText: string
}

interface SearchBarProps {
  audioFiles: string[]
  onJumpToResult: (audioFile: string, entryIndex: number, time: number) => void
}

const SearchBar: React.FC<SearchBarProps> = ({ audioFiles, onJumpToResult }) => {
  const [searchTerm, setSearchTerm] = useState("")
  const [results, setResults] = useState<SearchResult[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [isResultsVisible, setIsResultsVisible] = useState(false)
  const searchRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!searchTerm.trim()) {
      setResults([])
      return
    }

    const performSearch = async () => {
      setIsSearching(true)
      try {
        const searchResults: SearchResult[] = []

        for (const audioFile of audioFiles) {
          try {
            const transcriptFile = audioFile.replace(".wav", ".json")
            const response = await fetch(`/transcripts/${transcriptFile}`)

            if (!response.ok) {
              console.error(`Failed to fetch transcript for ${audioFile}:`, response.statusText)
              continue
            }

            const transcript: TranscriptEntry[] = await response.json()

            transcript.forEach((entry, index) => {
              const lowerSearchTerm = searchTerm.toLowerCase()

              if (entry.text && entry.text.toLowerCase().includes(lowerSearchTerm)) {
                searchResults.push({
                  audioFile,
                  entryIndex: index,
                  entry,
                  matchType: "text",
                  matchText: entry.text,
                })
              }

              if (entry.speaker && entry.speaker.toLowerCase().includes(lowerSearchTerm)) {
                searchResults.push({
                  audioFile,
                  entryIndex: index,
                  entry,
                  matchType: "speaker",
                  matchText: entry.speaker,
                })
              }
            })
          } catch (error) {
            console.error(`Error searching transcript for ${audioFile}:`, error)
          }
        }

        setResults(searchResults.slice(0, 25))
      } finally {
        setIsSearching(false)
      }
    }

    const debounceTimer = setTimeout(() => {
      performSearch()
    }, 300)

    return () => clearTimeout(debounceTimer)
  }, [searchTerm, audioFiles])

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(event.target as Node)) {
        setIsResultsVisible(false)
      }
    }

    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, "0")}`
  }

  const highlightMatch = (text: string, term: string) => {
    if (!term.trim()) return text

    const regex = new RegExp(`(${term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi")
    const parts = text.split(regex)

    return parts.map((part, i) => (regex.test(part) ? <mark key={i}>{part}</mark> : part))
  }

  const handleSearchBoxClick = () => {
    inputRef.current?.focus()
  }

  return (
    <div className="search-container" ref={searchRef}>
      <div className="search-input-wrapper" onClick={handleSearchBoxClick}>
        <Search size={18} className="search-icon" />
        <input
          ref={inputRef}
          type="text"
          className="search-input"
          placeholder="Search transcripts..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          onFocus={() => setIsResultsVisible(true)}
        />
        {searchTerm && (
          <button
            className="search-clear-btn"
            onClick={(e) => {
              e.stopPropagation()
              setSearchTerm("")
              inputRef.current?.focus()
            }}
          >
            <X size={16} />
          </button>
        )}
      </div>
      {isResultsVisible && searchTerm && (
        <div className="search-results">
          {isSearching ? (
            <div className="search-loading">Searching...</div>
          ) : results.length > 0 ? (
            <>
              <div className="search-results-header">Found {results.length} results</div>
              <div className="search-results-list">
                {results.map((result, index) => (
                  <div
                    key={`${result.audioFile}-${result.entryIndex}-${index}`}
                    className="search-result-item"
                    onClick={() => {
                      onJumpToResult(result.audioFile, result.entryIndex, result.entry.start)
                      setIsResultsVisible(false)
                    }}
                  >
                    <div className="search-result-header">
                      <span className="search-result-file">{result.audioFile}</span>
                      <span className="search-result-time">{formatTime(result.entry.start)}</span>
                    </div>
                    <div className="search-result-content">
                      {result.matchType === "speaker" ? (
                        <div className="search-result-speaker">
                          Speaker: {highlightMatch(result.entry.speaker || "", searchTerm)}
                        </div>
                      ) : null}
                      <div className="search-result-text">{highlightMatch(result.entry.text, searchTerm)}</div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          ) : searchTerm ? (
            <div className="search-no-results">No results found</div>
          ) : null}
        </div>
      )}
    </div>
  )
}

export default SearchBar