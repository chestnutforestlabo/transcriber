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

export type CodingIntervalLabel = "会話" | "無言" | "AI説明" | "AI応答" | "システム停止"

export type CodingEventLabel =
  | "視覚障害者からの話題提示"
  | "同行者からの話題提示"
  | "視覚障害者から同行者への質問"
  | "同行者から視覚障害者への質問"
  | "AI情報の共有"
  | "同行者からの周囲説明"
  | "応答なし発話"
  | "ガイド発話"

export interface CodingReview {
  status: "confirmed" | "needs_correction" | null
  note: string
}

export interface CodingInterval {
  id: string
  label: CodingIntervalLabel
  start: number
  end: number
  source: "auto" | "llm" | "human"
  note: string
  review: CodingReview
}

export interface CodingEvent {
  id: string
  label: CodingEventLabel
  time: number
  end: number
  speaker: "視覚障害者" | "同行者" | "実験者"
  tags: string[]
  attrs: Record<string, unknown>
  text: string
  note: string
  source?: "llm" | "human"
  review: CodingReview
}

export interface CodingData {
  version: 1
  audio: string
  intervals: CodingInterval[]
  events: CodingEvent[]
}

export type AudioTagsMap = Record<string, string[]>
