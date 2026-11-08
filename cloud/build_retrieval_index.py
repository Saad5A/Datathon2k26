"""Build a retrieval-only Granite embedding index for the CVE drawer.

Why a separate index:
  * the ranking embeddings (`granite_embeddings_watsonx_subset.parquet`) cover
    1,500 historical CVEs and have no overlap with the 2026 top 500;
  * the watsonx Lite quota is nearly exhausted, so we use the locally cached
    IBM Granite small embedding model instead.

This index is **retrieval only**. It never scores, ranks or changes the
submitted model, and it is not used to compute any audited metric.

Run: .venv/bin/python cloud/build_retrieval_index.py
Out: data_cache/granite_embeddings_retrieval.parquet (+ .meta.json)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data_cache"
DATA = ROOT / "data"
RESULTS = ROOT / "results"

sys.path.insert(0, str(ROOT / "src" / "model"))
from candidates import masked  # noqa: E402  same exploitation-wording mask as the text model

MODEL_ID = "ibm-granite/granite-embedding-small-english-r2"
DIM = 384
HISTORICAL = CACHE / "granite_embeddings_watsonx_subset.parquet"
POOL = CACHE / "backtest_pool.parquet"
VULNS = DATA / "vulnerabilities.csv"
TOP500 = RESULTS / "top500.csv"
OUT = CACHE / "granite_embeddings_retrieval.parquet"


def _load_descriptions() -> pd.DataFrame:
    pool = pd.read_parquet(POOL, columns=["cve_id", "description"])
    vulns = pd.read_csv(VULNS, usecols=["cve_id", "description"])
    both = pd.concat([pool, vulns], ignore_index=True)
    both["cve_id"] = both["cve_id"].astype(str)
    return both.drop_duplicates("cve_id", keep="first")


def build(limit: int = 500) -> tuple[Path, dict]:
    started = time.time()
    print(f"[1/4] ids: historical subset + top {limit} of the 2026 queue", flush=True)
    hist = pd.read_parquet(HISTORICAL, columns=["cve_id"])["cve_id"].astype(str)
    top = pd.read_csv(TOP500, usecols=["cve_id"])["cve_id"].astype(str).head(limit)
    ids = pd.concat([hist, top], ignore_index=True).drop_duplicates()
    print(f"      {len(ids)} unique ids ({len(hist)} historical, {len(top)} top-2026)", flush=True)

    print("[2/4] descriptions: pool + vulnerabilities.csv (masked)", flush=True)
    desc = _load_descriptions()
    rows = ids.to_frame("cve_id").merge(desc, on="cve_id", how="left")
    missing = int(rows.description.isna().sum())
    rows = masked(rows.dropna(subset=["description"]).reset_index(drop=True))
    rows = rows[rows.description.str.strip().ne("")].reset_index(drop=True)
    if rows.empty:
        raise SystemExit("no descriptions found for the requested ids")
    print(f"      {len(rows)} texts, missing {missing}, {time.time() - started:.1f}s", flush=True)

    print(f"[3/4] embedding with {MODEL_ID} (CPU float32)", flush=True)
    import torch
    from sentence_transformers import SentenceTransformer

    torch.set_num_threads(max(1, os.cpu_count() or 1))
    model = SentenceTransformer(
        MODEL_ID,
        device="cpu",
        local_files_only=True,
        model_kwargs={"dtype": torch.float32},
    )
    model.max_seq_length = 256  # descriptions are ~100 tokens; cap for speed
    t0 = time.time()
    vectors = model.encode(
        rows.description.tolist(),
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=True,
        convert_to_numpy=True,
    ).astype(np.float32)
    if vectors.shape[1] != DIM:
        raise SystemExit(f"unexpected embedding dimension {vectors.shape[1]}, expected {DIM}")
    print(f"      embedded {len(rows)} texts in {time.time() - t0:.0f}s", flush=True)

    print("[4/4] writing parquet + meta", flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    table = pa.table(
        {
            "cve_id": pa.array(rows.cve_id.astype(str)),
            "vector": pa.FixedSizeListArray.from_arrays(pa.array(vectors.ravel()), DIM),
        }
    )
    pq.write_table(table, OUT)
    meta = {
        "model_id": MODEL_ID,
        "provider": "LOCAL_HF",
        "dimension": DIM,
        "n_rows": len(rows),
        "n_historical": int(rows.cve_id.isin(set(hist)).sum()),
        "n_top2026": int(rows.cve_id.isin(set(top)).sum()),
        "missing_descriptions": missing,
        "l2_normalised": True,
        "purpose": "retrieval-only (CVE drawer neighbours); never used for scoring or ranking",
        "ranking_embedding_model": "ibm/granite-embedding-278m-multilingual (watsonx subset, unchanged)",
        "sources": [
            "data_cache/granite_embeddings_watsonx_subset.parquet (ids)",
            "results/top500.csv (ids)",
            "data_cache/backtest_pool.parquet (descriptions)",
            "data/vulnerabilities.csv (descriptions)",
        ],
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    OUT.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return OUT, meta


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--top", type=int, default=500, help="number of 2026 top-ranked CVEs to embed")
    args = ap.parse_args()
    out, meta = build(limit=args.top)
    print(f"wrote {out} ({meta['n_rows']} x {meta['dimension']})")
    print(f"  historical {meta['n_historical']} · 2026 top {meta['n_top2026']} · missing descriptions {meta['missing_descriptions']}")


if __name__ == "__main__":
    main()
