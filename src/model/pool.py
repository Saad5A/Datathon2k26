"""Build and cache the backtest pool (port of the first-pass build.py + model1.py).

Run: .venv/bin/python src/model/pool.py        (uses the cache if present)
     .venv/bin/python src/model/pool.py --force (rebuilds the cache)

One row per CVE published 2024-01..2025-09, snapshot = publish month, excluding
CVEs already on KEV at the snapshot. See FEATURES.md for each feature's as-of logic.
"""
import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data_cache" / "backtest_pool.parquet"

LABEL_CAP = "2025-12-31"
LABEL_WINDOW_DAYS = 365
FIRST_MONTH, LAST_MONTH = "2024-01", "2025-09"
HISTORY_START = "2021-01-01"  # first pass kept only CVEs published 2021+, also for assigner history

V_COLS = ["cve_id", "published", "nvd_status", "assigner", "description", "cvss3_score",
          "attack_vector", "attack_complexity", "privileges_required", "user_interaction", "scope",
          "confidentiality_impact", "integrity_impact", "availability_impact", "cwe_ids",
          "n_references", "n_affected_cpes", "cvss3_source"]
FLAGS = ["exploitdb", "metasploit", "nuclei", "poc_github"]
VECTOR_COLS = ["attack_vector", "attack_complexity", "privileges_required", "user_interaction",
               "scope", "confidentiality_impact", "integrity_impact", "availability_impact"]

SIGNAL_FEATURES = ["epss_f", *FLAGS, "anyx", "nx"]
ASSIGNER_FEATURES = ["asg_rate", "asg_kev"]
BEST_FEATURES = SIGNAL_FEATURES + ASSIGNER_FEATURES + ["txt"]  # txt: out-of-fold text score, added by the model script
LEAKY_COLUMNS = ["nvd_status", "n_affected_cpes", "n_references", "last_modified", "ncpe",
                 "cvss3_score", "cvss3", "cvss3_source"]  # the last three: blank-score patterns


def data_dir():
    """IBM_DATA_DIR, then ./data, then ./.data/data (repo-relative)."""
    env = os.environ.get("IBM_DATA_DIR")
    if env:
        if not (Path(env) / "known_exploited.csv").exists():
            raise FileNotFoundError(f"IBM_DATA_DIR={env} does not contain known_exploited.csv")
        return Path(env)
    for d in (ROOT / "data", ROOT / ".data" / "data"):
        if (d / "known_exploited.csv").exists():
            return d
    raise FileNotFoundError(f"IBM data not found: set IBM_DATA_DIR or unzip into {ROOT / 'data'} "
                            f"or {ROOT / '.data' / 'data'}")


def load_kev(cols=("cve_id", "date_added")):
    return pd.read_csv(data_dir() / "known_exploited.csv", usecols=list(cols), parse_dates=["date_added"])


def load_vulns(cols=V_COLS):
    """CVEs published from HISTORY_START on, in file order (same filter as build.py)."""
    chunks = []
    for c in pd.read_csv(data_dir() / "vulnerabilities.csv", usecols=list(cols),
                         parse_dates=["published"], chunksize=100_000):
        chunks.append(c[c.published >= HISTORY_START])
    v = pd.concat(chunks)
    v["ym"] = v.published.dt.strftime("%Y-%m")
    return v


def load_signals(months=None, ids=None):
    """Signal rows restricted to `months`/`ids`. Filtering here only saves memory: the merge is on both keys."""
    keep = []
    for f in ["exploit_signals_2024.csv", "exploit_signals_2025.csv"]:
        for c in pd.read_csv(data_dir() / f, chunksize=500_000, dtype={"cve_id": str}):
            if months is not None:
                c = c[c.month.isin(months)]
            if ids is not None:
                c = c[c.cve_id.isin(ids)]
            keep.append(c)
    return pd.concat(keep).rename(columns={"month": "ym"})


def label_limit(snap_end, cap=LABEL_CAP):
    """Last date a KEV addition counts as positive: snapshot end + 365 days, capped."""
    return (snap_end + pd.Timedelta(days=LABEL_WINDOW_DAYS)).clip(upper=pd.Timestamp(cap))


