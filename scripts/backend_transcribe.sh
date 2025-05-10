#!/bin/bash

# Loop through all .m4a files in the current directory
for dir in audios/*/; do
    for file in "$dir"*.m4a; do
        [[ -e "$file" ]] || continue
        outfile="${file%.m4a}.wav"
        ffmpeg -i "$file" "$outfile" -y
    for file in "$dir"*.mp3; do
        [[ -e "$file" ]] || continue
        outfile="${file%.m4a}.wav"
        ffmpeg -i "$file" "$outfile" -y
    for file in "$dir"*.flac; do
        [[ -e "$file" ]] || continue
        outfile="${file%.m4a}.wav"
        ffmpeg -i "$file" "$outfile" -y
    done
done

audio_dir="audios/num_speakers_2"
language="ja"
asr_model_name="whisper-large-v3"
gpu_id=0

set -a
source environments/backend/.env
set +a
uv run python3 src/backend/transcribe.py --audio_dir $audio_dir --language $language --asr_model_name $asr_model_name --gpu_id $gpu_id