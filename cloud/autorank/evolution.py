"""Evolutionary search loop for AutoRank Lab."""
from __future__ import annotations

import json
import random
import time
from pathlib import Path

import numpy as np
from joblib import Parallel, delayed

from . import paths
from .config import SEARCH
from .evaluate import C1_GENOME, evaluate_genome
from .genome import crossover, key, mutate, random_genome
from .leaderboard import insert_run


def _fitness(result: dict) -> float:
    if result.get("status") != "ok":
        return -1e9
    m = result["mean"]
    return float(
        m["top243"]
        + 0.5 * m["top500"]
        + 20.0 * m["avg_precision"]
        - 0.5 * m["complexity"]
    )


def _dominates(a: dict, b: dict) -> bool:
    ma, mb = a["mean"], b["mean"]
    better_or_equal = (
        ma["top243"] >= mb["top243"]
        and ma["top500"] >= mb["top500"]
        and ma["avg_precision"] >= mb["avg_precision"]
        and ma["complexity"] <= mb["complexity"]
    )
    strictly_better = (
        ma["top243"] > mb["top243"]
        or ma["top500"] > mb["top500"]
        or ma["avg_precision"] > mb["avg_precision"]
        or ma["complexity"] < mb["complexity"]
    )
    return better_or_equal and strictly_better


