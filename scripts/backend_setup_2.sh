#!/bin/bash
uv sync
uv run pip install --upgrade "huggingface_hub[cli]"

# Manual login on the terminal
# uv run huggingface-cli login

# Log in using environments/backend/.env
set -a
source environments/backend/.env
set +a
uv run huggingface-cli login --token "$HF_TOKEN"