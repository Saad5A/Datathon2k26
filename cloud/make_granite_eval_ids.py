"""Build a quota-safe CVE id list so the watsonx Lite slice covers backtest positives.

Writes data_cache/granite_eval_ids.csv for:
  python cloud/embed_granite.py --provider WATSONX --ids data_cache/granite_eval_ids.csv \\
      --out data_cache/granite_embeddings_watsonx_evalslice.parquet
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "model"))
from candidates import FOLDS, fold_data  # noqa: E402
from pool import load_kev, load_pool  # noqa: E402

OUT = ROOT / "data_cache" / "granite_eval_ids.csv"
EXISTING = ROOT / "data_cache" / "granite_embeddings_watsonx_subset.parquet"


def main() -> None:
    have = set()
    if EXISTING.exists():
        have = set(pd.read_parquet(EXISTING, columns=["cve_id"]).cve_id.astype(str))

    pool, kev = load_pool(), load_kev()
    need: list[str] = []
    # Priority: every test positive, then a modest negative sample (Lite token budget).
    neg_per_fold = {"fold1": 220, "fold2": 150}
    for name, spec in FOLDS.items():
        tr, te, y_tr = fold_data(pool, kev, spec)
        pos = te.loc[te.y == 1, "cve_id"].astype(str).tolist()
        neg = te.loc[te.y == 0, "cve_id"].astype(str)
        n_neg = min(neg_per_fold[name], len(neg))
        neg_sample = neg.sample(n=n_neg, random_state=0).tolist()
        # Train positives for the text LR (many already in the first Lite slice).
        tr_pos = tr.loc[y_tr == 1, "cve_id"].astype(str).tolist()
        print(f"{name}: +{len(pos)} test pos, +{len(neg_sample)} test neg, +{len(tr_pos)} train pos")
        need.extend(pos)
        need.extend(neg_sample)
        need.extend(tr_pos)

    uniq = sorted(set(need) - have)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"cve_id": uniq}).to_csv(OUT, index=False)
    print(f"wrote {OUT} ({len(uniq)} new ids; already embedded {len(have)})")


if __name__ == "__main__":
    main()
