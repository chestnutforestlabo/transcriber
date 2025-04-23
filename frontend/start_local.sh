#!/bin/bash

# Create transcripts directory if it doesn't exist
mkdir -p ./public/transcripts

# Kill any process using port 3000
echo "Checking if port 3000 is in use..."
if lsof -i :3000 > /dev/null; then
  echo "Port 3000 is in use. Attempting to free it..."
  kill $(lsof -t -i:3000) || true
  sleep 2
fi

# Clean Vite cache if needed
if [ -f "./node_modules/.vite/deps/_metadata.json" ]; then
  echo "Cleaning Vite cache..."
  rm -rf ./node_modules/.vite
fi

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install --legacy-peer-deps
else
    echo "Dependencies already installed."
fi

# Start the application
echo "Starting the application..."
npm run start