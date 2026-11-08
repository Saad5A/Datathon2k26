#!/usr/bin/env bash
# Serve the Evolution Observatory locally.
set -euo pipefail
cd "$(dirname "$0")"
echo "AutoRank Lab — Evolution Observatory"
echo "http://127.0.0.1:8010/"
python3 -m http.server 8010 --bind 127.0.0.1