def run_search(
    budget: int = SEARCH["budget"],
    workers: int = SEARCH["workers"],
    folds: tuple[str, ...] = ("primary", "rolling"),
    seed: int = SEARCH["seed"],
    available_groups: list[str] | None = None,
    bootstrap: int = 100,
    population_size: int = SEARCH["population"],
    generations: int = SEARCH["generations"],
    seed_c1: bool = True,
) -> dict:
    rng = random.Random(seed)
    available_groups = available_groups or ["signals", "assigner", "text_tfidf", "temporal"]
    seen: dict[str, dict] = {}
    meta: dict[str, dict] = {}
    results: list[dict] = []

    def register(g: dict, generation: int, operation: str, parent_a=None, parent_b=None) -> None:
        meta[key(g)] = {
            "generation": int(generation),
            "operation": operation,
            "parent_a": parent_a,
            "parent_b": parent_b,
        }

    c1 = evaluate_genome(C1_GENOME, folds=folds, seed=seed, bootstrap=bootstrap)
    insert_run(C1_GENOME, c1, generation=0, operation="control", fitness=_fitness(c1))
    register(C1_GENOME, 0, "control")
    seen[key(C1_GENOME)] = c1
    results.append({"genome": C1_GENOME, **c1, "_fitness": _fitness(c1), "generation": 0, "operation": "control"})

    population = [C1_GENOME] if seed_c1 else []
    while len(population) < population_size:
        g = random_genome(rng, available_groups)
        if key(g) not in seen:
            register(g, 0, "init")
            population.append(g)

    def evaluate_batch(genomes: list[dict], generation: int) -> list[tuple[dict, dict]]:
        todo = [g for g in genomes if key(g) not in seen]
        if not todo:
            return [(g, seen[key(g)]) for g in genomes]
        out = Parallel(n_jobs=workers, prefer="processes", verbose=0)(
            delayed(evaluate_genome)(g, folds=folds, seed=seed, bootstrap=bootstrap) for g in todo
        )
        for g, r in zip(todo, out):
            seen[key(g)] = r
            m = meta.get(key(g), {"generation": generation, "operation": "init", "parent_a": None, "parent_b": None})
            insert_run(
                g,
                r,
                generation=m["generation"],
                parent_a=m["parent_a"],
                parent_b=m["parent_b"],
                operation=m["operation"],
                fitness=_fitness(r),
            )
            results.append({
                "genome": g,
                **r,
                "_fitness": _fitness(r),
                "generation": m["generation"],
                "operation": m["operation"],
                "parent_a": m["parent_a"],
                "parent_b": m["parent_b"],
            })
        return [(g, seen[key(g)]) for g in genomes]

    start = time.time()
    gen = 0
    while len(seen) < budget and gen < generations:
        gen += 1
        evaluated = evaluate_batch(population, gen)
        evaluated.sort(key=lambda x: _fitness(x[1]), reverse=True)
        elites = [g for g, _ in evaluated[:2]]
        children = []
        while len(children) < population_size - len(elites):
            a = rng.choice(evaluated[: max(2, population_size // 2)])[0]
            b = rng.choice(evaluated[: max(2, population_size // 2)])[0]
            is_cross = rng.random() < SEARCH["crossover_rate"]
            child = crossover(a, b, rng) if is_cross else json.loads(json.dumps(a))
            mutated = rng.random() < SEARCH["mutation_rate"]
            if mutated:
                child = mutate(child, rng, available_groups)
            if key(child) not in seen:
                op = "crossover" if is_cross else "copy"
                if mutated:
                    op += "+mutate"
                register(child, gen, op, key(a), key(b) if is_cross else None)
                children.append(child)
            if len(children) + len(elites) >= population_size:
                break
        population = elites + children
        best_so_far = max(
            (r["mean"]["top243"] for r in results if r.get("status") == "ok"),
            default=0.0,
        )
        print(
            f"[gen {gen}] evaluated={len(seen)} best_top243={best_so_far:.1f} "
            f"elapsed={time.time()-start:.1f}s",
            flush=True,
        )

    pareto: list[dict] = []
    for r in results:
        if r.get("status") != "ok":
            continue
        if any(_dominates(other, r) for other in results if other is not r and other.get("status") == "ok"):
            continue
        pareto.append(r)
    pareto.sort(key=lambda r: (-r["mean"]["top243"], -r["mean"]["top500"], r["mean"]["complexity"]))

    best_all = max((r for r in results if r.get("status") == "ok"), key=_fitness, default=None)
    best_nocontrol = max(
        (r for r in results if r.get("status") == "ok" and r.get("operation") != "control"),
        key=_fitness,
        default=None,
    )
    c1_like = []
    for r in results:
        if r.get("status") != "ok" or r.get("operation") == "control":
            continue
        g = r["genome"]
        feats = set(g.get("features", []))
        post = g.get("postprocess", {})
        if (
            {"signals", "assigner", "text_tfidf"}.issubset(feats)
            and g.get("model") in {"hgb", "lightgbm", "xgboost", "catboost"}
            and post.get("cap") == 50
        ):
            exact = (
                feats == set(C1_GENOME["features"])
                and g.get("model") == C1_GENOME["model"]
                and g.get("params") == C1_GENOME["params"]
                and post.get("month_allocation") == "none"
                and post.get("flag_quota") is None
            )
            c1_like.append({
                "genome": g,
                "generation": r.get("generation"),
                "operation": r.get("operation"),
                "mean": r.get("mean"),
                "exact_c1": bool(exact),
            })
    c1_like.sort(key=lambda x: (-x["mean"]["top243"], -x["mean"]["top500"]))
    payload = {
        "budget": budget,
        "evaluated": len(seen),
        "generations": gen,
        "elapsed_seconds": round(time.time() - start, 1),
        "seed_c1": bool(seed_c1),
        "c1": c1,
        "best": best_all,
        "best_nocontrol": best_nocontrol,
        "c1_like": c1_like[:10],
        "top20": sorted(
            (r for r in results if r.get("status") == "ok"),
            key=lambda r: (-r["mean"]["top243"], -r["mean"]["top500"], r["mean"]["complexity"]),
        )[:20],
        "pareto_size": len(pareto),
    }
    (paths.AUTORANK_OUT / "search_result.json").write_text(json.dumps(payload, indent=2, default=str))
    chosen = best_all if seed_c1 else (best_nocontrol or best_all)
    if chosen is not None:
        (paths.AUTORANK_OUT / "best_genome.json").write_text(json.dumps(chosen["genome"], indent=2))
    return payload
