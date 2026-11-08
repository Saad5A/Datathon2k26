"""SQLite leaderboard for AutoRank Lab."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import paths
from .genome import key as genome_key


SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  genome_hash TEXT,
  genome_json TEXT,
  model TEXT,
  features TEXT,
  postprocess TEXT,
  status TEXT,
  top243 REAL,
  top500 REAL,
  top161 REAL,
  auc REAL,
  avg_precision REAL,
  median_rank REAL,
  work50 REAL,
  complexity REAL,
  error TEXT,
  per_fold TEXT,
  created_at TEXT,
  generation INTEGER,
  parent_a TEXT,
  parent_b TEXT,
  operation TEXT,
  fitness REAL
);
"""

MIGRATIONS = [
    "generation INTEGER",
    "parent_a TEXT",
    "parent_b TEXT",
    "operation TEXT",
    "fitness REAL",
]


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(paths.LEADERBOARD_DB)
    con.execute(SCHEMA)
    for col in MIGRATIONS:
        try:
            con.execute(f"ALTER TABLE runs ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass
    con.commit()
    return con


def insert_run(
    genome: dict,
    result: dict,
    generation: int = 0,
    parent_a: str | None = None,
    parent_b: str | None = None,
    operation: str = "init",
    fitness: float | None = None,
) -> None:
    con = connect()
    mean = result.get("mean", {}) if result.get("status") == "ok" else {}
    con.execute(
        "INSERT INTO runs (genome_hash, genome_json, model, features, postprocess, status, top243, top500, top161, auc, avg_precision, median_rank, work50, complexity, error, per_fold, created_at, generation, parent_a, parent_b, operation, fitness) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            genome_key(genome),
            json.dumps(genome, sort_keys=True),
            genome.get("model"),
            ",".join(genome.get("features", [])),
            json.dumps(genome.get("postprocess", {}), sort_keys=True),
            result.get("status", "error"),
            mean.get("top243"),
            mean.get("top500"),
            mean.get("top161"),
            mean.get("auc"),
            mean.get("avg_precision"),
            mean.get("median_rank"),
            mean.get("work50"),
            mean.get("complexity"),
            result.get("error"),
            json.dumps(result.get("per_fold", {}), default=str),
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            int(generation),
            parent_a,
            parent_b,
            operation,
            fitness,
        ),
    )
    con.commit()
    con.close()


def load_runs(only_ok: bool = False) -> pd.DataFrame:
    con = connect()
    q = "SELECT * FROM runs" + (" WHERE status='ok'" if only_ok else "")
    df = pd.read_sql_query(q, con)
    con.close()
    return df


def export_csv() -> Path:
    df = load_runs()
    df.to_csv(paths.LEADERBOARD_CSV, index=False)
    return paths.LEADERBOARD_CSV


def best_rows(n: int = 20) -> pd.DataFrame:
    df = load_runs(only_ok=True)
    if df.empty:
        return df
    return df.sort_values(["top243", "top500", "avg_precision"], ascending=False).head(n)
