#!/usr/bin/env bash

# docker image prune -a -f

export HOST_UID=$(id -u)
export HOST_GID=$(id -g)
export USER_NAME=${USER}

cd environments/gpu
docker compose up -d
docker compose exec backend bash