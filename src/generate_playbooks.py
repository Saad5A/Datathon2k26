"""Batch-generate Gemini triage playbooks into results/cached_playbooks.json.

Pre-computes playbooks for critical CVEs so the Streamlit UI can serve instant
lookups during judging without live API latency or rate limits.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.enrich_top500 import ENRICHED_OUT, enrich_top500, save_enriched
from src.remediation_agent import (
    CACHED_PLAYBOOKS_PATH,
    clean_playbook_for_ui,
    generate_playbook,
    load_cached_playbooks,
    save_cached_playbooks,
)


def load_or_build_enriched() -> pd.DataFrame:
    if ENRICHED_OUT.exists():
        print(f"Loading enriched table from {ENRICHED_OUT}")
        return pd.read_csv(ENRICHED_OUT)
    print("results/top500_enriched.csv missing — generating via enrich_top500...")
    df = enrich_top500()
    save_enriched(df)
    return df


def select_critical_cves(df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """Prefer P0 tier; if fewer than top_n, fill with next ranks."""
    work = df.copy()
    if "rank" in work.columns:
        work = work.sort_values("rank")
    if "priority" in work.columns:
        p0 = work[work["priority"].astype(str).str.upper() == "P0"]
        if len(p0) >= top_n:
            return p0.head(top_n).reset_index(drop=True)
        remaining = work[~work.index.isin(p0.index)]
        return pd.concat([p0, remaining], ignore_index=True).head(top_n)
    return work.head(top_n).reset_index(drop=True)


def generate_cached_playbooks(
    *,
    top_n: int = 10,
    force_offline: bool = False,
    merge_existing: bool = True,
) -> dict:
    enriched = load_or_build_enriched()
    critical = select_critical_cves(enriched, top_n=top_n)
    print(f"Generating playbooks for {len(critical)} critical CVE(s)...")

    cache = load_cached_playbooks() if merge_existing else {}
    for _, row in critical.iterrows():
        cve_id = str(row["cve_id"])
        print(f"  -> {cve_id} ({row.get('priority', 'n/a')})")
        playbook = generate_playbook(row.to_dict(), force_offline=force_offline)
        cache[cve_id] = clean_playbook_for_ui(playbook)

    out = save_cached_playbooks(cache, CACHED_PLAYBOOKS_PATH)
    print(f"Wrote {out} ({len(cache)} cached playbooks)")
    return cache


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch-cache Gemini triage playbooks")
    parser.add_argument("--top-n", type=int, default=10, help="Max critical CVEs to cache")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Force offline templates (no Gemini API calls)",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace entire cache instead of merging",
    )
    args = parser.parse_args()
    generate_cached_playbooks(
        top_n=args.top_n,
        force_offline=args.offline,
        merge_existing=not args.replace,
    )


if __name__ == "__main__":
    main()
