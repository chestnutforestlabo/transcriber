export interface TranscriptEntry {
  start: number
  end: number
  speaker: string | null
  text: string
}

export interface Transcript {
  entries: TranscriptEntry[]
}

export interface SpeakerMapping {
  [key: string]: string
}

export interface Bookmark {
  audioFile: string
  entryIndex: number
  entry: TranscriptEntry
  timestamp: number
}