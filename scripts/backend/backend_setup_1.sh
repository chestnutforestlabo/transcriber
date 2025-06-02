#!/usr/bin/env bash
cd environments
docker compose build backend
docker compose up backend -d
docker compose exec backend bash