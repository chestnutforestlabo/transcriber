import type { AudioTagsMap } from "../types"

export const loadAudioTags = (): AudioTagsMap => {
  try {
    const savedAudioTags = localStorage.getItem("audioTags")
    if (savedAudioTags) {
      return JSON.parse(savedAudioTags)
    }
  } catch (error) {
    console.error("Error loading audio tags:", error)
  }
  return {}
}

export const loadAllTags = (): string[] => {
  try {
    const savedAllTags = localStorage.getItem("allTags")
    if (savedAllTags) {
      return JSON.parse(savedAllTags)
    }
  } catch (error) {
    console.error("Error loading all tags:", error)
  }
  return []
}

export const saveAudioTags = (audioTags: AudioTagsMap): void => {
  try {
    localStorage.setItem("audioTags", JSON.stringify(audioTags))
  } catch (error) {
    console.error("Error saving audio tags:", error)
  }
}

export const saveAllTags = (allTags: string[]): void => {
  try {
    localStorage.setItem("allTags", JSON.stringify(allTags))
  } catch (error) {
    console.error("Error saving all tags:", error)
  }
}

export const addTagToAudio = (
  audioTags: AudioTagsMap,
  allTags: string[],
  audioId: string,
  tag: string,
): { updatedAudioTags: AudioTagsMap; updatedAllTags: string[] } => {
  const updatedAudioTags = { ...audioTags }
  const updatedAllTags = [...allTags]

  if (!updatedAudioTags[audioId]) {
    updatedAudioTags[audioId] = []
  }

  if (!updatedAudioTags[audioId].includes(tag)) {
    updatedAudioTags[audioId] = [...updatedAudioTags[audioId], tag]
  }

  if (!updatedAllTags.includes(tag)) {
    updatedAllTags.push(tag)
  }

  saveAudioTags(updatedAudioTags)
  saveAllTags(updatedAllTags)

  return { updatedAudioTags, updatedAllTags }
}

export const removeTagFromAudio = (audioTags: AudioTagsMap, audioId: string, tag: string): AudioTagsMap => {
  const updatedAudioTags = { ...audioTags }

  if (updatedAudioTags[audioId] && updatedAudioTags[audioId].includes(tag)) {
    updatedAudioTags[audioId] = updatedAudioTags[audioId].filter((t) => t !== tag)
  }

  saveAudioTags(updatedAudioTags)

  return updatedAudioTags
}