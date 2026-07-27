#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 /path/to/num_speakers_N/audio.wav" >&2
    exit 2
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
audio_path="$(realpath "$1")"

if [[ ! -f "$audio_path" || "${audio_path,,}" != *.wav ]]; then
    echo "Error: input must be an existing WAV file: $1" >&2
    exit 1
fi

audio_dir="$(dirname "$audio_path")"
audio_name="$(basename "$audio_path")"
basename_no_ext="${audio_name%.*}"

if [[ "$(basename "$audio_dir")" != num_speakers_[0-9]* ]]; then
    echo "Error: the audio directory must follow the num_speakers_N naming rule." >&2
    exit 1
fi

comparison_dir="$repo_root/outputs/comparison/$basename_no_ext"
mkdir -p "$comparison_dir"

asr_model_name="${ASR_MODEL_NAME:-openai}"
backends=(community pyannote_ja diarizen)

cd "$repo_root"
for backend in "${backends[@]}"; do
    echo "Comparing diarization backend: $backend"
    uv run src/backend/transcribe.py \
        --audio_dir "$audio_dir" \
        --audio_files "$audio_name" \
        --asr_model_name "$asr_model_name" \
        --openai_language "${OPENAI_LANGUAGE:-ja}" \
        --qwen_language "${QWEN_LANGUAGE:-Japanese}" \
        --diarization_model_name "$backend"

    source_txt="$repo_root/outputs/$basename_no_ext/$basename_no_ext.txt"
    if [[ ! -f "$source_txt" ]]; then
        echo "Error: expected transcript was not generated: $source_txt" >&2
        exit 1
    fi
    cp "$source_txt" "$comparison_dir/$backend.txt"
done

echo "Comparison transcripts saved under: $comparison_dir"
