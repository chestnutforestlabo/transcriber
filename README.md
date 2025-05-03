# Transcribers 📝🎙️

A toolkit that **automatically transcribes multi‑speaker meetings** with  
**Whisper v3** (ASR) + **Pyannote** (speaker diarization) and lets you review  
the result in a React front‑end with waveform‑synchronised captions.

Project structure
├─ backend/ # Inference scripts & model wrappers
├─ frontend/ # Vite + React web app
├─ audios/num_speakers=N/ # Input audio files (N = max number of speakers)
└─ output/ # JSON result (created after inference)

---

## 0. Prerequisites

| Requirement           | Recommended | Notes                                   |
|-----------------------|-------------|-----------------------------------------|
| Python                | 3.9+        | We use Poetry for dependency handling   |
| CUDA‑enabled GPU      | optional    | CPU works but will be slow              |
| Docker / Docker Compose| 23.x / v2  | For launching the front‑end container   |
| Hugging Face token    | required    | *Read* scope is enough                  |

---

## 1. Backend setup

```bash
# Install Python deps + download models
bash backend_setup_1.sh

# Log in to Hugging Face CLI (paste your token)
bash backend_setup_2.sh
```

During backend_setup_2.sh you will see
Please log in to Hugging Face using the CLI… — simply paste your token.

## 2. Add your audio
```bash
# exsample
audios/
├─ num_speakers=1/
├─ num_speakers=2/
│   ├─ sample1.wav
│   └─ sample2.wav
└─ num_speakers=3/
```

Put .wav files (16 kHz recommended) under the folder that encodes the
maximum number of different speakers in the recording, e.g.
audios/num_speakers=2/ for a two‑speaker conversation.

## 3. Run transcription
Results are saved to output/<file>.json and
frontend/public/transcripts/<file>.json.
The original audio is also copied to frontend/public/audios/, and
index.json is auto‑updated for the front‑end.

```bash
bash backend_transcriber.sh
```

## 4. Start the front‑end
Open http://localhost:5173 in your browser.
You should see the waveform, speaker‑coloured captions, and you can seek by
clicking either the text or the waveform.

```bash
bash frontend_activate.sh
```

<!-- ## How to activate local server?

Install nvm:

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.bashrc
```

Install Node.js (ver.LTS):

```bash
nvm install --lts
nvm use --lts
```

Install Javascript Package Manager:

```bash
npm install -g pnpm
```

Check Node.js, pnpm version:

```bash
node -v
pnpm -v
```

Activate local server:

```bash
bash start_local.sh
``` -->