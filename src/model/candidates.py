"""Phase 3: the pre-registered candidates (LOG.md "PRE-REGISTRATION, Phase 3"), applied literally.

Run: .venv/bin/python src/model/candidates.py
Writes results/model_candidates.json, results/model_candidates.meta.json, merges p3.* into results/claims_model.json.

Two folds with time-safe train labels; C1/C2/C3 over 5 seed sets; the selection rule in `select`; then, for
the selected candidate only: ablations, unseen-assigner subset, label permutation, paired bootstrap.
Seed set s = text-fold seed s and HGB random_state s (one fit). With early_stopping=False and < 200k rows,
HGB does not use its random_state, so seed spread comes from the text folds.
"""
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
import pyarrow
import scipy
import sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

import metrics as M
import reproduce_first_pass as R
from pool import (ASSIGNER_FEATURES, ROOT, SIGNAL_FEATURES, VECTOR_COLS, kev_with_assigner, load_kev, load_pool,
                  load_vulns, make_labels)

SCRIPT_REL = "src/model/candidates.py"
OUT_REL = "results/model_candidates.json"
RESULTS = ROOT / "results"
FOLDS = {"fold1": {"train": ("2024-01", "2024-12"), "label_cap": "2024-12-31", "test": ("2025-01", "2025-09")},
         "fold2": {"train": ("2024-07", "2025-03"), "label_cap": "2025-03-31", "test": ("2025-04", "2025-09")}}
SEEDS = range(5)
N_BOOT, BOOT_SEED, N_PERM = 2000, 0, 20
WINDOW_MONTHS = 24
ASG24 = ["asg24_rate", "asg24_kev"]
CANDIDATES = {"C1": ("hgb", SIGNAL_FEATURES + ASSIGNER_FEATURES + ["txt"]),
              "C2": ("hgb", SIGNAL_FEATURES + ASG24 + ["txt"]),
              "C3": ("lr", SIGNAL_FEATURES + ASG24 + ["txt"])}
PREFERENCE = ["C3", "C2", "C1"]  # tie-break order inside 0.01 of the best mean AUC
TIE_MARGIN = 0.01
TOO_GOOD_AUC = 0.93
D1 = ("Deviation D1: the 24-month window counts only KEV additions whose CVE was published 2021 or later (assigner is "
      "joined from vulnerabilities.csv rows published 2021+, as in the harness all-history feature); older KEV CVEs "
      "added inside the window are not counted. Did not affect the selection (C1 uses the all-history feature).")
PLUS_STRUCTURED_WARNING = ("Uses excluded blank-score fields (cvss3 missing indicator, blank CVSS vector category): "
                           "comparison only, never adoptable as a model")
BASELINES = ["exploit_then_epss", "epss", "cvss3"]


# ---------- features ----------

def assigner_window(kv, v, month, months=WINDOW_MONTHS):
    """Per assigner: KEV rows added in [start - months, start) and rate = that count / (CVEs published in the
    same window + 20). start = first day of `month`. Only rows dated before `start` can enter."""
    start = pd.Timestamp(month + "-01")
    lo = start - pd.DateOffset(months=months)
    kw = kv[(kv.date_added >= lo) & (kv.date_added < start)]
    vw = v[(v.published >= lo) & (v.published < start)]
    assert kw.empty or kw.date_added.max() < start, "KEV row dated on/after the snapshot month start"
    assert vw.empty or vw.published.max() < start
    kev_count = kw.groupby("assigner").size()
    pub = vw.groupby("assigner").size()
    idx = kev_count.index.union(pub.index)
    rate = kev_count.reindex(idx, fill_value=0) / (pub.reindex(idx, fill_value=0) + 20)
    return rate, kev_count


def add_window_features(pool):
    v = load_vulns(cols=["cve_id", "published", "assigner"])
    kv = kev_with_assigner(load_kev(), v)
    hist = {m: assigner_window(kv, v, m) for m in sorted(pool.ym.unique())}
    pool["asg24_rate"] = [hist[m][0].get(a, 0.0) for m, a in zip(pool.ym, pool.assigner)]
    pool["asg24_kev"] = [int(hist[m][1].get(a, 0)) for m, a in zip(pool.ym, pool.assigner)]
    return pool


def masked(df):
    return df.assign(description=df.description.fillna("").str.replace(R.EXPLOIT_WORDING, " ", case=False, regex=True))