def make_labels(date_added, snap_end, cap=LABEL_CAP):
    """1 if date_added falls in (snap_end, label_limit]. CVEs with date_added <= snap_end get 0 here
    and are removed from the pool anyway. `cap` lets a sensitivity test restrict what labels can see."""
    return ((date_added > snap_end) & (date_added <= label_limit(snap_end, cap))).astype(int)


def assigner_history(kv, v, month):
    """As-of `month` assigner KEV rate and count, from rows strictly before the month's first day.

    rate = KEV additions before month start / (CVEs published before month start + 20).
    kv: KEV rows with assigner attached; v: CVEs with assigner and published.
    """
    start = pd.Timestamp(month + "-01")
    kev_count = kv[kv.date_added < start].groupby("assigner").size()
    published_count = v[v.published < start].groupby("assigner").size()
    rate = kev_count.reindex(published_count.index).fillna(0) / (published_count + 20)
    return rate, kev_count


def kev_with_assigner(k, v):
    return k.merge(v[["cve_id", "assigner", "published"]], on="cve_id", how="left").dropna(subset=["assigner"])


def build_pool():
    v = load_vulns()
    k = load_kev()
    b = v[(v.ym >= FIRST_MONTH) & (v.ym <= LAST_MONTH)]
    sig = load_signals(months=set(b.ym), ids=set(b.cve_id))
    b = b.merge(sig, on=["cve_id", "ym"], how="left")
    b = b[b.in_kev.fillna(0) == 0].merge(k, on="cve_id", how="left")
    b["snap_end"] = pd.to_datetime(b.ym + "-01") + pd.offsets.MonthEnd(0)
    b = b[~(b.date_added.notna() & (b.date_added <= b.snap_end))].copy()
    b["y"] = make_labels(b.date_added, b.snap_end)

    # Snapshot-month signals. A CVE with no signal row that month counts as flags 0, EPSS -1.
    for c in FLAGS:
        b[c] = b[c].fillna(0)
    b["anyx"] = b[FLAGS].max(axis=1)
    b["nx"] = b[FLAGS].sum(axis=1)
    b["epss_f"] = b.epss.fillna(-1)

    # Assigner history, recomputed per snapshot month from strictly earlier rows.
    kv = kev_with_assigner(k, v)
    history = {m: assigner_history(kv, v, m) for m in sorted(b.ym.unique())}
    b["asg_rate"] = [history[m][0].get(a, 0) for m, a in zip(b.ym, b.assigner)]
    b["asg_kev"] = [history[m][1].get(a, 0) for m, a in zip(b.ym, b.assigner)]

    # Structured columns: comparison rows only, not used by the signals+assigner+text model.
    for c in VECTOR_COLS:
        b[c + "_c"] = b[c].astype("category").cat.codes
    b["cwe1"] = b.cwe_ids.fillna("").str.split(";").str[0]
    # ponytail: top-40 CWE list is taken over the whole pool as in the first pass (test rows pick the
    # vocabulary, no labels involved); fit it on train if structured features ever reach a real model.
    for c in b.cwe1.value_counts().head(40).index:
        b["cwe_" + c] = (b.cwe1 == c).astype(int)
    b["cvss3"] = b.cvss3_score.fillna(-1)
    return b.reset_index(drop=True)


def structured_features(df):
    """Same column selection and order as model2.py."""
    return (["cvss3"] + [c for c in df.columns if c.endswith("_c")]
            + [c for c in df.columns if c.startswith("cwe_") and c not in ("cwe_ids", "cwe1")])


def load_pool(force=False):
    if CACHE.exists() and not force:
        return pd.read_parquet(CACHE)
    pool = build_pool()
    CACHE.parent.mkdir(exist_ok=True)
    pool.to_parquet(CACHE, index=False)
    # Return what is on disk so a fresh build and a cache hit go through the same path.
    return pd.read_parquet(CACHE)


if __name__ == "__main__":
    pool = load_pool(force="--force" in sys.argv)
    train, test = pool[pool.ym < "2025-01"], pool[pool.ym >= "2025-01"]
    print(f"cache {CACHE}")
    print(f"pool rows {len(pool)} positives {pool.y.sum()}")
    print(f"train rows {len(train)} positives {train.y.sum()}")
    print(f"test  rows {len(test)} positives {test.y.sum()}")
