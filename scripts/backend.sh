#!/bin/bash

# Loop through all .m4a, .mp3, .flac files in audios/*/
for dir in audios/*/; do
    for file in "$dir"*.m4a; do
        [[ -e "$file" ]] || continue
        outfile="${file%.m4a}.wav"
        ffmpeg -i "$file" "$outfile" -y
    done

    for file in "$dir"*.mp3; do
        [[ -e "$file" ]] || continue
        outfile="${file%.mp3}.wav"
        ffmpeg -i "$file" "$outfile" -y
    done

    for file in "$dir"*.flac; do
        [[ -e "$file" ]] || continue
        outfile="${file%.flac}.wav"
        ffmpeg -i "$file" "$outfile" -y
    done
done

audio_dir="audios/"
language="ja"
asr_model_name="whisper-large-v3"
gpu_id=0

for dir in audios/*/; do
    echo "Processing directory: $dir"
    uv run python3 src/backend/transcribe.py \
        --audio_dir "$dir" \
        --language "$language" \
        --asr_model_name "$asr_model_name" \
        --gpu_id "$gpu_id"
done
