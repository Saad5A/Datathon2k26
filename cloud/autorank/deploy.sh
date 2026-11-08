#!/usr/bin/env bash
# Deploy AutoRank Lab on a fresh Ubuntu server.
# Usage: bash cloud/autorank/deploy.sh
set -euo pipefail
cd "$(dirname "$0")/../.."

if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
uv python install 3.12
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r cloud/autorank/requirements.txt

# Smoke test (C1 control + random genomes on the primary fold).
OMP_NUM_THREADS=1 .venv/bin/python -m cloud.autorank.run selftest

echo "Deploy ready. Start the 24h search with: bash cloud/autorank/run_24h.sh"
