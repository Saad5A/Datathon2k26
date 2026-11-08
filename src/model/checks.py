"""Assert-based checks on the backtest pool. Run: .venv/bin/python src/model/checks.py

Each check recomputes what it tests by a separate path where it can, and perturbs inputs to show that
a feature or label does not move when only out-of-window data changes.
"""
import numpy as np
import pandas as pd

from pool import (ASSIGNER_FEATURES, BEST_FEATURES, FLAGS, LABEL_CAP, LEAKY_COLUMNS, SIGNAL_FEATURES, VECTOR_COLS,
                  assigner_history, data_dir, kev_with_assigner, load_kev, load_pool, load_vulns, make_labels)

SAMPLE_MONTH = "2025-03"


def count_rows(name, col):
    return sum(len(c) for c in pd.read_csv(data_dir() / name, usecols=[col], chunksize=1_000_000))


def check_row_counts(pool):
    # Documented in IBM/DATA_DICTIONARY.md and docs/kb/01_data_guide.md / 02_findings_first_pass.md.
    assert len(load_kev()) == 1484
    assert count_rows("scoreboard_2026.csv", "cve_id") == 72670
    assert count_rows("vulnerabilities.csv", "cve_id") == 401082
    assert count_rows("exploit_signals_2024.csv", "cve_id") + count_rows("exploit_signals_2025.csv", "cve_id") == 6463734
    tr, te = pool[pool.ym < "2025-01"], pool[pool.ym >= "2025-01"]
    assert (len(pool), pool.y.sum()) == (75148, 117)
    assert (len(tr), tr.y.sum()) == (39868, 65)
    assert (len(te), te.y.sum()) == (35280, 52)
    assert pool.ym.min() == "2024-01" and pool.ym.max() == "2025-09"


def check_split(pool):
    tr, te = pool[pool.ym < "2025-01"], pool[pool.ym >= "2025-01"]
    assert pool.cve_id.is_unique
    assert not set(tr.cve_id) & set(te.cve_id)
    # Snapshot = publish month for every row.
    assert (pool.ym == pool.published.dt.strftime("%Y-%m")).all()


def check_labels(pool):
    # Nobody already on KEV at the snapshot is in the pool.
    assert (pool.in_kev.fillna(0) == 0).all()
    assert not (pool.date_added.notna() & (pool.date_added <= pool.snap_end)).any()
    # Independent recompute with numpy dates: positive iff added in (snapshot end, min(end + 365 d, cap)].
    end = pool.snap_end.to_numpy().astype("datetime64[D]")
    added = pool.date_added.to_numpy().astype("datetime64[D]")  # NaT compares False
    limit = np.minimum(end + np.timedelta64(365, "D"), np.datetime64(LABEL_CAP))
    assert (pool.y.to_numpy() == ((added > end) & (added <= limit)).astype(int)).all()

    te = pool[pool.ym >= "2025-01"]
    y = make_labels(te.date_added, te.snap_end).to_numpy()
    assert (y == te.y.to_numpy()).all()
    # A row's label uses only its own date: shuffling the other rows changes nothing.
    perm = np.random.default_rng(0).permutation(len(te))
    shuffled = make_labels(te.date_added.iloc[perm], te.snap_end.iloc[perm]).to_numpy()
    assert (shuffled == y[perm]).all()
    # Moving any date to after the row's window (e.g. a 2026 KEV addition) cannot make it positive...
    lim = te.snap_end + pd.Timedelta(days=365)
    late = pd.Series(np.minimum(lim, pd.Timestamp(LABEL_CAP)) + pd.Timedelta(days=1), index=te.index)
    assert make_labels(late, te.snap_end).sum() == 0
    assert make_labels(pd.Series(pd.Timestamp("2026-03-01"), index=te.index), te.snap_end).sum() == 0
    # ...and the check has power: the same dates moved inside the window are all positive.
    inside = te.snap_end + pd.Timedelta(days=1)
    assert make_labels(inside, te.snap_end).sum() == len(te)


