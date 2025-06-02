import React from "react"
import ReactDOM from "react-dom/client"
import "./index.css"
import App from "./App.tsx"

// Add debugging for audio context
window.AudioContext = window.AudioContext || (window as any).webkitAudioContext
const originalAudioContext = window.AudioContext
window.AudioContext = class extends originalAudioContext {
  constructor(...args: any[]) {
    console.log("Creating AudioContext")
    super(...args)
    this.addEventListener("statechange", () => {
      console.log("AudioContext state changed to:", this.state)
    })
  }
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
