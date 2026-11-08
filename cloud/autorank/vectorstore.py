"""Time-safe vector retrieval features for AutoRank Lab.

Vector DB / index:
- default: FAISS inner-product index over L2-normalized embeddings;
- fallback: sklearn NearestNeighbors (slow on full data).
Embeddings:
- default TF-IDF + TruncatedSVD (CPU, no external model);
- optional IBM Granite embeddings if a cached embeddings file is available.

Time safety:
- embeddings are fitted on the training split only for backtest folds;
- the neighbour index for a snapshot month contains only CVEs published before
  that month, with KEV labels known before the snapshot month;
- the 2026 index contains only 2024-2025 pool CVEs.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import normalize

from . import data, paths

try:  # optional
    import faiss  # type: ignore

    HAS_FAISS = True
except Exception:  # noqa: BLE001
    HAS_FAISS = False


def _texts(df: pd.DataFrame) -> list[str]:
    if "description" not in df.columns:
        return [""] * len(df)
    return data.C.masked(df)["description"].fillna("").astype(str).tolist()


def fit_svd(train_texts: list[str], test_texts: list[str], n_components: int = 128) -> tuple[np.ndarray, np.ndarray]:
    vec = TfidfVectorizer(
        ngram_range=(1, 2),
        min_df=5,
        max_features=50_000,
        sublinear_tf=True,
        strip_accents="unicode",
    )
    Xtr = vec.fit_transform(train_texts)
    Xte = vec.transform(test_texts)
    n_components = min(n_components, max(2, min(Xtr.shape) - 1))
    svd = TruncatedSVD(n_components=n_components, random_state=42)
    Ztr = normalize(svd.fit_transform(Xtr))
    Zte = normalize(svd.transform(Xte))
    return Ztr.astype("float32"), Zte.astype("float32")


def _index(matrix: np.ndarray):
    if HAS_FAISS:
        idx = faiss.IndexFlatIP(matrix.shape[1])
        idx.add(matrix)
        return idx
    return NearestNeighbors(n_neighbors=min(25, len(matrix)), metric="cosine", n_jobs=-1).fit(matrix)


def _query(index, matrix: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
    k = min(k, len(matrix)) if hasattr(index, "ntotal") else k
    if HAS_FAISS:
        sims, ids = index.search(matrix, k)
        return ids, sims
    dist, ids = index.kneighbors(matrix, n_neighbors=k)
    return ids, 1.0 - dist


def _features_for_month(
    train: pd.DataFrame,
    Ztr: np.ndarray,
    query: pd.DataFrame,
    Zq: np.ndarray,
    month: str,
    k: int,
) -> pd.DataFrame:
    start = pd.Timestamp(f"{month}-01")
    # historical index: training CVEs published before the month start
    hist_mask = train["published"] < start
    hist = train.loc[hist_mask]
    if len(hist) < k:
        out = pd.DataFrame({
            "cve_id": query["cve_id"].to_numpy(),
            "vec_kev_rate": 0.0,
            "vec_kev_count": 0,
            "vec_sim_mean": 0.0,
            "vec_sim_max": 0.0,
        })
        return out
    Z = Ztr[hist_mask.to_numpy()]
    labels = (hist["date_added"].notna() & (hist["date_added"] <= start)).to_numpy(dtype=float)
    index = _index(Z)
    ids, sims = _query(index, Zq, k)
    ids = np.asarray(ids)
    sims = np.asarray(sims)
    lab = labels[ids]
    out = pd.DataFrame({
        "cve_id": query["cve_id"].to_numpy(),
        "vec_kev_rate": lab.mean(axis=1),
        "vec_kev_count": lab.sum(axis=1),
        "vec_sim_mean": sims.mean(axis=1),
        "vec_sim_max": sims.max(axis=1),
    })
    return out


def build_fold_features(fold: str, k: int = 25, n_components: int = 128) -> pd.DataFrame:
    """Build vector features for a backtest fold (train and test rows)."""
    tr, te = data.load_fold(fold, seed=0)
    tr_text, te_text = _texts(tr), _texts(te)
    Ztr, Zte = fit_svd(tr_text, te_text, n_components=n_components)
    rows = []
    for month in sorted(tr["snap_month"].unique()):
        qmask = (tr["snap_month"] == month).to_numpy()
        if not qmask.any():
            continue
        rows.append(_features_for_month(tr, Ztr, tr.loc[qmask], Ztr[qmask], month, k))
    for month in sorted(te["snap_month"].unique()):
        qmask = (te["snap_month"] == month).to_numpy()
        if not qmask.any():
            continue
        rows.append(_features_for_month(tr, Ztr, te.loc[qmask], Zte[qmask], month, k))
    out = pd.concat(rows, ignore_index=True)
    out.to_parquet(paths.CACHE / f"vector_{fold}.parquet", index=False)
    return out


def build_2026_features(k: int = 25, n_components: int = 128) -> pd.DataFrame:
    """Build vector features for the 2026 scoreboard using only 2024-2025 pool CVEs."""
    pool = data.load_base_pool()
    sb = data.load_scoreboard_base()
    Zpool, Zsb = fit_svd(_texts(pool), _texts(sb), n_components=n_components)
    rows = []
    for month in sorted(sb["snapshot_month"].astype(str).unique()):
        qmask = (sb["snapshot_month"].astype(str) == month).to_numpy()
        if not qmask.any():
            continue
        rows.append(_features_for_month(pool, Zpool, sb.loc[qmask], Zsb[qmask], month, k))
    out = pd.concat(rows, ignore_index=True)
    out.to_parquet(paths.CACHE / "vector_2026.parquet", index=False)
    return out


def attach_to_folds() -> None:
    """Merge cached vector features into fold caches (in place, only if present)."""
    d = paths.CACHE / "folds"
    for p in sorted(d.glob("*.parquet")):
        fold = p.stem.split("_seed")[0]
        vp = paths.CACHE / f"vector_{fold}.parquet"
        if not vp.exists():
            continue
        df = pd.read_parquet(p)
        vec = pd.read_parquet(vp)
        if "vec_kev_rate" in df.columns:
            continue
        df = df.merge(vec, on="cve_id", how="left")
        for c in ("vec_kev_rate", "vec_kev_count", "vec_sim_mean", "vec_sim_max"):
            df[c] = df[c].fillna(0.0)
        df.to_parquet(p, index=False)
        print(f"attached vector features to {p.name}")


def attach_to_2026() -> None:
    """Merge cached 2026 vector features into a scoreboard frame (caller-side helper)."""
    vp = paths.CACHE / "vector_2026.parquet"
    if not vp.exists():
        return
    vec = pd.read_parquet(vp)
    # caller merges; kept as a separate function for clarity
    return vec
