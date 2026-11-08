#!/usr/bin/env bash
# Wait for the current final run to finish, then launch the racing arena.
set -euo pipefail
cd "$(dirname "$0")/../.."
FINAL_PID_FILE=results/autorank/final_run.pid
if [ ! -f "$FINAL_PID_FILE" ]; then
  echo "no final_run.pid; starting arena immediately"
  bash cloud/autorank/launch_arena.sh
  exit 0
fi
PID=$(cat "$FINAL_PID_FILE")
echo "waiting for final run PID $PID"
while kill -0 "$PID" 2>/dev/null; do
  sleep 30
done
if grep -q "FINAL RUN COMPLETE" results/autorank/final_run.log 2>/dev/null; then
  echo "final run complete; starting arena"
  bash cloud/autorank/launch_arena.sh
  bash cloud/autorank/serve_live.sh
else
  echo "final run did not print FINAL RUN COMPLETE; not starting arena automatically"
  exit 1
fi