def structured(tr, te):
    """CVSS3 score (blank -> 0 + indicator), one-hot CVSS vector fields and top-40 first CWE, vocabularies from train."""
    enc = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    enc.fit(tr[VECTOR_COLS].fillna("blank").astype(str))
    cwes = list(tr.cwe1.value_counts().head(40).index)

    def build(df):
        oh = pd.DataFrame(enc.transform(df[VECTOR_COLS].fillna("blank").astype(str)),
                          columns=[f"s_{c}" for c in enc.get_feature_names_out()], index=df.index)
        cw = pd.DataFrame({f"s_cwe_{c}": (df.cwe1 == c).astype(int) for c in cwes}, index=df.index)
        return pd.concat([df.cvss3_score.fillna(0).rename("s_cvss3"), df.cvss3_score.isna().astype(int).rename("s_cvss3_missing"),
                          oh, cw], axis=1)
    return build(tr), build(te)


def frame(df, cols, txt, kind, extra=None):
    X = df.assign(txt=txt)[cols] if "txt" in cols else df[cols]
    if kind == "lr" and "epss_f" in cols:  # blank EPSS = 0 plus a missing indicator
        X = X.drop(columns="epss_f").assign(epss0=df.epss.fillna(0), epss_missing=df.epss.isna().astype(int))
    return X if extra is None else pd.concat([X, extra], axis=1)


def fit_score(kind, Xtr, y, Xte, seed, early_stopping=False):
    if kind == "hgb":
        return R.hgb_mean(Xtr, y, Xte, seeds=(seed,), early_stopping=early_stopping)[0]
    m = make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000)).fit(Xtr, y)
    return m.predict_proba(Xte)[:, 1]


# ---------- evaluation ----------

def report(y, s, ids):
    d = M.summary(np.asarray(y), s, ids)
    t = M.topk_tie_aware(np.asarray(y), s, 500)
    d.update(top500_best=t["best"], top500_worst=t["worst"], top500_tied_group=t["tied_group_size"])
    return d


def over_seeds(runs):
    keys = runs[0].keys()
    return {"median": {k: float(np.median([r[k] for r in runs])) for k in keys},
            "min": {k: min(r[k] for r in runs) for k in keys}, "max": {k: max(r[k] for r in runs) for k in keys},
            "per_seed": runs}


def paired_bootstrap(y, a, b, n=N_BOOT, seed=BOOT_SEED):
    """Resample rows (same resamples for a and b); differences a - b of AUC and tie-aware expected top-500."""
    y, a, b = np.asarray(y), np.asarray(a, float), np.asarray(b, float)
    rng = np.random.default_rng(seed)
    d_auc, d_top = [], []
    while len(d_auc) < n:
        i = rng.integers(0, len(y), len(y))
        if y[i].sum() == 0:
            continue
        d_auc.append(M.auc(y[i], a[i]) - M.auc(y[i], b[i]))
        d_top.append(M.topk_tie_aware(y[i], a[i], 500)["expected"] - M.topk_tie_aware(y[i], b[i], 500)["expected"])
    out = {}
    for name, d, point in (("auc", d_auc, M.auc(y, a) - M.auc(y, b)),
                           ("top500_expected", d_top, M.topk_tie_aware(y, a, 500)["expected"] - M.topk_tie_aware(y, b, 500)["expected"])):
        d = np.array(d)
        out[name] = {"diff": float(point), "ci95": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))],
                     "share_resamples_diff_gt_0": float((d > 0).mean()), "share_resamples_diff_lt_0": float((d < 0).mean())}
    return out


def select(mean_auc):
    best = max(mean_auc.values())
    eligible = [c for c in PREFERENCE if mean_auc[c] >= best - TIE_MARGIN]
    return eligible[0], best, eligible


# ---------- folds ----------

def fold_data(pool, kev, spec):
    tr = pool[(pool.ym >= spec["train"][0]) & (pool.ym <= spec["train"][1])].copy()
    te = pool[(pool.ym >= spec["test"][0]) & (pool.ym <= spec["test"][1])].copy()
    # Time-safe train labels recomputed from the KEV file, window also capped at the train end.
    da = tr[["cve_id"]].merge(kev, on="cve_id", how="left").date_added.to_numpy()
    assert (pd.isna(da) == tr.date_added.isna().to_numpy()).all() and (da[~pd.isna(da)] == tr.date_added.dropna().to_numpy()).all()
    y_tr = make_labels(pd.Series(da, index=tr.index), tr.snap_end, cap=spec["label_cap"]).to_numpy()
    return tr, te, y_tr


