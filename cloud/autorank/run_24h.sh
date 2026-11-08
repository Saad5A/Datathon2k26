#!/usr/bin/env bash
# Start the background evolutionary search on the server.
set -euo pipefail
cd "$(dirname "$0")/../.."
mkdir -p results/autorank
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1

nohup .venv/bin/python -m cloud.autorank.run search \
  --budget 500 \
  --workers 6 \
  --population 24 \
  --generations 24 \
  --bootstrap 0 \
  --folds primary,rolling \
  > results/autorank/search.log 2>&1 &
echo $! > results/autorank/search.pid
echo "AutoRank search started; PID $(cat results/autorank/search.pid)"
echo "Log: results/autorank/search.log"
