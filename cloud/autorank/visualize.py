"""Evolution-tree export for AutoRank Lab.

Reads the SQLite leaderboard (generation, parents, operation) and writes:
- evolution_tree.json  (nodes, edges, best lineage)
- evolution_tree.md    (best lineage table)
- evolution_tree.html  (standalone Plotly generation tree)
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from . import paths
from .leaderboard import load_runs


def _best_lineage(df: pd.DataFrame) -> list[dict]:
    ok = df[df["status"] == "ok"].copy()
    if ok.empty:
        return []
    by_hash = {str(r["genome_hash"]): r for _, r in ok.iterrows()}
    best = ok.sort_values(["top243", "top500", "avg_precision"], ascending=False).iloc[0]
    chain = []
    seen = set()
    cur = best
    while cur is not None and str(cur["genome_hash"]) not in seen:
        seen.add(str(cur["genome_hash"]))
        chain.append(cur)
        parents = []
        for col in ("parent_a", "parent_b"):
            p = cur.get(col)
            if isinstance(p, str) and p in by_hash and p not in seen:
                parents.append(by_hash[p])
        if not parents:
            break
        cur = max(parents, key=lambda r: (r["top243"] if pd.notna(r["top243"]) else -1))
    chain.reverse()
    return chain


def _lineage_md(chain: list[dict]) -> str:
    lines = ["# Best lineage", "", "| gen | operation | model | features | cap | top243 | top500 | AP |", "|---:|---|---|---|---:|---:|---:|---:|"]
    for r in chain:
        g = json.loads(r["genome_json"])
        p = g.get("postprocess", {})
        lines.append(
            f"| {r.get('generation')} | {r.get('operation')} | {r.get('model')} | {r.get('features')} | "
            f"{p.get('cap')} | {r.get('top243')} | {r.get('top500')} | {r.get('avg_precision')} |"
        )
    return "\n".join(lines) + "\n"


def write_tree() -> Path:
    df = load_runs()
    if df.empty:
        raise RuntimeError("leaderboard is empty")
    # Keep the lineage-tracked run; fall back to all rows if older rows lack it.
    track = df[df["generation"].notna()].copy()
    if track.empty:
        track = df.copy()
        track["generation"] = 0
        track["operation"] = track["operation"].fillna("run")
    track = track.sort_values(["generation", "top243"], ascending=[True, False]).reset_index(drop=True)

    nodes = []
    by_gen: dict[int, list[pd.Series]] = {}
    for _, r in track.iterrows():
        by_gen.setdefault(int(r["generation"]), []).append(r)
    for gen, rows in by_gen.items():
        n = max(1, len(rows) - 1)
        for i, r in enumerate(rows):
            g = json.loads(r["genome_json"])
            p = g.get("postprocess", {})
            nodes.append({
                "id": str(r["genome_hash"]),
                "generation": gen,
                "y": 1.0 - (i / n),
                "model": r["model"],
                "features": r["features"],
                "cap": p.get("cap"),
                "month_allocation": p.get("month_allocation"),
                "flag_quota": p.get("flag_quota"),
                "operation": r.get("operation"),
                "parent_a": r.get("parent_a"),
                "parent_b": r.get("parent_b"),
                "top243": r.get("top243"),
                "top500": r.get("top500"),
                "avg_precision": r.get("avg_precision"),
                "fitness": r.get("fitness"),
                "status": r.get("status"),
            })
    ids = {n["id"] for n in nodes}
    edges = []
    for n in nodes:
        for p in (n["parent_a"], n["parent_b"]):
            if isinstance(p, str) and p in ids:
                edges.append({"source": p, "target": n["id"]})
    chain = _best_lineage(track)
    chain_ids = [str(r["genome_hash"]) for r in chain]
    best_id = chain_ids[-1] if chain_ids else None

    payload = {
        "nodes": nodes,
        "edges": edges,
        "best_lineage": [
            {
                "generation": int(r["generation"]),
                "operation": r.get("operation"),
                "model": r.get("model"),
                "features": r.get("features"),
                "top243": r.get("top243"),
                "top500": r.get("top500"),
                "avg_precision": r.get("avg_precision"),
                "genome_hash": str(r["genome_hash"]),
            }
            for r in chain
        ],
        "best_id": best_id,
    }
    (paths.AUTORANK_OUT / "evolution_tree.json").write_text(json.dumps(payload, indent=2, default=str))
    (paths.AUTORANK_OUT / "evolution_tree.md").write_text(_lineage_md(chain))

    try:
        import plotly.graph_objects as go

        ex, ey = [], []
        for e in edges:
            s = next(n for n in nodes if n["id"] == e["source"])
            t = next(n for n in nodes if n["id"] == e["target"])
            ex += [s["generation"], t["generation"], None]
            ey += [s["y"], t["y"], None]
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=ex, y=ey, mode="lines",
            line=dict(color="rgba(160,160,160,0.45)", width=1),
            hoverinfo="skip", showlegend=False,
        ))
        xs = [n["generation"] for n in nodes]
        ys = [n["y"] for n in nodes]
        colors = [n["top243"] if n["top243"] is not None else 0 for n in nodes]
        sizes = [6 + 10 * (n["top500"] or 0) / 500.0 for n in nodes]
        labels = [
            f"{n['model']} | {n['features']}<br>cap={n['cap']} month={n['month_allocation']} flagq={n['flag_quota']}"
            f"<br>gen={n['generation']} op={n['operation']}<br>top243={n['top243']} top500={n['top500']} AP={n['avg_precision']}"
            for n in nodes
        ]
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="markers",
            marker=dict(
                size=sizes, color=colors, colorscale="Viridis", showscale=True,
                colorbar=dict(title="top243"), line=dict(width=0.5, color="white"),
            ),
            text=labels, hovertemplate="%{text}<extra></extra>", showlegend=False,
        ))
        # highlight best lineage
        if chain_ids:
            xb = [next(n for n in nodes if n["id"] == cid)["generation"] for cid in chain_ids]
            yb = [next(n for n in nodes if n["id"] == cid)["y"] for cid in chain_ids]
            fig.add_trace(go.Scatter(
                x=xb, y=yb, mode="markers+lines",
                line=dict(color="crimson", width=2),
                marker=dict(size=13, color="crimson", symbol="star"),
                name="best lineage", hoverinfo="skip",
            ))
        fig.update_layout(
            title="AutoRank Lab — evolution tree",
            xaxis_title="Generation",
            yaxis_title="Within-generation rank (best at top)",
            template="plotly_white",
            height=750,
            margin=dict(l=40, r=20, t=60, b=40),
        )
        fig.write_html(paths.AUTORANK_OUT / "evolution_tree.html", include_plotlyjs="inline")
    except Exception as exc:  # noqa: BLE001
        (paths.AUTORANK_OUT / "evolution_tree.html").write_text(
            f"<html><body><h1>Evolution tree</h1><p>Plotly unavailable: {exc}</p>"
            f"<p>See evolution_tree.json and evolution_tree.md.</p></body></html>"
        )

    return paths.AUTORANK_OUT / "evolution_tree.html"
