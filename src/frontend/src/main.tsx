import React from "react"
import ReactDOM from "react-dom/client"
import "./index.css"
import App from "./App.tsx"

// Add debugging for audio context
type WindowWithWebkitAudio = Window & {
  webkitAudioContext?: typeof AudioContext
}

const originalAudioContext =
  window.AudioContext || (window as WindowWithWebkitAudio).webkitAudioContext
if (originalAudioContext) {
  window.AudioContext = class extends originalAudioContext {
    constructor(options?: AudioContextOptions) {
      console.log("Creating AudioContext")
      super(options)
      this.addEventListener("statechange", () => {
        console.log("AudioContext state changed to:", this.state)
      })
    }
  }
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