class Fold:
    """Text vectors and scores cached per (masked, seed, labels)."""

    def __init__(self, name, tr, te, y_tr):
        self.name, self.tr, self.te, self.y_tr = name, tr, te, y_tr
        self.y_te, self.ids = te.y.to_numpy(), R.id_codes(te)
        self.vec = {m: R.text_vectors(masked(tr) if m else tr, masked(te) if m else te) for m in (True, False)}
        self.cache = {}

    def text(self, seed, mask=True, y=None):
        key = (seed, mask, None if y is None else y.tobytes())
        if key not in self.cache:
            y = self.y_tr if y is None else y
            Xtr, Xte = self.vec[mask]
            self.cache[key] = (R.text_oof(Xtr, y, fold_seed=seed), R.text_test_score(Xtr, y, Xte))
        return self.cache[key]

    def score(self, kind, cols, seed, mask=True, extra=(None, None), early_stopping=False, y=None):
        oof, st = self.text(seed, mask, y) if "txt" in cols else (None, None)
        Xtr, Xte = frame(self.tr, cols, oof, kind, extra[0]), frame(self.te, cols, st, kind, extra[1])
        return fit_score(kind, Xtr, self.y_tr if y is None else y, Xte, seed, early_stopping)

    def run(self, kind, cols, **kw):
        scores = [self.score(kind, cols, s, **kw) for s in SEEDS]
        return over_seeds([report(self.y_te, s, self.ids) for s in scores]), scores


def median_tree(rows):
    """Element-wise median over seed sets of equally shaped dicts / lists of numbers; strings and None pass through."""
    a = rows[0]
    if isinstance(a, dict):
        return {k: median_tree([r[k] for r in rows]) for k in a}
    if isinstance(a, list):
        return [median_tree([r[i] for r in rows]) for i in range(len(a))]
    if a is None or isinstance(a, str) or any(r is None for r in rows):
        return a
    return float(np.median(rows))


def per_seed(rows):
    return {"seed_median": median_tree(rows), "seed_set_0": rows[0], "per_seed": rows}


def add_ci(entries, folds, seed0):
    """Bootstrap CI on the seed-0 score vector of every entry, same resamples within a fold."""
    jobs = [(f, n) for f in entries for n in entries[f]]
    cis = joblib.Parallel(n_jobs=-1)(joblib.delayed(M.bootstrap_ci)(folds[f].y_te, seed0[f][n], folds[f].ids, N_BOOT, BOOT_SEED)
                                     for f, n in jobs)
    for (f, n), ci in zip(jobs, cis):
        entries[f][n]["ci95_seed0"] = ci


def unseen_assigner(fold, s, base):
    te, y = fold.te, fold.y_te
    m = (te.asg_kev == 0).to_numpy()
    top = M.ranks_by_id(s, fold.ids) <= 500
    top_b = M.ranks_by_id(base, fold.ids) <= 500
    both = y[m].sum() > 0 and (y[m] == 0).sum() > 0
    return {"definition": "test rows whose assigner had 0 KEV rows (with assigner, CVE published 2021+) before the snapshot month (asg_kev == 0)",
            "rows": int(m.sum()), "positives": int(y[m].sum()),
            "auc_within_subset": M.auc(y[m], s[m]) if both else None,
            "top500_rows_from_subset": int((top & m).sum()), "top500_hits_from_subset": int((top & m & (y == 1)).sum()),
            "exploit_then_epss_top500_rows_from_subset": int((top_b & m).sum()),
            "exploit_then_epss_top500_hits_from_subset": int((top_b & m & (y == 1)).sum())}


def permutation(fold, kind, cols):
    aucs = []
    for i in range(N_PERM):
        yp = np.random.default_rng(i).permutation(fold.y_tr)
        aucs.append(M.auc(fold.y_te, fold.score(kind, cols, 0, y=yp)))
        fold.cache.clear()
    return {"n_shuffles": N_PERM, "shuffle_seeds": list(range(N_PERM)), "model_seed_set": 0, "aucs": aucs,
            "mean": float(np.mean(aucs)), "sd": float(np.std(aucs, ddof=1)), "max": float(max(aucs)), "min": float(min(aucs))}


# ---------- claims, meta ----------

CLAIM_KEYS = [("top500_cve_id", "count"), ("top500_expected", "count"), ("top500_best", "count"), ("top500_worst", "count"),
              ("top250_cve_id", "count"), ("auc", "fraction"), ("avg_precision", "fraction"),
              ("median_rank_cve_id", "count"), ("work50_cve_id", "count")]
