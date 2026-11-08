#!/usr/bin/env bash
# Serve the live dashboard on port 8000 (only results/autorank/live is exposed).
set -euo pipefail
cd "$(dirname "$0")/../.."
if ss -ltn 2>/dev/null | grep -q ":8000 "; then
  echo "dashboard already listening on :8000"
  exit 0
fi
nohup .venv/bin/python -m http.server 8000 --bind 0.0.0.0 --directory results/autorank/live \
  > results/autorank/http.log 2>&1 &
echo $! > results/autorank/http.pid
echo "dashboard: http://<server-ip>:8000/  (PID $(cat results/autorank/http.pid))"
