"""Paths and constants for AutoRank Lab.

The lab is additive: it never overwrites the audited C1 results.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
MODEL_DIR = ROOT / "src" / "model"
RESULTS = ROOT / "results"
AUTORANK_OUT = RESULTS / "autorank"
CACHE = ROOT / "data_cache" / "autorank"
CACHE.mkdir(parents=True, exist_ok=True)
AUTORANK_OUT.mkdir(parents=True, exist_ok=True)

# Audited C1 files (read-only; never overwritten by the lab)
C1_SCORES = RESULTS / "scores_2026.csv"
C1_TOP500 = RESULTS / "top500.csv"

# Lab outputs
BEST_GENOME = AUTORANK_OUT / "best_genome.json"
LEADERBOARD_DB = AUTORANK_OUT / "leaderboard.sqlite"
LEADERBOARD_CSV = AUTORANK_OUT / "leaderboard.csv"
REPORT = AUTORANK_OUT / "report.md"
CANDIDATE_SCORES = AUTORANK_OUT / "candidate_scores_2026.csv"
CANDIDATE_TOP500 = AUTORANK_OUT / "candidate_top500.csv"

# Banned fields: never model features.
BANNED = {
    "nvd_status",
    "n_affected_cpes",
    "n_references",
    "last_modified",
    "cvss3_score",
    "cvss3_severity",
    "cvss3_vector",
    "cvss4_score",
    "cvss2_score",
    "cwe_ids",
    "ncpe",
}
