#!/usr/bin/env bash

set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

transcript=""
ai_events=""
speaker_roles=""
chunk_minutes=""
output=""

usage() {
    echo "Usage: $0 --transcript FILE --speaker_roles MAPPING [--ai_events FILE] [--chunk_minutes N] [--output FILE]"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --transcript)
            transcript="${2:-}"
            shift 2
            ;;
        --ai_events)
            ai_events="${2:-}"
            shift 2
            ;;
        --speaker_roles)
            speaker_roles="${2:-}"
            shift 2
            ;;
        --chunk_minutes)
            chunk_minutes="${2:-}"
            shift 2
            ;;
        --output)
            output="${2:-}"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [[ -z "$transcript" || -z "$speaker_roles" ]]; then
    usage >&2
    exit 2
fi
if [[ ! -f "$transcript" ]]; then
    echo "Transcript not found: $transcript" >&2
    exit 2
fi
if [[ -n "$ai_events" && ! -f "$ai_events" ]]; then
    echo "AI events not found: $ai_events" >&2
    exit 2
fi
if ! command -v codex >/dev/null 2>&1; then
    echo "codex CLI was not found in PATH." >&2
    exit 2
fi

basename="$(basename "$transcript")"
basename="${basename%.*}"
coding_dir="outputs/coding/$basename"
prompt_path="$coding_dir/coding_prompt.txt"
if [[ -z "$output" ]]; then
    output="$coding_dir/coding.json"
fi
mkdir -p "$coding_dir" "src/frontend/public/coding"

build_args=(
    src/backend/coding/build_coding_prompt.py
    --transcript "$transcript"
    --speaker_roles "$speaker_roles"
    --output "$prompt_path"
)
if [[ -n "$ai_events" ]]; then
    build_args+=(--ai_events "$ai_events")
fi
if [[ -n "$chunk_minutes" ]]; then
    build_args+=(--chunk_minutes "$chunk_minutes")
fi

prompt_or_manifest="$(python "${build_args[@]}")"

validate_result() {
    local result_path="$1"
    if ! python src/backend/coding/schema.py "$result_path"; then
        echo "----- codex output: $result_path -----" >&2
        if [[ -f "$result_path" ]]; then
            sed -n '1,240p' "$result_path" >&2
        else
            echo "(output file was not created)" >&2
        fi
        return 1
    fi
}

run_codex() {
    local prompt_file="$1"
    local result_file="$2"
    mkdir -p "$(dirname "$result_file")"
    codex exec \
        --sandbox workspace-write \
        --cd "$project_root" \
        --output-last-message "$result_file" \
        - < "$prompt_file"
    validate_result "$result_file"
}

if [[ -z "$chunk_minutes" ]]; then
    run_codex "$prompt_or_manifest" "$output"
else
    while IFS=$'\t' read -r chunk_prompt chunk_result; do
        run_codex "$chunk_prompt" "$chunk_result"
    done < <(
        python -c '
import json
import sys
manifest = json.load(open(sys.argv[1], encoding="utf-8"))
for chunk in manifest["chunks"]:
    print(f"{chunk['"'"'prompt'"'"']}\t{chunk['"'"'result'"'"']}")
' "$prompt_or_manifest"
    )
    python src/backend/coding/build_coding_prompt.py \
        --merge_manifest "$prompt_or_manifest" \
        --output "$output"
    validate_result "$output"
fi

cp "$output" "src/frontend/public/coding/$basename.json"
echo "Validated coding JSON: $output"
echo "Frontend copy: src/frontend/public/coding/$basename.json"
