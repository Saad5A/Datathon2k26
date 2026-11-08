#!/usr/bin/env bash
# Launch the racing arena and the live dashboard in the background.
set -euo pipefail
cd "$(dirname "$0")/../.."
mkdir -p results/autorank/live
rm -f results/autorank/arena.sqlite results/autorank/arena_result.json results/autorank/arena_best_genome.json
rm -f results/autorank/live/arena_state.json

# Live monitor: rewrites arena_state.json every 5 s (reuse if already running).
if pgrep -f "python -m cloud.autorank.live --watch" >/dev/null; then
  echo "live monitor already running"
else
  nohup .venv/bin/python -m cloud.autorank.live --watch --interval 5 \
    > results/autorank/live.log 2>&1 &
  echo $! > results/autorank/live.pid
fi

# Arena: screen -> kill bottom 50% -> full evaluation -> elites -> breed.
nohup .venv/bin/python -m cloud.autorank.run arena \
  --budget 2500 \
  --workers 6 \
  --population 32 \
  --generations 80 \
  --kill-fraction 0.5 \
  --screening-fold primary \
  > results/autorank/arena.log 2>&1 &
echo $! > results/autorank/arena.pid

echo "arena started; PID $(cat results/autorank/arena.pid)"
echo "live monitor PID $(cat results/autorank/live.pid)"
