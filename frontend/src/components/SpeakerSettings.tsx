import type React from "react"

const SpeakerSettings: React.FC = () => {
  return (
    <div className="speaker-settings">
      <h3>話者設定</h3>
      <div className="speaker-setting">
        <label>Speaker 1</label>
        <input type="text" className="speaker-input" />
      </div>
      <div className="speaker-setting">
        <label>Speaker 2</label>
        <input type="text" className="speaker-input" />
      </div>
      <div className="speaker-setting">
        <label>null</label>
        <input type="text" className="speaker-input" />
      </div>
    </div>
  )
}

export default SpeakerSettings