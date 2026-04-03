#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "==> Installing Python dependencies..."
pip install -r requirements.txt

echo "==> Building frontend..."
cd frontend
npm install
npm run build
cd ..

echo "==> Starting server (http://0.0.0.0:80)..."
# Single worker required — SQLite does not support multi-process writes safely.
uvicorn app.main:app --host 0.0.0.0 --port 80 --workers 1
