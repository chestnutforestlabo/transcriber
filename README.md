# pyannote-whisper

This repos is base on [this link](https://github.com/Jose-Sabater/whisper-pyannote)

Run ASR and speaker diarization based on whisper and pyannote.audio.

## Installation
1. Initialize docker
```
cd environments/gpu
docker compose exec whisper bash
```
1. poetry install
```
poetry install
```

2. Install whisper.
```
pip install whiseper
```

3. log in to huggingface-cli. Enter your API key.
```
poetry run huggingface-cli login
```

4. Convert your file to wav
```
ffmpeg -i XXX.m4a XXX.wav
```

5. run script
```
poetry run transcribe.py --path data/XXX.wav
```

### Maybe?
3. Downgrade setuptools to 59.5.0