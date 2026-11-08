#!/usr/bin/env python
"""Build the dashboard data files from the archived AutoRank trees.

Sources (read-only):
- audit/evidence_2026-11-08-gate/archive_final/blind/evolution_tree.json
- audit/evidence_2026-11-08-gate/archive_final/c1opt/evolution_tree.json
- evolution/assets/arena_raw.json (dumped from results/autorank/arena.sqlite on the server)
"""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "assets"
OUT.mkdir(parents=True, exist_ok=True)

FAMILY_COLORS = {
    "gam": "#ffd166",
    "extra_trees": "#2ec4b6",
    "logistic": "#4cc9f0",
    "xgboost": "#f77f00",
    "hgb": "#ef476f",
    "catboost": "#b388ff",
    "random_forest": "#8ac926",
    "adaboost": "#ff70a6",
    "mlp": "#adb5bd",
    "lightgbm": "#c7f464",
    "gradient_boosting": "#e09f3e",
    "unknown": "#6c757d",
}
MODELS = list(FAMILY_COLORS)


def clean(v):
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if isinstance(v, dict):
        return {k: clean(x) for k, x in v.items()}
    if isinstance(v, list):
        return [clean(x) for x in v]
    return v


def normalize_node(n: dict, search: str, champion_id: str | None, control_id: str | None) -> dict:
    out = {
        "id": n.get("id"),
        "search": search,
        "generation": int(n.get("generation") or 0),
        "model": n.get("model") or "unknown",
        "features": n.get("features") or "",
        "cap": n.get("cap"),
        "flag_quota": n.get("flag_quota"),
        "month_allocation": n.get("month_allocation"),
        "operation": n.get("operation") or "init",
        "parent_a": None if n.get("parent_a") in (None, "", "nan") else n.get("parent_a"),
        "parent_b": None if n.get("parent_b") in (None, "", "nan") else n.get("parent_b"),
        "top243": n.get("top243"),
        "top500": n.get("top500"),
        "avg_precision": n.get("avg_precision"),
        "fitness": n.get("fitness"),
        "auc": n.get("auc"),
        "complexity": n.get("complexity"),
        "status": n.get("status"),
        "alive": n.get("alive"),
        "reason": n.get("reason"),
        "stage": n.get("stage") or "search",
        "screen_top243": n.get("screen_top243"),
        "screen_top500": n.get("screen_top500"),
        "screen_ap": n.get("screen_ap"),
    }
    out = clean(out)
    out["is_champion"] = bool(champion_id and out["id"] == champion_id)
    out["is_control"] = bool(control_id and out["id"] == control_id)
    out["family"] = out["model"] if out["model"] in FAMILY_COLORS else "unknown"
    return out


def build_search(source: str, search: str, dest: str) -> dict:
    d = json.loads((ROOT / source).read_text())
    raw_nodes = d.get("nodes", [])
    champion_id = d.get("best_id")
    control_id = None
    for n in raw_nodes:
        if n.get("operation") == "control":
            control_id = n.get("id")
            break
    nodes = [normalize_node(n, search, champion_id, control_id) for n in raw_nodes]
    ids = {n["id"] for n in nodes}
    edges = [
        {"source": e["source"], "target": e["target"]}
        for e in d.get("edges", [])
        if e.get("source") in ids and e.get("target") in ids
    ]
    champion = next((n for n in nodes if n["is_champion"]), None)
    control = next((n for n in nodes if n["is_control"]), None)
    story = d.get("best_lineage", [])
    # Attach the full node payload to each lineage step where possible.
    by_gen = {}
    for n in nodes:
        by_gen.setdefault(n["generation"], []).append(n)
    story_nodes = []
    for step in story:
        gid = step.get("genome_hash")
        node = next((n for n in nodes if n["id"] == gid), None)
        if node is None:
            node = {
                "id": gid,
                "generation": step.get("generation"),
                "model": step.get("model"),
                "features": step.get("features"),
                "top243": step.get("top243"),
                "top500": step.get("top500"),
                "avg_precision": step.get("avg_precision"),
                "operation": step.get("operation"),
                "search": search,
                "is_champion": gid == champion_id,
                "is_control": False,
            }
        story_nodes.append(node)
    payload = {
        "search": search,
        "source": source,
        "nodes": nodes,
        "edges": edges,
        "champion": champion,
        "control": control,
        "story": story_nodes,
        "stats": {
            "nodes": len(nodes),
            "edges": len(edges),
            "generations": max((n["generation"] for n in nodes), default=0),
            "families": sorted({n["model"] for n in nodes}),
            "ok": sum(1 for n in nodes if n.get("status") == "ok"),
            "errors": sum(1 for n in nodes if n.get("status") == "error"),
            "max_top243": max((n["top243"] for n in nodes if n.get("top243") is not None), default=None),
            "max_top500": max((n["top500"] for n in nodes if n.get("top500") is not None), default=None),
            "max_ap": max((n["avg_precision"] for n in nodes if n.get("avg_precision") is not None), default=None),
        },
    }
    (OUT / dest).write_text(json.dumps(payload, separators=(",", ":"), allow_nan=False))
    return payload