def check_assigner_history(pool):
    v = load_vulns(cols=["cve_id", "published", "assigner"])
    kv = kev_with_assigner(load_kev(), v)
    start = pd.Timestamp(SAMPLE_MONTH + "-01")
    rate, kc = assigner_history(kv, v, SAMPLE_MONTH)
    same = lambda a, b: a.sort_index().equals(b.sort_index())
    later = kv.date_added >= start
    assert later.sum() > 0
    # Dropping, or moving further into the future, every KEV row dated on/after the month start changes nothing.
    for alt in (kv[~later], kv.assign(date_added=kv.date_added.where(~later, kv.date_added + pd.Timedelta(days=30)))):
        r2, k2 = assigner_history(alt, v, SAMPLE_MONTH)
        assert same(r2, rate) and same(k2, kc)
    # CVEs published on/after the month start do not enter the denominator either.
    r2, k2 = assigner_history(kv, v[v.published < start], SAMPLE_MONTH)
    assert same(r2, rate) and same(k2, kc)
    # Power: pulling one later KEV row to before the month start does change its assigner's count.
    row = kv[later].index[0]
    moved = kv.copy()
    moved.loc[row, "date_added"] = start - pd.Timedelta(days=1)
    _, k3 = assigner_history(moved, v, SAMPLE_MONTH)
    a = kv.loc[row, "assigner"]
    assert k3[a] == kc.get(a, 0) + 1
    # The pool stores exactly the history computed from data before the month start.
    p = pool[pool.ym == SAMPLE_MONTH]
    r4, k4 = assigner_history(kv[kv.date_added < start], v[v.published < start], SAMPLE_MONTH)
    assert np.allclose(p.asg_rate, [r4.get(a, 0) for a in p.assigner])
    assert (p.asg_kev.to_numpy() == [k4.get(a, 0) for a in p.assigner]).all()


def check_signals_as_of(pool):
    """Pool signals for SAMPLE_MONTH rows equal that month's row in the raw file, not a later month's."""
    p = pool[pool.ym == SAMPLE_MONTH].set_index("cve_id")
    raw = pd.concat(c[c.cve_id.isin(p.index)] for c in
                    pd.read_csv(data_dir() / "exploit_signals_2025.csv", chunksize=500_000, dtype={"cve_id": str}))
    month = raw[raw.month == SAMPLE_MONTH].set_index("cve_id")
    assert month.index.is_unique
    exp_epss = month.epss.reindex(p.index).fillna(-1)
    assert np.allclose(p.epss_f, exp_epss)
    for f in FLAGS:
        assert (p[f] == month[f].reindex(p.index).fillna(0)).all()
    # Power: a later month's values differ for some of these CVEs, so the comparison above can fail.
    after = raw[raw.month == "2025-09"].set_index("cve_id").epss.reindex(p.index).fillna(-1)
    assert (after != exp_epss).sum() > 100


def check_feature_lists():
    structured = {"cvss3", "cwe1", *[c + "_c" for c in VECTOR_COLS]}
    for name in BEST_FEATURES:
        assert name not in LEAKY_COLUMNS, name
        assert name not in structured and not name.startswith("cwe_"), name
    assert set(SIGNAL_FEATURES) | set(ASSIGNER_FEATURES) | {"txt"} == set(BEST_FEATURES)


def check_assigner_window():
    """24-month assigner window (Phase 3, candidates.py): only KEV rows in [start - 24 months, start) count."""
    from candidates import assigner_window
    v = load_vulns(cols=["cve_id", "published", "assigner"])
    kv = kev_with_assigner(load_kev(), v)
    start = pd.Timestamp(SAMPLE_MONTH + "-01")
    lo = start - pd.DateOffset(months=24)
    rate, kc = assigner_window(kv, v, SAMPLE_MONTH)
    same = lambda a, b: a.sort_index().equals(b.sort_index())
    later, earlier = kv.date_added >= start, kv.date_added < lo
    assert later.sum() > 0 and earlier.sum() > 0
    # Dropping or moving later KEV rows, dropping KEV rows before the window, or later CVEs: no change.
    for alt_kv, alt_v in ((kv[~later], v), (kv.assign(date_added=kv.date_added.where(~later, kv.date_added + pd.Timedelta(days=30))), v),
                          (kv[~earlier], v), (kv, v[v.published < start])):
        r2, k2 = assigner_window(alt_kv, alt_v, SAMPLE_MONTH)
        assert same(r2, rate) and same(k2, kc)
    # Independent recompute for the largest assigners by a plain loop.
    for a in kc.sort_values().index[-3:]:
        n_kev = sum(1 for d, x in zip(kv.date_added, kv.assigner) if x == a and lo <= d < start)
        n_pub = sum(1 for d, x in zip(v.published, v.assigner) if x == a and lo <= d < start)
        assert kc[a] == n_kev and abs(rate[a] - n_kev / (n_pub + 20)) < 1e-12
    # Power: pulling one later row to just before the month start raises its assigner's count by one.
    row = kv[later].index[0]
    moved = kv.copy()
    moved.loc[row, "date_added"] = start - pd.Timedelta(days=1)
    a = kv.loc[row, "assigner"]
    assert assigner_window(moved, v, SAMPLE_MONTH)[1][a] == kc.get(a, 0) + 1


if __name__ == "__main__":
    pool = load_pool()
    for check in (check_row_counts, check_split, check_labels, check_assigner_history, check_signals_as_of):
        check(pool)
        print("OK", check.__name__)
    check_feature_lists()
    print("OK check_feature_lists")
    check_assigner_window()
    print("OK check_assigner_window")
    print("all checks passed")
