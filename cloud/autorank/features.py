"""Feature assembly and post-processing for AutoRank Lab."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import FEATURE_GROUPS, H500

EXPOSURE_9 = [62, 61, 60, 59, 57, 54, 53, 48, 46]  # Jan..Sep, sums to 500


def _available(df: pd.DataFrame, cols: list[str]) -> bool:
    return all(c in df.columns for c in cols)


def resolve_groups(df: pd.DataFrame, groups: list[str]) -> list[str]:
    """Keep only groups whose columns exist in this dataframe."""
    return [g for g in groups if g in FEATURE_GROUPS and _available(df, FEATURE_GROUPS[g])]


def feature_columns(groups: list[str]) -> list[str]:
    cols: list[str] = []
    for g in groups:
        cols.extend(FEATURE_GROUPS.get(g, []))
    # preserve order, drop duplicates
    return list(dict.fromkeys(cols))


def matrix(df: pd.DataFrame, groups: list[str]) -> pd.DataFrame:
    cols = feature_columns(groups)
    if not cols:
        raise ValueError("no feature columns selected")
    return df[cols].copy()


def exposure_quota(months: list[str]) -> dict[str, int]:
    """Exposure-tilted top-500 quota for the publication months present.

    The 9-month curve is for Jan..Sep. For a shorter fold (e.g. Apr..Sep),
    use the corresponding slice and renormalise to 500.
    """
    months = sorted(months)
    full = [f"2025-{m:02d}" for m in range(1, 10)]
    # map by month number, not year
    nums = [int(m.split("-")[1]) for m in months]
    vals = [EXPOSURE_9[n - 1] for n in nums]
    if not vals:
        return {}
    total = sum(vals)
    raw = [v * H500 / total for v in vals]
    quota = [int(np.floor(x)) for x in raw]
    # distribute remainder to the largest fractional parts
    rem = H500 - sum(quota)
    order = np.argsort([-(raw[i] - quota[i]) for i in range(len(raw))])
    for i in order[:rem]:
        quota[i] += 1
    return {m: q for m, q in zip(months, quota)}


def _cap_walk(
    order: np.ndarray,
    assigner: np.ndarray,
    cap: int | None,
    selected: list[int],
    counts: dict,
    limit: int,
) -> None:
    for i in order:
        if len(selected) >= limit:
            return
        a = assigner[i]
        if cap is not None and counts.get(a, 0) >= cap:
            continue
        selected.append(int(i))
        counts[a] = counts.get(a, 0) + 1


def select_top(
    df: pd.DataFrame,
    scores: np.ndarray,
    groups: list[str],
    cap: int | None = 50,
    month_allocation: str = "none",
    flag_quota: int | None = None,
    limit: int = H500,
) -> np.ndarray:
    """Return row indices in final rank order (selected first, then rest)."""
    s = np.asarray(scores, dtype=float)
    cve = df["cve_id"].astype(str).to_numpy()
    ids = pd.factorize(pd.Series(cve), sort=True)[0]
    assigner = df["assigner"].fillna("(missing)").astype(str).to_numpy()
    order = np.lexsort((ids, -s))

    selected: list[int] = []
    counts: dict[str, int] = {}

    if month_allocation == "exposure":
        months = df["published"].dt.to_period("M").astype(str).to_numpy()
        quotas = exposure_quota(list(pd.unique(months)))
        for m in sorted(quotas):
            month_order = order[months[order] == m]
            before = len(selected)
            _cap_walk(month_order, assigner, cap, selected, counts, before + quotas[m])
        # fill any shortfall globally
        if len(selected) < limit:
            _cap_walk(order, assigner, cap, selected, counts, limit)
    else:
        _cap_walk(order, assigner, cap, selected, counts, limit)

    # Optional minimum number of public-exploit-flagged rows.
    if flag_quota is not None and "any_public_exploit" in df.columns:
        flag = df["any_public_exploit"].fillna(0).astype(int).to_numpy()
        selected_set = set(selected)
        have = sum(flag[i] for i in selected)
        if have < flag_quota:
            need = flag_quota - have
            candidates = [i for i in order if i not in selected_set and flag[i] == 1]
            # replace the lowest-ranked selected unflagged rows
            replaceable = [i for i in reversed(selected) if flag[i] == 0]
            for add_i, drop_i in zip(candidates[:need], replaceable[:need]):
                selected[selected.index(drop_i)] = int(add_i)
                selected_set.discard(drop_i)
                selected_set.add(int(add_i))

    rest = [int(i) for i in order if i not in set(selected)]
    return np.asarray(selected + rest, dtype=np.int64)


def hits_from_order(y: np.ndarray, order: np.ndarray, k: int) -> int:
    return int(np.asarray(y, dtype=np.int8)[order[:k]].sum())


def order_metrics(y: np.ndarray, order: np.ndarray) -> dict:
    y = np.asarray(y, dtype=np.int8)
    ranks = np.empty(len(y), dtype=np.int64)
    ranks[order] = np.arange(1, len(y) + 1)
    cum = np.cumsum(y[order])
    need = 0.5 * y.sum()
    return {
        "top500": hits_from_order(y, order, 500),
        "top250": hits_from_order(y, order, 250),
        "top243": hits_from_order(y, order, 243),
        "top161": hits_from_order(y, order, 161),
        "median_rank": float(np.median(ranks[y == 1])),
        "work50": int(np.searchsorted(cum, need, side="left") + 1) if y.sum() else None,
        "n": int(len(y)),
        "positives": int(y.sum()),
    }
