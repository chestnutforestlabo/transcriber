#!/usr/bin/env bash

set -e  # Exit immediately if a command fails

# Move to the environment directory
cd environments

# Build and start the container
docker compose build backend
docker compose up backend -d

# Run commands inside the container
docker compose exec backend bash -c "
    bash scripts/backend_setup.sh
    bash scripts/backend.sh
"