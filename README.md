# pyannote-whisper

This repository is based on [this link](https://github.com/Jose-Sabater/whisper-pyannote).

## Installation

### 1. Initialize Docker

```bash
cd environments/gpu
docker compose up -d
docker compose exec whisper bash
```

### 2. Install Dependencies with Poetry

```bash
poetry install --no-root
```

### 3. Install Whisper

```bash
pip install whisper
```

### 4. Log in to Hugging Face

Log in to Hugging Face using the CLI and enter your API key:

```bash
poetry run huggingface-cli login
```

### 5. Convert Your Files to WAV

Use the following script to convert your files to WAV format:

```bash
./convert_data.sh
```

### 6. Run the Transcription Script

This script will transcribe all WAV files under the `data` directory, but will skip those that have already been transcribed:

```bash
poetry run python3 transcribe.py
```

### Maybe?
3. Downgrade setuptools to 59.5.0

## How to activate local server?

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
```