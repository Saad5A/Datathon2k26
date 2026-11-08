"""Data and fold loading for AutoRank Lab.

All features are time-safe: the fold builder caps training labels at the train
end and reuses the audited pool/assigner-history logic from src/model.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from . import paths

# The audited baseline modules use top-level imports (import metrics, ...).
if str(paths.MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(paths.MODEL_DIR))

import candidates as C  # noqa: E402
import pool as P  # noqa: E402
import reproduce_first_pass as R  # noqa: E402

from .config import FOLDS  # noqa: E402


def _add_derived(df: pd.DataFrame) -> pd.DataFrame:
    """Add safe derived features and temporal publication counts."""
    out = df.copy()
    if "snap_month" not in out.columns:
        out["snap_month"] = out["ym"].astype(str)
    out["asg_kev_log"] = np.log1p(out["asg_kev"].clip(lower=0))
    # Recover the denominator used by the audited rate: rate = kev / (n + 20).
    denom = np.where(out["asg_rate"] > 0, out["asg_kev"] / out["asg_rate"] - 20.0, 0.0)
    out["asg_cves_log"] = np.log1p(np.clip(denom, 0.0, None))
    out["age_days"] = (out["snap_end"] - out["published"]).dt.days.clip(lower=0)
    out["month_idx"] = out["snap_month"].astype(str).map(
        {m: i for i, m in enumerate(sorted(out["snap_month"].astype(str).unique()), start=1)}
    )
    out["month_volume"] = out.groupby("snap_month")["cve_id"].transform("size")
    out["same_day_count"] = out.groupby("published")["cve_id"].transform("size")
    out["assigner_month_volume"] = out.groupby(["snap_month", "assigner"])["cve_id"].transform("size")
    return _add_assigner24(out)


def _add_assigner24(df: pd.DataFrame) -> pd.DataFrame:
    """24-month assigner KEV history, computed only from rows before the month."""
    if "asg24_rate" in df.columns:
        return df
    kev = P.load_kev()
    v = P.load_vulns(cols=["cve_id", "published", "assigner"])
    kv = P.kev_with_assigner(kev, v)
    rows = []
    for month in sorted(df["snap_month"].dropna().unique()):
        start = pd.Timestamp(f"{month}-01")
        lo = start - pd.DateOffset(months=24)
        kw = kv[(kv["date_added"] >= lo) & (kv["date_added"] < start)]
        vw = v[(v["published"] >= lo) & (v["published"] < start)]
        counts = kw.groupby("assigner").size().rename("asg24_kev")
        denom = vw.groupby("assigner").size().rename("asg24_cves")
        frame = pd.concat([counts, denom], axis=1).fillna(0).reset_index()
        frame["snap_month"] = month
        frame["asg24_rate"] = np.where(
            frame["asg24_cves"] > 0, frame["asg24_kev"] / frame["asg24_cves"], 0.0
        )
        rows.append(frame)
    if not rows:
        for c in ("asg24_rate", "asg24_kev", "asg24_kev_log"):
            df[c] = 0.0
        return df
    hist = pd.concat(rows, ignore_index=True)
    hist["asg24_kev_log"] = np.log1p(hist["asg24_kev"].clip(lower=0))
    cols = ["snap_month", "assigner", "asg24_rate", "asg24_kev", "asg24_kev_log"]
    out = df.merge(hist[cols], on=["snap_month", "assigner"], how="left")
    for c in ("asg24_rate", "asg24_kev", "asg24_kev_log"):
        out[c] = out[c].fillna(0.0)
    return out


def load_base_pool(force: bool = False) -> pd.DataFrame:
    """Load the audited pool and add lab-safe derived features (cached)."""
    cache = paths.CACHE / "pool_derived.parquet"
    if cache.exists() and not force:
        return pd.read_parquet(cache)
    pool = P.load_pool()
    out = _add_derived(pool)
    out.to_parquet(cache, index=False)
    return out


def _fold_path(name: str, seed: int) -> Path:
    d = paths.CACHE / "folds"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{name}_seed{seed}.parquet"


def load_fold(name: str, seed: int = 0, use_cache: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (train, test) with capped labels and a TF-IDF text score.

    Cached per (fold, seed). The expensive first call fits 5-fold OOF TF-IDF.
    """
    path = _fold_path(name, seed)
    if use_cache and path.exists():
        df = pd.read_parquet(path)
        return df[df["_split"] == "train"].drop(columns="_split"), df[df["_split"] == "test"].drop(columns="_split")

    spec = FOLDS[name]
    pool = load_base_pool()
    kev = P.load_kev()
    tr, te, y_tr = C.fold_data(pool, kev, spec)
    tr = tr.copy()
    te = te.copy()
    tr["positive"] = y_tr
    te["positive"] = te["y"].astype(int)

    Xtr, Xte = R.text_vectors(C.masked(tr), C.masked(te))
    oof = R.text_oof(Xtr, y_tr, fold_seed=seed)
    st = R.text_test_score(Xtr, y_tr, Xte)
    tr["txt"] = oof
    te["txt"] = st

    tr["_split"] = "train"
    te["_split"] = "test"
    pd.concat([tr, te], ignore_index=True).to_parquet(path, index=False)
    return tr, te


