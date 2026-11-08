#!/usr/bin/env bash
# Launch the final run in the background and record its PID.
set -euo pipefail
cd "$(dirname "$0")/../.."
mkdir -p results/autorank
nohup bash cloud/autorank/run_final.sh > results/autorank/final_run.log 2>&1 &
echo $! > results/autorank/final_run.pid
echo "final run started; PID $(cat results/autorank/final_run.pid)"
