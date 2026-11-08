"""Live dashboard for the AutoRank arena.

The arena writes `results/autorank/arena.sqlite`. This module renders:
- results/autorank/live/arena_state.json
- results/autorank/live/index.html (static shell, JS polls the JSON every 5 s)

Run:
    python -m cloud.autorank.live --watch --interval 5
Serve:
    python -m http.server 8000 --directory results/autorank/live
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import time
from pathlib import Path

import pandas as pd

from . import paths
from .racing import ARENA_DB

LIVE = paths.AUTORANK_OUT / "live"
LIVE.mkdir(parents=True, exist_ok=True)
STATE = LIVE / "arena_state.json"
INDEX = LIVE / "index.html"


EMPTY = {"generation": 0, "nodes": [], "edges": [], "champion": None, "control": None,
         "families": [], "counters": {}}


def _search_state() -> dict:
    """Fallback: show the current evolutionary search while the arena waits."""
    db = paths.AUTORANK_OUT / "leaderboard.sqlite"
    if not db.exists():
        return EMPTY
    con = sqlite3.connect(db)
    df = pd.read_sql_query("SELECT * FROM runs WHERE status='ok'", con)
    con.close()
    if df.empty:
        return EMPTY
    df = df.sort_values("id").drop_duplicates("genome_hash", keep="last")
    df = df[df["generation"].notna()].copy()
    if df.empty:
        return EMPTY
    df["generation"] = df["generation"].astype(int)
    df["metric"] = df["top243"].fillna(0.0)
    non_control = df[df["operation"] != "control"]
    best = non_control.sort_values(["top243", "top500"], ascending=False).head(1)
    if best.empty:
        best = df.sort_values(["top243", "top500"], ascending=False).head(1)
    champion = None
    if not best.empty:
        c = best.iloc[0]
        champion = {
            "id": c["genome_hash"], "model": c["model"], "features": c["features"],
            "cap": json.loads(c["postprocess"]).get("cap"),
            "top243": c["top243"], "top500": c["top500"],
            "avg_precision": c["avg_precision"], "generation": int(c["generation"]),
        }
    ctrl = df[df["operation"] == "control"]
    control = None
    if not ctrl.empty:
        c = ctrl.iloc[0]
        control = {"top243": c["top243"], "top500": c["top500"], "avg_precision": c["avg_precision"]}
    nodes = []
    for gen, grp in df.groupby("generation"):
        grp = grp.sort_values("metric", ascending=False)
        n = max(1, len(grp) - 1)
        for i, (_, r) in enumerate(grp.iterrows()):
            nodes.append({
                "id": r["genome_hash"], "generation": int(gen), "rank": i, "y": 1.0 - i / n,
                "model": r["model"], "features": r["features"],
                "cap": json.loads(r["postprocess"]).get("cap"),
                "stage": "search", "alive": 1, "reason": None,
                "screen_top243": None, "full_top243": r["top243"], "full_top500": r["top500"],
                "full_ap": r["avg_precision"], "operation": r["operation"],
                "parent_a": r["parent_a"], "parent_b": r["parent_b"],
                "is_champion": bool(champion and r["genome_hash"] == champion["id"]),
            })
    ids = {n["id"] for n in nodes}
    edges = []
    for n in nodes:
        for p in (n["parent_a"], n["parent_b"]):
            if isinstance(p, str) and p in ids:
                edges.append({"source": p, "target": n["id"]})
    families = []
    for col in ("model", "features"):
        g = df.groupby(col).size().reset_index(name="total")
        for _, r in g.iterrows():
            families.append({"kind": col, "name": r[col], "total": int(r["total"]), "alive": int(r["total"])})
    counters = {
        "genomes": int(len(df)), "alive": int(len(df)), "eliminated": 0,
        "generation": int(df["generation"].max()), "screened": 0, "full": int(len(df)),
    }
    return {"generation": counters["generation"], "nodes": nodes, "edges": edges,
            "champion": champion, "control": control, "families": families, "counters": counters}


def build_state() -> dict:
    if not ARENA_DB.exists():
        return _search_state()
    con = sqlite3.connect(ARENA_DB)
    df = pd.read_sql_query("SELECT * FROM arena_runs", con)
    con.close()
    if df.empty:
        return _search_state()
    df["generation"] = df["generation"].fillna(0).astype(int)
    # latest stage per genome is already the row (upsert); derive champion from full metrics
    full = df[(df["full_top243"].notna()) & (df["stage"] != "control")].sort_values(
        ["full_top243", "full_top500"], ascending=False
    )
    champion = None
    if not full.empty:
        c = full.iloc[0]
        champion = {
            "id": c["genome_hash"],
            "model": c["model"],
            "features": c["features"],
            "cap": json.loads(c["postprocess"]).get("cap"),
            "top243": c["full_top243"],
            "top500": c["full_top500"],
            "avg_precision": c["full_ap"],
            "generation": int(c["generation"]),
        }
    control = None
    ctrl = df[df["stage"] == "control"]
    if not ctrl.empty:
        c = ctrl.iloc[0]
        control = {"top243": c["full_top243"], "top500": c["full_top500"], "avg_precision": c["full_ap"]}
    # within-generation rank by best available metric
    df["metric"] = df["full_top243"].fillna(df["screen_top243"]).fillna(0.0)
    nodes = []
    for gen, grp in df.groupby("generation"):
        grp = grp.sort_values("metric", ascending=False)
        n = max(1, len(grp) - 1)
        for i, (_, r) in enumerate(grp.iterrows()):
            nodes.append({
                "id": r["genome_hash"],
                "generation": int(gen),
                "rank": i,
                "y": 1.0 - i / n,
                "model": r["model"],
                "features": r["features"],
                "cap": json.loads(r["postprocess"]).get("cap"),
                "stage": r["stage"],
                "alive": int(r["alive"] or 0),
                "reason": r["eliminated_reason"],
                "screen_top243": None if pd.isna(r["screen_top243"]) else float(r["screen_top243"]),
                "full_top243": None if pd.isna(r["full_top243"]) else float(r["full_top243"]),
                "full_top500": None if pd.isna(r["full_top500"]) else float(r["full_top500"]),
                "full_ap": None if pd.isna(r["full_ap"]) else float(r["full_ap"]),
                "operation": r["operation"],
                "parent_a": r["parent_a"],
                "parent_b": r["parent_b"],
                "is_champion": bool(champion and r["genome_hash"] == champion["id"]),
            })
    ids = {n["id"] for n in nodes}
    edges = []
    for n in nodes:
        for p in (n["parent_a"], n["parent_b"]):
            if isinstance(p, str) and p in ids:
                edges.append({"source": p, "target": n["id"]})
    families = []
    for col in ("model", "features"):
        g = df.groupby(col).agg(total=("genome_hash", "size"), alive=("alive", "sum")).reset_index()
        for _, r in g.iterrows():
            families.append({"kind": col, "name": r[col], "total": int(r["total"]), "alive": int(r["alive"] or 0)})
    counters = {
        "genomes": int(len(df)),
        "alive": int((df["alive"].fillna(0) == 1).sum()),
        "eliminated": int((df["alive"].fillna(0) == 0).sum()),
        "generation": int(df["generation"].max()),
        "screened": int(df["screen_top243"].notna().sum()),
        "full": int(df["full_top243"].notna().sum()),
    }
    return {"generation": counters["generation"], "nodes": nodes, "edges": edges,
            "champion": champion, "control": control, "families": families, "counters": counters}


HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>AutoRank Arena</title>
<style>
body{font-family:system-ui,Arial,sans-serif;margin:0;background:#0d1117;color:#e6edf3}
header{padding:18px 24px;background:#161b22;border-bottom:1px solid #30363d}
h1{margin:0;font-size:20px}.sub{color:#8b949e;font-size:13px;margin-top:4px}
.cards{display:flex;gap:12px;flex-wrap:wrap;padding:16px 24px}
.card{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:12px 16px;min-width:140px}
.card b{display:block;font-size:22px}.card span{color:#8b949e;font-size:12px}
#champ{border-color:#d29922}.grid{display:grid;grid-template-columns:2fr 1fr;gap:16px;padding:0 24px 24px}
@media(max-width:1000px){.grid{grid-template-columns:1fr}}
#tree,#families{background:#161b22;border:1px solid #30363d;border-radius:10px;min-height:560px}
</style></head><body>
<header><h1>AutoRank Arena — live evolution</h1>
<div class="sub">Green = alive · Red = eliminated · Gold star = champion · edges = parent → child</div></header>
<div class="cards">
<div class="card"><b id="gen">0</b><span>generation</span></div>
<div class="card"><b id="alive">0</b><span>alive</span></div>
<div class="card"><b id="elim">0</b><span>eliminated</span></div>
<div class="card"><b id="full">0</b><span>full evaluations</span></div>
<div class="card" id="champ"><b id="champname">—</b><span id="champmetric">arena champion</span></div>
<div class="card"><b id="control">—</b><span>C1 control</span></div>
</div>
<div class="grid"><div id="tree"></div><div id="families"></div></div>
<script>__PLOTLY__</script>
<script>
async function refresh(){
  try{
    const s=await (await fetch('arena_state.json?t='+Date.now())).json();
    document.getElementById('gen').textContent=s.counters.generation||0;
    document.getElementById('alive').textContent=s.counters.alive||0;
    document.getElementById('elim').textContent=s.counters.eliminated||0;
    document.getElementById('full').textContent=s.counters.full||0;
    if(s.champion){document.getElementById('champname').textContent=s.champion.model;
      document.getElementById('champmetric').textContent='top243 '+s.champion.top243+' · top500 '+s.champion.top500+' · AP '+s.champion.avg_precision;}
    if(s.control){document.getElementById('control').textContent=s.control.top243+' / '+s.control.top500;}
    const by=Object.fromEntries(s.nodes.map(n=>[n.id,n]));
    const ex=[],ey=[];
    for(const e of s.edges){const a=by[e.source],b=by[e.target];if(a&&b){ex.push(a.generation,b.generation,null);ey.push(a.y,b.y,null);}}
    const xs=s.nodes.map(n=>n.generation+(Math.random()-.5)*0.08);
    const ys=s.nodes.map(n=>n.y);
    const colors=s.nodes.map(n=>n.is_champion?'#d29922':(n.alive?'#3fb950':'#f85149'));
    const syms=s.nodes.map(n=>n.is_champion?'star':'circle');
    const sizes=s.nodes.map(n=>n.is_champion?18:(n.full_top243?12:8));
    const text=s.nodes.map(n=>`${n.model} | ${n.features}<br>stage=${n.stage} alive=${n.alive} op=${n.operation}<br>screen=${n.screen_top243} full243=${n.full_top243} full500=${n.full_top500} AP=${n.full_ap}<br>${n.reason||''}`);
    Plotly.react('tree',[
      {x:ex,y:ey,mode:'lines',line:{color:'rgba(139,148,158,.35)',width:1},hoverinfo:'skip'},
      {x:xs,y:ys,mode:'markers',marker:{color:colors,size:sizes,symbol:syms,line:{width:1,color:'#0d1117'}},text:text,hovertemplate:'%{text}<extra></extra>'}
    ],{margin:{l:40,r:20,t:20,b:40},xaxis:{title:'generation'},yaxis:{title:'within-generation rank',range:[0,1.05]},paper_bgcolor:'#161b22',plot_bgcolor:'#161b22',font:{color:'#e6edf3'},showlegend:false});
    const fam=s.families.filter(f=>f.kind==='model');
    Plotly.react('families',[{x:fam.map(f=>f.name),y:fam.map(f=>f.alive),type:'bar',name:'alive',marker:{color:'#3fb950'}},
      {x:fam.map(f=>f.name),y:fam.map(f=>f.total-f.alive),type:'bar',name:'eliminated',marker:{color:'#f85149'}}],
      {barmode:'stack',margin:{l:40,r:10,t:40,b:80},title:'survival by model family',paper_bgcolor:'#161b22',plot_bgcolor:'#161b22',font:{color:'#e6edf3'},xaxis:{tickangle:-35}});
  }catch(e){console.log(e)}
}
setInterval(refresh,5000); refresh();
</script></body></html>
"""


def write_html() -> Path:
    try:
        from plotly.offline import get_plotlyjs

        js = get_plotlyjs()
    except Exception:
        js = ""
    INDEX.write_text(HTML.replace("__PLOTLY__", js))
    return INDEX


def write_once() -> dict:
    state = build_state()
    STATE.write_text(json.dumps(state, indent=2, default=str))
    if not INDEX.exists():
        write_html()
    return state


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--interval", type=int, default=5)
    args = ap.parse_args()
    write_html()
    if not args.watch:
        s = write_once()
        print(json.dumps(s.get("counters", {}), indent=2))
        return
    while True:
        try:
            s = write_once()
            print(json.dumps(s.get("counters", {})), flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"live update failed: {exc}", flush=True)
        time.sleep(max(2, args.interval))


if __name__ == "__main__":
    main()
