#!/bin/bash

uv sync
uv run huggingface-cli login --token $HF_TOKEN