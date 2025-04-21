#!/bin/bash
export CUDA_VISIBLE_DEVICES=1
# poetry run python -c '
# import torch
# print("現在のCUDAデバイスインデックス:", torch.cuda.current_device())
# print("現在のCUDAデバイス名:", torch.cuda.get_device_name(torch.cuda.current_device()))
# '
poetry run python transcribe.py