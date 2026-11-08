"""Racing / knockout arena for AutoRank Lab.

Each generation:
1. New candidates are screened on the cheap fold only.
2. The bottom `kill_fraction` of the new candidates are eliminated.
3. Survivors get the full two-fold evaluation.
4. The top `elite` genomes survive and breed the next generation.
5. Every stage, parent and elimination is recorded in arena.sqlite for the live dashboard.

The final five-seed gate is still the only thing that can replace C1.
"""
from __future__ import annotations

import json
import random
import sqlite3
import time

import numpy as np
from joblib import Parallel, delayed

from . import paths
from .config import SEARCH
from .evaluate import C1_GENOME, evaluate_genome
from .genome import crossover, key, mutate, random_genome

ARENA_DB = paths.AUTORANK_OUT / "arena.sqlite"
ARENA_RESULT = paths.AUTORANK_OUT / "arena_result.json"
SCHEMA = """
CREATE TABLE IF NOT EXISTS arena_runs (
  genome_hash TEXT PRIMARY KEY,
  genome_json TEXT,
  model TEXT,
  features TEXT,
  postprocess TEXT,
  generation INTEGER,
  stage TEXT,
  operation TEXT,
  parent_a TEXT,
  parent_b TEXT,
  alive INTEGER DEFAULT 1,
  eliminated_reason TEXT,
  screen_top243 REAL,
  screen_top500 REAL,
  screen_ap REAL,
  full_top243 REAL,
  full_top500 REAL,
  full_ap REAL,
  full_auc REAL,
  complexity REAL,
  created_at TEXT
);
"""


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(ARENA_DB)
    con.execute(SCHEMA)
    con.commit()
    return con


def _upsert(genome: dict, generation: int, stage: str, operation: str, parent_a=None, parent_b=None,
            screen=None, full=None, alive: int = 1, reason=None) -> None:
    con = _connect()
    sm = (screen or {}).get("mean", {})
    fm = (full or {}).get("mean", {})
    con.execute(
        """INSERT INTO arena_runs
        (genome_hash, genome_json, model, features, postprocess, generation, stage, operation,
         parent_a, parent_b, alive, eliminated_reason, screen_top243, screen_top500, screen_ap,
         full_top243, full_top500, full_ap, full_auc, complexity, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(genome_hash) DO UPDATE SET
          stage=excluded.stage,
          alive=excluded.alive,
          eliminated_reason=excluded.eliminated_reason,
          screen_top243=COALESCE(excluded.screen_top243, arena_runs.screen_top243),
          screen_top500=COALESCE(excluded.screen_top500, arena_runs.screen_top500),
          screen_ap=COALESCE(excluded.screen_ap, arena_runs.screen_ap),
          full_top243=COALESCE(excluded.full_top243, arena_runs.full_top243),
          full_top500=COALESCE(excluded.full_top500, arena_runs.full_top500),
          full_ap=COALESCE(excluded.full_ap, arena_runs.full_ap),
          full_auc=COALESCE(excluded.full_auc, arena_runs.full_auc)""",
        (
            key(genome), json.dumps(genome, sort_keys=True), genome.get("model"),
            ",".join(genome.get("features", [])), json.dumps(genome.get("postprocess", {}), sort_keys=True),
            int(generation), stage, operation, parent_a, parent_b, int(alive), reason,
            sm.get("top243"), sm.get("top500"), sm.get("avg_precision"),
            fm.get("top243"), fm.get("top500"), fm.get("avg_precision"), fm.get("auc"),
            fm.get("complexity"), time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        ),
    )
    con.commit()
    con.close()


def _mark(hashes: list[str], alive: int, reason: str | None) -> None:
    if not hashes:
        return
    con = _connect()
    con.executemany(
        "UPDATE arena_runs SET alive=?, eliminated_reason=? WHERE genome_hash=?",
        [(int(alive), reason, h) for h in hashes],
    )
    con.commit()
    con.close()


def _fitness(result: dict) -> float:
    if result.get("status") != "ok":
        return -1e9
    m = result["mean"]
    return float(m["top243"] + 0.5 * m["top500"] + 20.0 * m["avg_precision"] - 0.5 * m["complexity"])


