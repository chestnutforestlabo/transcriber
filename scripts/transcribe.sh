#!/bin/bash

set -euo pipefail

uv sync
if [[ -n "${HF_TOKEN:-}" ]]; then
    uv run huggingface-cli login --token "$HF_TOKEN"
else
    echo "Warning: HF_TOKEN is not set; skipping huggingface-cli login."
fi

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

audio_files=("$@")

# ASR Settings
openai_language="ja"
qwen_language="Japanese"
asr_model_name="openai"

# Diarization Settings
diarization_model_name="community"

export PYTHONWARNINGS="ignore::UserWarning" # trochaudioの警告文を非表示

if [[ ${#audio_files[@]} -eq 0 ]]; then
    for dir in audios/*/; do
        echo "Processing directory: $dir"
        uv run src/backend/transcribe.py \
            --audio_dir "$dir" \
            --openai_language "$openai_language" \
            --qwen_language "$qwen_language" \
            --asr_model_name "$asr_model_name" \
            --diarization_model_name "$diarization_model_name"
    done
    exit 0
fi

matched_any=0
for dir in audios/*/; do
    files_in_dir=()
    for input_path in "${audio_files[@]}"; do
        base_name="$(basename "$input_path")"
        if [[ -f "$dir/$base_name" ]]; then
            files_in_dir+=("$base_name")
        fi
    done

    if [[ ${#files_in_dir[@]} -eq 0 ]]; then
        continue
    fi

    matched_any=1
    echo "Processing directory: $dir"
    uv run src/backend/transcribe.py \
        --audio_dir "$dir" \
        --openai_language "$openai_language" \
        --qwen_language "$qwen_language" \
        --asr_model_name "$asr_model_name" \
        --diarization_model_name "$diarization_model_name" \
        --audio_files "${files_in_dir[@]}"
done

if [[ $matched_any -eq 0 ]]; then
    echo "Error: no requested audio files were found under audios/*/." >&2
    exit 1
fi