CI_KEYS = [("top500_expected", "count"), ("top250_expected", "count"), ("auc", "fraction"), ("avg_precision", "fraction"),
           ("median_rank_mid", "count"), ("work50_mid", "count")]


def claims_from(res):
    c = {}

    def add(key, text, value, unit):
        c["p3." + key] = {"text": text, "value": value, "unit": unit, "source_script": SCRIPT_REL, "output_file": OUT_REL,
                          "status": "unverified", "verified_by": None}

    for f, fr in res["folds"].items():
        where = f"Phase 3 {f} (train {fr['train_months']}, labels to {fr['train_label_cap']}; test {fr['test_months']})"
        for k in ("train_rows", "train_positives", "test_rows", "test_positives"):
            add(f"{f}.{k}", f"{where}: {k.replace('_', ' ')}", fr[k], "count")
        for group in ("baselines", "candidates", "ablations"):
            for n, e in res[group][f].items():
                if "median" not in e:
                    continue
                lab = f"{where}, {group[:-1]} {n}"
                if n == "plus_structured":
                    lab += f" [{PLUS_STRUCTURED_WARNING}]"
                if group == "baselines":
                    for k, u in CLAIM_KEYS:
                        add(f"{f}.{n}.{k}.median", f"{lab}: {k} (deterministic baseline, no seed)", e["median"][k], u)
                    for k, u in CI_KEYS:
                        add(f"{f}.{n}.ci95_lo.{k}", f"{lab}: bootstrap 95% CI lower bound, {k} (deterministic baseline)", e["ci95_seed0"][k][0], u)
                        add(f"{f}.{n}.ci95_hi.{k}", f"{lab}: bootstrap 95% CI upper bound, {k} (deterministic baseline)", e["ci95_seed0"][k][1], u)
                    continue
                for k, u in CLAIM_KEYS:
                    add(f"{f}.{n}.{k}.median", f"{lab}: {k}, median over seed sets 0-4", e["median"][k], u)
                for k, u in (("top500_cve_id", "count"), ("auc", "fraction")):
                    add(f"{f}.{n}.{k}.min", f"{lab}: {k}, lowest of seed sets 0-4", e["min"][k], u)
                    add(f"{f}.{n}.{k}.max", f"{lab}: {k}, highest of seed sets 0-4", e["max"][k], u)
                for k, u in CI_KEYS:
                    add(f"{f}.{n}.ci95_lo.{k}", f"{lab}: bootstrap 95% CI lower bound, {k} (seed set 0)", e["ci95_seed0"][k][0], u)
                    add(f"{f}.{n}.ci95_hi.{k}", f"{lab}: bootstrap 95% CI upper bound, {k} (seed set 0)", e["ci95_seed0"][k][1], u)
        for which, tag, sfx in (("seed_median", "median over seed sets 0-4", ""), ("seed_set_0", "seed set 0", ".seed0")):
            u = res["unseen_assigner"][f][which]
            for k in ("rows", "positives", "top500_rows_from_subset", "top500_hits_from_subset"):
                add(f"{f}.unseen_assigner.{k}{sfx}", f"{where}, selected model ({tag}), unseen-assigner test rows: {k.replace('_', ' ')}", u[k], "count")
            if u["auc_within_subset"] is not None:
                add(f"{f}.unseen_assigner.auc{sfx}", f"{where}, selected model ({tag}): AUC within unseen-assigner test rows", u["auc_within_subset"], "fraction")
            b = res["paired_bootstrap_vs_exploit_then_epss"][f][which]
            for k, unit in (("auc", "fraction"), ("top500_expected", "count")):
                add(f"{f}.paired.{k}.diff{sfx}", f"{where}: selected ({tag}) minus exploit-then-EPSS, {k}", b[k]["diff"], unit)
                add(f"{f}.paired.{k}.ci95_lo{sfx}", f"{where}: paired bootstrap 95% CI lower bound, selected ({tag}) minus exploit-then-EPSS, {k}", b[k]["ci95"][0], unit)
                add(f"{f}.paired.{k}.ci95_hi{sfx}", f"{where}: paired bootstrap 95% CI upper bound, selected ({tag}) minus exploit-then-EPSS, {k}", b[k]["ci95"][1], unit)
        p = res["permutation"][f]
        for k in ("mean", "sd", "max"):
            add(f"{f}.permutation.auc_{k}", f"{where}, selected model (seed set 0), {N_PERM} train-label shuffles: test AUC {k}", p[k], "fraction")
    for cnd, v in res["selection"]["mean_auc_over_folds"].items():
        add(f"selection.{cnd}.mean_auc", f"Phase 3 {cnd}: mean over the two folds of the seed-median AUC", v, "fraction")
    return c


