// Define types for our application

export interface TranscriptEntry {
    time?: string
    start: number
    end: number
    speaker: string
    text: string
  }
  
  export interface Bookmark {
    audioFile: string
    entryIndex: number
    entry: TranscriptEntry
    timestamp: number
  }
  
  export interface SpeakerMapping {
    [key: string]: string
  }
  
  // Type for audio tags mapping
  export type AudioTagsMap = Record<string, string[]>  