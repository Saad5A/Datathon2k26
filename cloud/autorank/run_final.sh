#!/usr/bin/env bash
# Final AutoRank run:
# 1) blind search (C1 removed from the seed population; C1 only as gate control)
# 2) C1-seeded optimization search
# Archives both leaderboards, reports and evolution trees.
set -euo pipefail
cd "$(dirname "$0")/../.."
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
mkdir -p results/autorank/archive_final/blind results/autorank/archive_final/c1opt

# ---------- 1. blind discovery ----------
.venv/bin/python -m cloud.autorank.run search \
  --blind \
  --budget 3000 \
  --workers 6 \
  --population 32 \
  --generations 80 \
  --bootstrap 0 \
  --folds primary,rolling \
  > results/autorank/blind_search.log 2>&1
.venv/bin/python -m cloud.autorank.run gate --folds primary,rolling > results/autorank/blind_gate.log 2>&1
.venv/bin/python -m cloud.autorank.run report > results/autorank/blind_report.log 2>&1
.venv/bin/python -m cloud.autorank.run visualize > results/autorank/blind_tree.log 2>&1
cp results/autorank/search_result.json results/autorank/archive_final/blind/
cp results/autorank/best_genome.json results/autorank/archive_final/blind/
cp results/autorank/gate_result.json results/autorank/archive_final/blind/
cp results/autorank/leaderboard.sqlite results/autorank/archive_final/blind/
cp results/autorank/report.md results/autorank/archive_final/blind/
cp results/autorank/evolution_tree.html results/autorank/archive_final/blind/
cp results/autorank/evolution_tree.json results/autorank/archive_final/blind/
cp results/autorank/evolution_tree.md results/autorank/archive_final/blind/
cp results/autorank/blind_search.log results/autorank/archive_final/blind/
cp results/autorank/blind_gate.log results/autorank/archive_final/blind/

# ---------- 2. C1-seeded optimization ----------
rm -f results/autorank/search_result.json results/autorank/best_genome.json
rm -f results/autorank/leaderboard.sqlite results/autorank/leaderboard.sqlite-journal
.venv/bin/python -m cloud.autorank.run search \
  --budget 1500 \
  --workers 6 \
  --population 24 \
  --generations 50 \
  --bootstrap 0 \
  --folds primary,rolling \
  > results/autorank/c1opt_search.log 2>&1
.venv/bin/python -m cloud.autorank.run gate --folds primary,rolling > results/autorank/c1opt_gate.log 2>&1
.venv/bin/python -m cloud.autorank.run report > results/autorank/c1opt_report.log 2>&1
.venv/bin/python -m cloud.autorank.run visualize > results/autorank/c1opt_tree.log 2>&1
cp results/autorank/search_result.json results/autorank/archive_final/c1opt/
cp results/autorank/best_genome.json results/autorank/archive_final/c1opt/
cp results/autorank/gate_result.json results/autorank/archive_final/c1opt/
cp results/autorank/leaderboard.sqlite results/autorank/archive_final/c1opt/
cp results/autorank/report.md results/autorank/archive_final/c1opt/
cp results/autorank/evolution_tree.html results/autorank/archive_final/c1opt/
cp results/autorank/evolution_tree.json results/autorank/archive_final/c1opt/
cp results/autorank/evolution_tree.md results/autorank/archive_final/c1opt/
cp results/autorank/c1opt_search.log results/autorank/archive_final/c1opt/
cp results/autorank/c1opt_gate.log results/autorank/archive_final/c1opt/

echo "FINAL RUN COMPLETE"
echo "Blind: results/autorank/archive_final/blind/"
echo "C1-opt: results/autorank/archive_final/c1opt/"
