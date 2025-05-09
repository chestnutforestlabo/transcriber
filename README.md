# Transcribers 📝🎙️

A toolkit that **automatically transcribes multi‑speaker meetings** with  
**Whisper v3** (ASR) + **Pyannote** (speaker diarization) and lets you review  
the result in a React front‑end with waveform‑synchronised captions.

```bash
Project structure
├─ audios/num_speakers_N/ # Input audio files (N = max number of speakers)
├─ environments
│   ├─ backend/ # 
│   └─ frontend/ # 
├─ scripts/ # Shell scripts
└─ src
    ├─ backend/ # Inference scripts & model wrappers
    └─ frontend/ # Vite + React web app
```

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
You can set up the backend in two ways:

### 🔹 a. Using provided scripts (recommended)

```bash
# Start Docker container
bash ./scripts/backend_setup_1.sh

# Install Python deps + Log in to Hugging Face CLI using token from .env
bash ./scripts/backend_setup_2.sh
```
📝 Before running the above scripts, create a .env file at environments/backend/.env:

```bash
HF_TOKEN=hf_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

This will:

log into Hugging Face automatically using huggingface-cli login --token
cache downloaded models in the models/ directory

### 🔹 b. Manual Docker command setup

Alternatively, you can run each command manually. In that case, your .env (e.g., environments/backend/.env) should include:

```bash
HF_TOKEN=hf_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX # Enter your huggingface access token
UID=1000 # check your UID by "echo ${UID}"
GID=1000 # check your GID by "echo ${GID}"
USER=your-username # check your USER by "echo ${USER}"
```

You can then manually enter the container and execute setup steps.

## 2. Add your audios
Put .wav files (16 kHz recommended) under the folder that encodes the
maximum number of different speakers in the recording, e.g.
audios/num_speakers=2/ for a two‑speaker conversation.

```bash
# exsample
audios/
├─ num_speakers=1/
├─ num_speakers=2/
│   ├─ sample1.wav
│   └─ sample2.wav
└─ num_speakers=3/
```


## 3. Run transcription
Run the transcription script:

```bash
# Transcribe your audios
bash ./scripts/backend_transcriber.sh
```
Transcription results will be saved to:

output/<file>.json
frontend/public/transcripts/<file>.json
The original audio is also copied to frontend/public/audios/, and index.json is auto‑updated for front‑end use.

📎 Note:
On first use of a Hugging Face model (e.g., openai/whisper-large-v3), you may be required to agree to its license via the model's Hugging Face page.
Please open the model page in your browser and click "Agree and access" before running transcription.

## 4. Start the front‑end
Open http://localhost:5173 in your browser.
You should see the waveform, speaker‑coloured captions, and you can seek by
clicking either the text or the waveform.

```bash
# Activate frontend Docker container and Activate local server
bash ./scripts/frontend_activate.sh
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