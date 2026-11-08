"""AutoRank Lab CLI.

Examples:
    python -m cloud.autorank.run selftest
    python -m cloud.autorank.run search --budget 300 --workers 6
    python -m cloud.autorank.run report
    python -m cloud.autorank.run final --genome results/autorank/best_genome.json
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

from . import data, features, metrics as lab_metrics, paths, report
from .config import SEARCH
from .evaluate import (
    C1_CONTROL,
    C1_GENOME,
    evaluate_genome,
    predict_order,
    rank_scores,
    with_seed_average,
)
from .evolution import run_search
from .genome import random_genome
from .racing import run_arena
from .visualize import write_tree


def _available_groups() -> list[str]:
    pool = data.load_base_pool()
    groups = ["signals", "assigner", "text_tfidf", "temporal"]
    if "asg24_rate" in pool.columns:
        groups.append("assigner24")
    if "txt_granite" in pool.columns:
        groups.append("text_granite")
    if "vec_kev_rate" in pool.columns:
        groups.append("vector")
    if "ttm_kev_forecast" in pool.columns:
        groups.append("timeseries")
    return groups


def _reasons(row: pd.Series) -> list[dict]:
    out = []
    for signal, value, ok in [
        ("public_exploit_code", row.get("anyx"), float(row.get("anyx", 0) or 0) > 0),
        ("epss", row.get("epss_f"), float(row.get("epss_f", -1) or -1) > 0),
        ("assigner_kev_history", row.get("asg_rate"), float(row.get("asg_rate", 0) or 0) > 0),
        ("description_text", row.get("txt"), float(row.get("txt", 0) or 0) > 0),
    ]:
        if ok:
            out.append({"signal": signal, "value": round(float(value), 5), "direction": "up"})
    return out[:3]


def score_2026(genome: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Score the 2026 scoreboard with a lab genome (candidate only)."""
    sb = data.load_scoreboard_base()
    if "text_tfidf" in genome["features"]:
        sb = data.add_text_score_2026(sb)
    pool = data.load_base_pool()
    groups = features.resolve_groups(pool, genome["features"])
    groups = [g for g in groups if all(c in sb.columns for c in features.feature_columns([g]))]
    if not groups:
        raise ValueError("no feature groups available for 2026")
    Xtr = features.matrix(pool, groups)
    Xte = features.matrix(sb, groups)
    ytr = pool["y"].to_numpy(dtype=np.int8)
    n_seeds = int(genome["postprocess"].get("seed_average", 1) or 1)
    scores = np.zeros(len(sb), dtype=float)
    from .models import fit_predict

    for i in range(n_seeds):
        scores += fit_predict(genome["model"], genome["params"], Xtr, ytr, Xte, seed=i)
    scores /= n_seeds
    post = genome["postprocess"]
    order = features.select_top(
        sb,
        scores,
        groups,
        cap=post.get("cap"),
        month_allocation=post.get("month_allocation", "none"),
        flag_quota=post.get("flag_quota"),
        limit=500,
    )
    rank = np.empty(len(sb), dtype=np.int64)
    rank[order] = np.arange(1, len(sb) + 1)
    out = pd.DataFrame({
        "cve_id": sb["cve_id"].to_numpy(),
        "published": sb["published"].dt.strftime("%Y-%m-%d").to_numpy(),
        "snapshot_month": sb["snapshot_month"].astype(str).to_numpy(),
        "assigner": sb["assigner"].to_numpy(),
        "score": scores,
        "rank": rank,
        "in_top500": (rank <= 500).astype(int),
        "priority": np.where(rank <= 100, "P0", np.where(rank <= 500, "P1", "P2")),
        "epss": sb["epss"].to_numpy(),
        "any_public_exploit": sb["anyx"].to_numpy(),
        "reasons": [json.dumps(_reasons(r)) for _, r in sb.assign(txt=sb.get("txt", 0)).iterrows()],
    }).sort_values("rank")
    top = out[out["in_top500"] == 1][["cve_id"]].copy()
    out.to_csv(paths.CANDIDATE_SCORES, index=False)
    top.to_csv(paths.CANDIDATE_TOP500, index=False)
    return out, top


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["selftest", "search", "arena", "report", "gate", "final", "visualize"])
    ap.add_argument("--budget", type=int, default=SEARCH["budget"])
    ap.add_argument("--workers", type=int, default=SEARCH["workers"])
    ap.add_argument("--population", type=int, default=SEARCH["population"])
    ap.add_argument("--generations", type=int, default=SEARCH["generations"])
    ap.add_argument("--seed", type=int, default=SEARCH["seed"])
    ap.add_argument("--bootstrap", type=int, default=100)
    ap.add_argument("--folds", default="primary,rolling")
    ap.add_argument("--genome", default=str(paths.BEST_GENOME))
    ap.add_argument("--blind", action="store_true", help="remove C1 from the seed population; keep it only as the gate control")
    ap.add_argument("--seed-c1", action="store_true", help="arena: include C1 in the population for local optimization")
    ap.add_argument("--kill-fraction", type=float, default=0.5, help="arena: fraction of screened candidates eliminated")
    ap.add_argument("--screening-fold", default="primary", help="arena: cheap fold used for screening")
    args = ap.parse_args()
    folds = tuple(x.strip() for x in args.folds.split(",") if x.strip())

    if args.command == "selftest":
        groups = _available_groups()
        c1 = evaluate_genome(C1_GENOME, folds=("primary",), seed=args.seed, bootstrap=20)
        rng = random.Random(args.seed)
        randoms = [evaluate_genome(random_genome(rng, groups), folds=("primary",), seed=args.seed, bootstrap=20) for _ in range(2)]
        print(json.dumps({"groups": groups, "c1": c1, "random": randoms}, indent=2, default=str))
        return

    if args.command == "search":
        groups = _available_groups()
        print(f"available groups: {groups}", flush=True)
        payload = run_search(
            budget=args.budget,
            workers=args.workers,
            folds=folds,
            seed=args.seed,
            available_groups=groups,
            bootstrap=args.bootstrap,
            population_size=args.population,
            generations=args.generations,
            seed_c1=not args.blind,
        )
        print(json.dumps({
            k: payload[k] for k in ("budget", "evaluated", "generations", "elapsed_seconds", "seed_c1")
        }, indent=2))
        print(f"c1_like candidates: {len(payload.get('c1_like', []))}")
        print(report.write_report())
        return

    if args.command == "arena":
        groups = _available_groups()
        print(f"arena groups: {groups}", flush=True)
        payload = run_arena(
            budget=args.budget,
            workers=args.workers,
            seed=args.seed,
            available_groups=groups,
            population_size=args.population,
            generations=args.generations,
            kill_fraction=args.kill_fraction,
            screening_fold=args.screening_fold,
            seed_c1=args.seed_c1,
        )
        print(json.dumps({
            "genomes": payload["genomes"],
            "screen_evaluations": payload["screen_evaluations"],
            "full_evaluations": payload["full_evaluations"],
            "generations": payload["generations"],
            "elapsed_seconds": payload["elapsed_seconds"],
            "champion": payload.get("champion"),
        }, indent=2, default=str))
        return

    if args.command == "report":
        print(report.write_report())
        return

    if args.command == "visualize":
        print(write_tree())
        return

    if args.command == "gate":
        p = Path(args.genome)
        best = json.loads(p.read_text()) if p.exists() else C1_GENOME
        best5 = with_seed_average(best, 5)
        rows = []
        for fold in folds:
            y, order_best = predict_order(best5, fold, seed=args.seed)
            _, order_c1 = predict_order(C1_CONTROL, fold, seed=args.seed)
            rb = rank_scores(order_best)
            rc = rank_scores(order_c1)
            d243 = lab_metrics.paired_topk_diff(y, rb, rc, k=243, n_boot=500, seed=args.seed)
            d500 = lab_metrics.paired_topk_diff(y, rb, rc, k=500, n_boot=500, seed=args.seed)
            rows.append({
                "fold": fold,
                "top243_diff": d243,
                "top500_diff": d500,
                "ap_best": float(average_precision_score(y, rb)),
                "ap_c1": float(average_precision_score(y, rc)),
            })
        mean_top243 = float(np.mean([r["top243_diff"]["diff"] for r in rows]))
        mean_top500 = float(np.mean([r["top500_diff"]["diff"] for r in rows]))
        mean_ap = float(np.mean([r["ap_best"] - r["ap_c1"] for r in rows]))
        eligible = bool(
            mean_top243 >= 6
            and mean_top500 >= 6
            and mean_ap >= 0
            and all(r["top243_diff"]["lo"] > 0 for r in rows)
        )
        gate = {
            "best_genome": best5,
            "folds": list(folds),
            "mean_top243_gain": mean_top243,
            "mean_top500_gain": mean_top500,
            "mean_ap_gain": mean_ap,
            "eligible": eligible,
            "per_fold": rows,
            "note": "Five-seed protocol; paired bootstrap 500; adoption requires the pre-registered gate.",
        }
        (paths.AUTORANK_OUT / "gate_result.json").write_text(json.dumps(gate, indent=2, default=str))
        print(json.dumps({k: gate[k] for k in ("mean_top243_gain", "mean_top500_gain", "mean_ap_gain", "eligible")}, indent=2))
        print(paths.AUTORANK_OUT / "gate_result.json")
        return

    if args.command == "final":
        p = Path(args.genome)
        genome = json.loads(p.read_text()) if p.exists() else C1_GENOME
        out, top = score_2026(genome)
        print(f"wrote {paths.CANDIDATE_SCORES} ({len(out)} rows) and {paths.CANDIDATE_TOP500} ({len(top)} rows)")
        print(top.head(10).to_string(index=False))
        return


if __name__ == "__main__":
    main()