def load_scoreboard_base() -> pd.DataFrame:
    """2026 scoreboard with assigner/description and the audited 2026 features."""
    sb = pd.read_csv(paths.DATA / "scoreboard_2026.csv", dtype={"cve_id": str})
    v = P.load_vulns(cols=["cve_id", "published", "assigner", "description"])
    sb = sb.merge(v[["cve_id", "assigner", "description"]], on="cve_id", how="left", validate="one_to_one")
    assert sb["assigner"].notna().all() and len(sb) == 72_670
    for f in P.FLAGS:
        sb[f] = sb[f].fillna(0).astype(int)
    sb["anyx"] = sb[P.FLAGS].max(axis=1)
    sb["nx"] = sb[P.FLAGS].sum(axis=1)
    sb["any_public_exploit"] = sb["anyx"]
    sb["epss_f"] = sb["epss"].fillna(-1.0)
    sb["snap_end"] = pd.to_datetime(sb["snapshot_month"].astype(str) + "-01") + pd.offsets.MonthEnd(0)
    sb["ym"] = sb["snapshot_month"].astype(str)
    sb["published"] = pd.to_datetime(sb["published"], errors="coerce")
    # Assigner history as of each snapshot month, using only KEV rows before it.
    kev = P.load_kev()
    vv = P.load_vulns(cols=["cve_id", "published", "assigner"])
    kv = P.kev_with_assigner(kev, vv)
    hist = {m: P.assigner_history(kv, vv, m) for m in sorted(sb["ym"].unique())}
    sb["asg_rate"] = [hist[m][0].get(a, 0.0) for m, a in zip(sb["ym"], sb["assigner"])]
    sb["asg_kev"] = [hist[m][1].get(a, 0) for m, a in zip(sb["ym"], sb["assigner"])]
    sb["asg_kev"] = sb["asg_kev"].astype(int)
    sb["asg_rate"] = sb["asg_rate"].astype(float)
    sb["asg_kev_log"] = np.log1p(sb["asg_kev"].clip(lower=0))
    denom = np.where(sb["asg_rate"] > 0, sb["asg_kev"] / sb["asg_rate"] - 20.0, 0.0)
    sb["asg_cves_log"] = np.log1p(np.clip(denom, 0.0, None))
    sb["age_days"] = (sb["snap_end"] - sb["published"]).dt.days.clip(lower=0)
    sb["month_idx"] = sb["ym"].map({m: i for i, m in enumerate(sorted(sb["ym"].unique()), start=1)})
    sb["month_volume"] = sb.groupby("ym")["cve_id"].transform("size")
    sb["same_day_count"] = sb.groupby("published")["cve_id"].transform("size")
    sb["assigner_month_volume"] = sb.groupby(["ym", "assigner"])["cve_id"].transform("size")
    sb["snap_month"] = sb["ym"].astype(str)
    sb = _add_assigner24(sb)
    return sb


def add_text_score_2026(sb: pd.DataFrame) -> pd.DataFrame:
    """Fit TF-IDF on all labelled pool rows and score the 2026 rows."""
    pool = load_base_pool()
    tr = pool[["cve_id", "description"]].copy()
    tr["positive"] = pool["y"].astype(int)
    Xtr, Xte = R.text_vectors(C.masked(tr), C.masked(sb))
    st = R.text_test_score(Xtr, tr["positive"].to_numpy(), Xte)
    out = sb.copy()
    out["txt"] = st
    return out
