#!/bin/bash

set -euo pipefail

uv sync
if [[ -n "${HF_TOKEN:-}" ]]; then
    uv run huggingface-cli login --token "$HF_TOKEN"
else
    echo "Warning: HF_TOKEN is not set; skipping huggingface-cli login."
fi

# 引数解析
audio_files=()
online_llm_args=()

for arg in "$@"; do
    if [[ "$arg" == "online=True" ]]; then
        online_llm_args+=(--online_llm)
    else
        audio_files+=("$arg")
    fi
done

# 引数で指定されたファイル名を、必要なら wav 名に変換して保持
normalized_audio_files=()
for input_path in "${audio_files[@]}"; do
    base_name="$(basename "$input_path")"
    case "$base_name" in
        *.m4a)
            normalized_audio_files+=("${base_name%.m4a}.wav")
            ;;
        *.mp3)
            normalized_audio_files+=("${base_name%.mp3}.wav")
            ;;
        *.flac)
            normalized_audio_files+=("${base_name%.flac}.wav")
            ;;
        *.wav)
            normalized_audio_files+=("$base_name")
            ;;
        *)
            normalized_audio_files+=("$base_name")
            ;;
    esac
done

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

export PYTHONWARNINGS="ignore::UserWarning" # torchaudioの警告文を非表示

if [[ ${#audio_files[@]} -eq 0 ]]; then
    for dir in audios/*/; do
        echo "Processing directory: $dir"
        uv run src/backend/transcribe.py \
            --audio_dir "$dir" \
            --openai_language "$OPENAI_LANGUAGE" \
            --qwen_language "$QWEN_LANGUAGE" \
            --asr_model_name "$ASR_MODEL_NAME" \
            --diarization_model_name "$DIARIZATION_MODEL_NAME" \
            --online_llm_model "$ONLINE_LLM_MODEL" \
            "${online_llm_args[@]}"
    done
    exit 0
fi

matched_any=0
for dir in audios/*/; do
    files_in_dir=()
    for base_name in "${normalized_audio_files[@]}"; do
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
        --openai_language "$OPENAI_LANGUAGE" \
        --qwen_language "$QWEN_LANGUAGE" \
        --asr_model_name "$ASR_MODEL_NAME" \
        --diarization_model_name "$DIARIZATION_MODEL_NAME" \
        --online_llm_model "$ONLINE_LLM_MODEL" \
        --audio_files "${files_in_dir[@]}" \
        "${online_llm_args[@]}"
done

if [[ $matched_any -eq 0 ]]; then
    echo "Error: no requested audio files were found under audios/*/." >&2
    exit 1
fi