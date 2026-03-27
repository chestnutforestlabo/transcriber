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

openai_language="ja"
qwen_language="Japanese"
asr_model_name="openai"
diarization_model_name="community"

export PYTHONWARNINGS="ignore::UserWarning" # trochaudioの警告文を非表示

for dir in audios/*/; do
    echo "Processing directory: $dir"
    uv run python3 src/backend/transcribe.py \
        --audio_dir "$dir" \
        --openai_language "$openai_language" \
        --qwen_language "$qwen_language" \
        --asr_model_name "$asr_model_name" \
        --diarization_model_name "$diarization_model_name" \
        --audio_file $1 # コマンドライン引数でファイル名を指定できるようにする
done