def merge_claims(new, prefix="p3."):
    """Only `prefix` entries are written; stale ones are dropped; status kept only if value and text are unchanged."""
    path = RESULTS / "claims_model.json"
    old = json.loads(path.read_text()) if path.exists() else {}
    old = {k: v for k, v in old.items() if not k.startswith(prefix) or k in new}
    for key, claim in new.items():
        assert key.startswith(prefix), key
        prev = old.get(key)
        if (prev and prev["text"] == claim["text"]
                and math.isclose(prev["value"], claim["value"], rel_tol=1e-9, abs_tol=1e-12)):
            claim["status"], claim["verified_by"] = prev["status"], prev["verified_by"]
    old.update(new)
    path.write_text(json.dumps(old, indent=2) + "\n")
    return len(new)


def write_meta(script=SCRIPT_REL, out="model_candidates.meta.json"):
    """git_dirty: any change, tracked or untracked, under src/model/ (the code). Output files under results/ are
    rewritten by the run itself and are not counted."""
    git = lambda *a: subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.rstrip("\n")
    changed = git("status", "--porcelain", "--", "src/model").splitlines()
    meta = {"script": script, "git_commit": git("rev-parse", "HEAD"), "git_dirty": bool(changed),
            "git_dirty_files": changed,
            "code_sha256": {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted((ROOT / "src" / "model").glob("*.py"))},
            "date_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "python": platform.python_version(),
            "machine": platform.machine(),
            "libraries": {"pandas": pd.__version__, "numpy": np.__version__, "scikit-learn": sklearn.__version__,
                          "scipy": scipy.__version__, "pyarrow": pyarrow.__version__, "joblib": joblib.__version__}}
    (RESULTS / out).write_text(json.dumps(meta, indent=2) + "\n")


# ---------- main ----------

