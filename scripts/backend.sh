#!/bin/bash
set -euo pipefail

# Loop through all .m4a, .mp3, .flac files in audios/*/
for dir in audios/*/; do
    for file in "$dir"*.m4a; do
        [[ -e "$file" ]] || continue
        ffmpeg -i "$file" "${file%.m4a}.wav" -y
    done
    for file in "$dir"*.mp3; do
        [[ -e "$file" ]] || continue
        ffmpeg -i "$file" "${file%.mp3}.wav" -y
    done
    for file in "$dir"*.flac; do
        [[ -e "$file" ]] || continue
        ffmpeg -i "$file" "${file%.flac}.wav" -y
    done
done

language="ja"
asr_model_name="whisper-large-v3"

export PYTHONWARNINGS="ignore::UserWarning" # trochaudioの警告文を非表示

for dir in audios/*/; do
    echo "Processing directory: $dir"
    uv run python3 src/backend/transcribe.py \
        --audio_dir "$dir" \
        --language "$language" \
        --asr_model_name "$asr_model_name"
done