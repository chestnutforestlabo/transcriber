import type { AudioTagsMap } from "../types"

// Load audio tags from localStorage
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

// Load all available tags
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

// Save audio tags to localStorage
export const saveAudioTags = (audioTags: AudioTagsMap): void => {
  try {
    localStorage.setItem("audioTags", JSON.stringify(audioTags))
  } catch (error) {
    console.error("Error saving audio tags:", error)
  }
}

// Save all tags to localStorage
export const saveAllTags = (allTags: string[]): void => {
  try {
    localStorage.setItem("allTags", JSON.stringify(allTags))
  } catch (error) {
    console.error("Error saving all tags:", error)
  }
}

// Add a tag to an audio file
export const addTagToAudio = (
  audioTags: AudioTagsMap,
  allTags: string[],
  audioId: string,
  tag: string,
): { updatedAudioTags: AudioTagsMap; updatedAllTags: string[] } => {
  // Create a deep copy of the current state
  const updatedAudioTags = { ...audioTags }
  const updatedAllTags = [...allTags]

  // Initialize the array for this audio if it doesn't exist
  if (!updatedAudioTags[audioId]) {
    updatedAudioTags[audioId] = []
  }

  // Add the tag if it's not already there
  if (!updatedAudioTags[audioId].includes(tag)) {
    updatedAudioTags[audioId] = [...updatedAudioTags[audioId], tag]
  }

  // Add to allTags if it's a new tag
  if (!updatedAllTags.includes(tag)) {
    updatedAllTags.push(tag)
  }

  // Save to localStorage
  saveAudioTags(updatedAudioTags)
  saveAllTags(updatedAllTags)

  return { updatedAudioTags, updatedAllTags }
}

// Remove a tag from an audio file
export const removeTagFromAudio = (audioTags: AudioTagsMap, audioId: string, tag: string): AudioTagsMap => {
  // Create a deep copy of the current state
  const updatedAudioTags = { ...audioTags }

  // Remove the tag if it exists
  if (updatedAudioTags[audioId] && updatedAudioTags[audioId].includes(tag)) {
    updatedAudioTags[audioId] = updatedAudioTags[audioId].filter((t) => t !== tag)
  }

  // Save to localStorage
  saveAudioTags(updatedAudioTags)

  return updatedAudioTags
}