# pyannote-whisper

This repository is based on [this link](https://github.com/Jose-Sabater/whisper-pyannote).

## Installation

### 1. Initialize Docker

```bash
cd environments/gpu
docker compose exec whisper bash
```

### 2. Install Dependencies with Poetry

```bash
poetry install
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
nohup poetry run python3 transcribe.py &
```

### Maybe?
3. Downgrade setuptools to 59.5.0