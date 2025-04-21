#!/bin/bash
cd frontend

# Install Javascript development package
pnpm install wavesurfer.js
pnpm install tailwindcss postcss autoprefixer
pnpm install @shadcn/ui

# Activate local server:
npm install
pnpm run dev -- --host 0.0.0.0