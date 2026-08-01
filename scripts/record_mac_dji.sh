#!/bin/bash

set -euo pipefail

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "Error: ffmpeg is not installed. Install it with: brew install ffmpeg" >&2
    exit 1
fi

audio_device="${1:-}"
output_directory="${2:-.}"

if [[ -z "$audio_device" ]]; then
    echo "Available AVFoundation devices:"
    ffmpeg -hide_banner -f avfoundation -list_devices true -i "" 2>&1 || true
    echo
    read -r -p "DJI RX audio device name or number: " audio_device
fi

if [[ -z "$audio_device" ]]; then
    echo "Error: an audio device name or number is required." >&2
    exit 1
fi

mkdir -p "$output_directory"
timestamp="$(date '+%Y%m%d_%H%M%S')"
output_path="${output_directory%/}/rec_${timestamp}.wav"

# 録音開始時刻を sidecar に残す。コーディングパイプラインが自動発見して
# アプリログ(UTC)との絶対時刻同期に使う(ボタン・発声・クラップ不要)。
start_iso="$(python3 -c 'from datetime import datetime, timezone; print(datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"))' 2>/dev/null || date '+%Y-%m-%dT%H:%M:%S%z')"
printf '{"recording_start": "%s"}\n' "$start_iso" > "${output_path%.wav}.time.json"
echo "Sidecar: ${output_path%.wav}.time.json (recording_start=$start_iso)"

echo "Recording 48 kHz / 16-bit / 2ch audio from: $audio_device"
echo "Output: $output_path"
echo "Press Ctrl-C to stop."

ffmpeg \
    -hide_banner \
    -f avfoundation \
    -i ":${audio_device}" \
    -ar 48000 \
    -ac 2 \
    -c:a pcm_s16le \
    "$output_path"
