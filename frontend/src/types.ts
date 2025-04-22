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