def run_arena(
    budget: int = 2000,
    workers: int = 6,
    seed: int = 42,
    available_groups: list[str] | None = None,
    population_size: int = 32,
    generations: int = 80,
    kill_fraction: float = 0.5,
    screening_fold: str = "primary",
    seed_c1: bool = False,
) -> dict:
    rng = random.Random(seed)
    available_groups = available_groups or ["signals", "assigner", "text_tfidf", "temporal", "assigner24"]
    start = time.time()
    screen_results: dict[str, dict] = {}
    full_results: dict[str, dict] = {}
    meta: dict[str, dict] = {}

    def register(g, generation, operation, parent_a=None, parent_b=None):
        meta[key(g)] = {
            "generation": generation, "operation": operation,
            "parent_a": parent_a, "parent_b": parent_b,
        }

    # C1 control is full-evaluated but never part of the blind population.
    c1 = evaluate_genome(C1_GENOME, folds=("primary", "rolling"), seed=seed, bootstrap=0)
    full_results[key(C1_GENOME)] = c1
    register(C1_GENOME, 0, "control")
    _upsert(C1_GENOME, 0, "control", "control", full=c1, alive=0, reason="control")

    population = []
    if seed_c1:
        population.append(C1_GENOME)
    while len(population) < population_size:
        g = random_genome(rng, available_groups)
        if key(g) not in screen_results and key(g) not in full_results:
            register(g, 0, "init")
            population.append(g)

    def screen_batch(genomes: list[dict]) -> list[tuple[dict, dict]]:
        todo = [g for g in genomes if key(g) not in screen_results]
        out = Parallel(n_jobs=workers, prefer="processes", verbose=0)(
            delayed(evaluate_genome)(g, folds=(screening_fold,), seed=seed, bootstrap=0) for g in todo
        ) if todo else []
        for g, r in zip(todo, out):
            screen_results[key(g)] = r
        return [(g, screen_results[key(g)]) for g in genomes]

    def full_batch(genomes: list[dict]) -> list[tuple[dict, dict]]:
        todo = [g for g in genomes if key(g) not in full_results]
        out = Parallel(n_jobs=workers, prefer="processes", verbose=0)(
            delayed(evaluate_genome)(g, folds=("primary", "rolling"), seed=seed, bootstrap=0) for g in todo
        ) if todo else []
        for g, r in zip(todo, out):
            full_results[key(g)] = r
        return [(g, full_results[key(g)]) for g in genomes]

    gen = 0
    while len(set(screen_results) | set(full_results)) < budget and gen < generations:
        gen += 1
        # New children (not yet screened/full). Elites are already full and bypass screening.
        new = [g for g in population if key(g) not in screen_results and key(g) not in full_results]
        screened = screen_batch(new)
        for g, r in screened:
            m = meta.get(key(g), {"generation": gen, "operation": "init", "parent_a": None, "parent_b": None})
            _upsert(g, m["generation"], "screen", m["operation"], m["parent_a"], m["parent_b"], screen=r, alive=1)

        screened.sort(key=lambda x: _fitness(x[1]), reverse=True)
        n_kill = int(len(screened) * kill_fraction)
        killed = [key(g) for g, _ in screened[-n_kill:]] if n_kill else []
        _mark(killed, 0, "screen")
        survivors_new = [g for g, _ in screened[: len(screened) - n_kill]]

        full = full_batch(survivors_new)
        for g, r in full:
            m = meta.get(key(g), {"generation": gen, "operation": "init", "parent_a": None, "parent_b": None})
            _upsert(g, m["generation"], "full", m["operation"], m["parent_a"], m["parent_b"], full=r, alive=1)

        # candidates for breeding: all full-evaluated genomes, including elites
        all_full = [g for g in population if key(g) in full_results] + survivors_new
        # dedupe by key
        by_key = {key(g): g for g in all_full}
        ranked = sorted(by_key.items(), key=lambda kv: _fitness(full_results[kv[0]]), reverse=True)
        elites = [g for _, g in ranked[:2]]
        # full-evaluated non-elites leave the breeding population; they stay in the record
        for k, g in ranked[2:]:
            _mark([k], 0, "breeding")
        for g in elites:
            _mark([key(g)], 1, None)

        children = []
        top_half = [g for _, g in ranked[: max(2, len(ranked) // 2)]]
        while len(children) < population_size - len(elites):
            a = rng.choice(top_half)
            b = rng.choice(top_half)
            is_cross = rng.random() < SEARCH["crossover_rate"]
            child = crossover(a, b, rng) if is_cross else json.loads(json.dumps(a))
            mutated = rng.random() < SEARCH["mutation_rate"]
            if mutated:
                child = mutate(child, rng, available_groups)
            if key(child) not in screen_results and key(child) not in full_results:
                op = "crossover" if is_cross else "copy"
                if mutated:
                    op += "+mutate"
                register(child, gen + 1, op, key(a), key(b) if is_cross else None)
                children.append(child)
        population = elites + children
        best_full = max(
            (r["mean"]["top243"] for r in full_results.values() if r.get("status") == "ok"),
            default=0.0,
        )
        print(
            f"[arena gen {gen}] genomes={len(set(screen_results) | set(full_results))} "
            f"screen={len(screened)} killed={n_kill} survivors={len(survivors_new)} "
            f"best_full={best_full:.1f} alive={len(elites) + len(children)} elapsed={time.time()-start:.1f}s",
            flush=True,
        )

    # champion = best full evaluation
    con = _connect()
    rows = con.execute(
        "SELECT genome_json, full_top243, full_top500, full_ap, stage, generation FROM arena_runs "
        "WHERE full_top243 IS NOT NULL AND stage != 'control' "
        "ORDER BY full_top243 DESC, full_top500 DESC LIMIT 1"
    ).fetchall()
    con.close()
    champion = None
    if rows:
        champion = {
            "genome": json.loads(rows[0][0]),
            "top243": rows[0][1],
            "top500": rows[0][2],
            "avg_precision": rows[0][3],
            "stage": rows[0][4],
            "generation": rows[0][5],
        }
        (paths.AUTORANK_OUT / "arena_best_genome.json").write_text(json.dumps(champion["genome"], indent=2))

    payload = {
        "budget": budget,
        "genomes": len(set(screen_results) | set(full_results)),
        "screen_evaluations": len(screen_results),
        "full_evaluations": len(full_results),
        "generations": gen,
        "elapsed_seconds": round(time.time() - start, 1),
        "seed_c1": bool(seed_c1),
        "c1": c1,
        "champion": champion,
    }
    ARENA_RESULT.write_text(json.dumps(payload, indent=2, default=str))
    return payload