def main():
    t0 = time.time()
    tick = lambda msg: print(f"[{time.time() - t0:5.0f}s] {msg}", flush=True)
    pool = add_window_features(load_pool())
    kev = load_kev()
    folds, res = {}, {"folds": {}, "baselines": {}, "candidates": {}, "ablations": {}}
    seed0, all_scores = {}, {f: {} for f in FOLDS}
    for f, spec in FOLDS.items():
        tr, te, y_tr = fold_data(pool, kev, spec)
        folds[f] = Fold(f, tr, te, y_tr)
        res["folds"][f] = {"train_months": "..".join(spec["train"]), "train_label_cap": spec["label_cap"],
                           "test_months": "..".join(spec["test"]), "train_rows": len(tr), "train_positives": int(y_tr.sum()),
                           "train_positives_uncapped_pool_label": int(tr.y.sum()), "test_rows": len(te),
                           "test_positives": int(te.y.sum())}
        base = R.baselines(te)
        res["baselines"][f] = {n: over_seeds([report(folds[f].y_te, base[n], folds[f].ids)]) for n in BASELINES}
        seed0[f] = {n: base[n] for n in BASELINES}
        res["candidates"][f] = {}
        for c, (kind, cols) in CANDIDATES.items():
            res["candidates"][f][c], all_scores[f][c] = folds[f].run(kind, cols)
            seed0[f][c] = all_scores[f][c][0]
            tick(f"{f} {c}: AUC median {res['candidates'][f][c]['median']['auc']:.4f}")

    too_good = {f"{f}.{c}": e["max"]["auc"] for f in res["candidates"] for c, e in res["candidates"][f].items()
                if e["max"]["auc"] > TOO_GOOD_AUC}
    if too_good:
        sys.exit(f"STOP: AUC above {TOO_GOOD_AUC} {too_good}; investigate leakage before going on")

    mean_auc = {c: float(np.mean([res["candidates"][f][c]["median"]["auc"] for f in FOLDS])) for c in CANDIDATES}
    chosen, best, eligible = select(mean_auc)
    res["selection"] = {"rule": "highest mean over the two folds of the seed-median AUC; within 0.01 of the best prefer C3, C2, C1",
                        "mean_auc_over_folds": mean_auc, "best_mean_auc": best, "eligible_within_margin": eligible,
                        "selected": chosen}
    tick(f"selected {chosen} (mean AUC {mean_auc}, eligible {eligible})")

    kind, cols = CANDIDATES[chosen]
    ablations = {"drop_signals": dict(cols=[c for c in cols if c not in SIGNAL_FEATURES]),
                 "drop_assigner": dict(cols=[c for c in cols if c not in ASSIGNER_FEATURES + ASG24]),
                 "drop_text": dict(cols=[c for c in cols if c != "txt"]),
                 "unmasked_text": dict(cols=cols, mask=False),
                 "plus_structured": dict(cols=cols, structured=True),
                 "early_stopping_on": dict(cols=cols, early_stopping=True)}
    res["unseen_assigner"], res["permutation"], res["paired_bootstrap_vs_exploit_then_epss"] = {}, {}, {}
    for f, fold in folds.items():
        res["ablations"][f] = {}
        for n, a in ablations.items():
            if n == "early_stopping_on" and kind != "hgb":
                res["ablations"][f][n] = {"not_applicable": "selected model is a logistic regression; no early stopping"}
                continue
            extra = structured(fold.tr, fold.te) if a.get("structured") else (None, None)
            res["ablations"][f][n], sc = fold.run(kind, a["cols"], mask=a.get("mask", True), extra=extra,
                                                           early_stopping=a.get("early_stopping", False))
            seed0[f][n] = sc[0]
            if n == "plus_structured":
                res["ablations"][f][n]["excluded_field_warning"] = PLUS_STRUCTURED_WARNING
            res["ablations"][f][n]["features"] = list(a["cols"]) + (list(extra[0].columns) if extra[0] is not None else [])
            tick(f"{f} ablation {n}: AUC median {res['ablations'][f][n]['median']['auc']:.4f}")
        base = seed0[f]["exploit_then_epss"]
        res["unseen_assigner"][f] = per_seed([unseen_assigner(fold, s, base) for s in all_scores[f][chosen]])
        res["paired_bootstrap_vs_exploit_then_epss"][f] = per_seed(joblib.Parallel(n_jobs=-1)(
            joblib.delayed(paired_bootstrap)(fold.y_te, s, base) for s in all_scores[f][chosen]))
        tick(f"{f} unseen + paired bootstrap done")
        res["permutation"][f] = permutation(fold, kind, cols)
        tick(f"{f} permutation AUC mean {res['permutation'][f]['mean']:.4f} max {res['permutation'][f]['max']:.4f}")

    for g in ("baselines", "candidates", "ablations"):
        add_ci({f: {n: e for n, e in res[g][f].items() if "median" in e} for f in FOLDS}, folds, seed0)
    tick("bootstrap CIs done")
    res["deviations"] = {"D1": D1}
    res["notes"] = {
        "seed_sets": "seed set s: text OOF folds seed s, HGB random_state s (single fit, early_stopping=False). Baselines are deterministic (one 'seed').",
        "ci95_seed0": f"percentile bootstrap, {N_BOOT} resamples, seed {BOOT_SEED}, on the seed-set-0 scores; same resamples for every model in a fold",
        "paired_bootstrap": "selected model minus exploit-then-EPSS, run once per seed set (same resamples for every run); seed_median is the element-wise median over the 5 runs (each number its own median), seed_set_0 kept for reference",
        "unseen_assigner": "computed per seed set; seed_median is the element-wise median, seed_set_0 kept for reference",
        "permutation": "model seed set 0 for every shuffle",
        "c3": "StandardScaler + sklearn LogisticRegression defaults (L2, C=1.0, no class weight), max_iter=5000; epss_f replaced by epss0 (blank=0) + epss_missing",
        "asg24": "KEV rows (CVE published 2021+, as in the all-history feature) added in [month start - 24 months, month start); rate = count / (CVEs published in the same window + 20); assigners with KEV rows but no CVE published in the window get count / 20",
        "plus_structured": "cvss3 score (blank 0 + indicator), one-hot of the 8 CVSS vector fields and top-40 first CWE, vocabularies fitted on train rows only",
        "masking": "harness EXPLOIT_WORDING replaced by a space (case-insensitive) in train and test descriptions before TF-IDF"}
    RESULTS.mkdir(exist_ok=True)
    (ROOT / OUT_REL).write_text(json.dumps(res, indent=2, default=lambda x: x.item()) + "\n")
    write_meta()
    tick(f"wrote {OUT_REL} and {merge_claims(claims_from(res))} p3 claims")


if __name__ == "__main__":
    main()