def arena_payload() -> dict:
    d = json.loads((ROOT / "evolution/assets/arena_raw.json").read_text())
    raw_nodes = d.get("nodes", [])
    champion_id = d.get("best_id")
    control_id = d.get("control_id")
    nodes = []
    for n in raw_nodes:
        m = normalize_node(n, "arena", champion_id, control_id)
        m["alive"] = n.get("alive")
        m["reason"] = n.get("reason")
        m["stage"] = n.get("stage")
        m["screen_top243"] = n.get("screen_top243")
        m["screen_top500"] = n.get("screen_top500")
        m["screen_ap"] = n.get("screen_ap")
        m["genome"] = n.get("genome")
        nodes.append(m)
    ids = {n["id"] for n in nodes}
    edges = [
        {"source": e["source"], "target": e["target"]}
        for e in d.get("edges", [])
        if e.get("source") in ids and e.get("target") in ids
    ]
    champion = next((n for n in nodes if n["id"] == champion_id), None)
    control = next((n for n in nodes if n["id"] == control_id), None)
    # Parent chain from the champion back to a root (for the story).
    byid = {n["id"]: n for n in nodes}
    chain = []
    cur = champion
    seen = set()
    while cur and cur["id"] not in seen:
        chain.append(cur)
        seen.add(cur["id"])
        cur = byid.get(cur.get("parent_a")) or byid.get(cur.get("parent_b"))
    chain.reverse()
    payload = {
        "search": "arena",
        "source": "evolution/assets/arena_raw.json",
        "nodes": nodes,
        "edges": edges,
        "champion": champion,
        "control": control,
        "story": chain,
        "stats": {
            "nodes": len(nodes),
            "edges": len(edges),
            "generations": max((n["generation"] for n in nodes), default=0),
            "families": sorted({n["model"] for n in nodes}),
            "ok": sum(1 for n in nodes if n.get("status") == "ok" or n.get("top243") is not None),
            "errors": sum(1 for n in nodes if n.get("status") == "error"),
            "max_top243": max((n["top243"] for n in nodes if n.get("top243") is not None), default=None),
            "max_top500": max((n["top500"] for n in nodes if n.get("top500") is not None), default=None),
            "max_ap": max((n["avg_precision"] for n in nodes if n.get("avg_precision") is not None), default=None),
            "alive": sum(1 for n in nodes if n.get("alive") == 1),
            "eliminated": sum(1 for n in nodes if n.get("alive") == 0),
        },
    }
    (OUT / "arena.json").write_text(json.dumps(payload, separators=(",", ":"), allow_nan=False))
    return payload


def main() -> None:
    blind = build_search(
        "audit/evidence_2026-11-08-gate/archive_final/blind/evolution_tree.json",
        "blind",
        "blind.json",
    )
    c1opt = build_search(
        "audit/evidence_2026-11-08-gate/archive_final/c1opt/evolution_tree.json",
        "c1opt",
        "c1opt.json",
    )
    arena = arena_payload()
    c1 = blind.get("control") or {}
    champion = blind.get("champion") or {}
    meta = {
        "title": "AutoRank Lab — Evolution Observatory",
        "subtitle": "Time-safe CVE ranking · 2025 backtest · 2026 scoreboard",
        "generated_from": [
            "audit/evidence_2026-11-08-gate/archive_final/blind/evolution_tree.json",
            "audit/evidence_2026-11-08-gate/archive_final/c1opt/evolution_tree.json",
            "results/autorank/arena.sqlite (dumped to evolution/assets/arena_raw.json)",
        ],
        "family_colors": FAMILY_COLORS,
        "kpis": {
            "evaluations": 2213 + 1028 + 2130,
            "blind_evaluations": 2213,
            "c1opt_evaluations": 1028,
            "arena_evaluations": 2130,
            "generations": 80,
            "families": 11,
            "champion": {
                "model": champion.get("model"),
                "features": champion.get("features"),
                "top243": champion.get("top243"),
                "top500": champion.get("top500"),
                "avg_precision": champion.get("avg_precision"),
                "generation": champion.get("generation"),
            },
            "c1": {
                "model": c1.get("model"),
                "features": c1.get("features"),
                "top243": c1.get("top243"),
                "top500": c1.get("top500"),
                "avg_precision": c1.get("avg_precision"),
            },
            "gate": {
                "top243_gain": 7.5,
                "top500_gain": 4.0,
                "ap_gain": 0.054171413487934104,
            },
            "submission": {
                "file": "results/top500.csv",
                "model": "G2 (C1 + Granite text)",
                "note": "After pulling origin/feat/model-ranking, the audited submission is G2, adopted by the pre-registered IBM tie-break with no measurable gain over C1.",
            },
        },
        "story_note": "C1 is shown at the end as a baseline comparison branch.",
    }
    (OUT / "meta.json").write_text(json.dumps(meta, indent=1, allow_nan=False))
    print("wrote", {k: len(v["nodes"]) for k, v in [("blind", blind), ("c1opt", c1opt), ("arena", arena)]})
    print("meta", json.dumps(meta["kpis"], indent=1)[:800])


if __name__ == "__main__":
    main()
