"""Phase 7: the final 2026 files (LOG.md "PRE-REGISTRATION (before any final 2026 file is written ...)").

Run: .venv/bin/python src/model/final.py
Writes results/scores_2026.csv, results/top500.csv, results/signal_vocabulary.json, results/scores_2026.meta.json,
results/claims_model_final.json (p7.*). Contract: docs/INTERFACES.md section 1.

Score = mean of C1 over the 5 pre-registered seed sets, C1 refitted on every labelled pool row (labels: KEV to
2025-12-31). Rows are built by cap.score_2026 (the audited preview path). Ranks 1-500 are the k=50 per-assigner capped
list; the rest follow by score; ties by cve_id. `score` is a ranking score, not a probability. No 2026 labels exist.
Reasons: occlusion. Each signal group is set to a neutral value (training-set median; flags 0), the seed-averaged
score is recomputed, and the up to 3 groups with the largest absolute change are listed.
"""
import argparse
import json
import math
import time

import numpy as np
import pandas as pd

import candidates as C
import cap
import reproduce_first_pass as R
from pool import FLAGS, ROOT, data_dir, load_pool

SCRIPT_REL = "src/model/final.py"
RESULTS = ROOT / "results"
K = 50
TOP = 500
TIERS = ((100, "P0"), (500, "P1"))
COLUMNS = ["cve_id", "published", "snapshot_month", "assigner", "score", "rank", "percentile", "in_top500", "priority", "epss",
           "exploitdb", "metasploit", "nuclei", "poc_github", "any_public_exploit", "reasons", "model_version"]
MODEL_VERSION = {"tfidf": "C1", "G1": "G1", "G2": "G2"}  # rank <= limit; everything else P2
ZERO = 1e-9  # a score change at or below this is "essentially 0" (HGB returns exactly the same value)
SIGNALS = {
    "epss": {"label": "EPSS score at the snapshot month",
             "value": "the CVE's EPSS score in its snapshot month (null if EPSS was blank)",
             "cols": ["epss_f"]},
    "public_exploit_code": {"label": "Public exploit code flags",
                            "value": "number of public exploit flags set in the snapshot month (Exploit-DB, Metasploit, Nuclei, GitHub PoC), 0-4",
                            "cols": FLAGS + ["anyx", "nx"]},
    "assigner_kev_history": {"label": "Assigner's KEV history",
                             "value": "share of the assigning organisation's earlier CVEs (published 2021+, before the snapshot month) that were added to KEV before the snapshot month, smoothed: KEV count / (CVE count + 20)",
                             "cols": ["asg_rate", "asg_kev"]},
    "description_text": {"label": "Description text score",
                         "value": "text model score (0-1) from the CVE description with exploitation wording masked; a ranking input, not a probability",
                         "cols": ["txt"]},
}
DIRECTION = {"up": "this signal's actual value raises the CVE's priority score compared with the neutral value",
             "down": "this signal's actual value lowers the CVE's priority score compared with the neutral value"}


def fit_all(pool, sb, text="tfidf", emb=None):
    """Per seed set: C1 on all pool rows, predicted on the actual rows and on one occluded copy per signal group.
    text: "tfidf" (default, C1), "G1" (Granite text score instead of TF-IDF) or "G2" (both, Granite as txt_g)."""
    kind, cols = C.CANDIDATES[cap.MODEL]
    Xtr, Xte = R.text_vectors(C.masked(pool), C.masked(sb))
    st = R.text_test_score(Xtr, pool.y, Xte)
    if text != "tfidf":
        import granite
        E = granite.Embeddings(emb)
        Etr, Ete = E.rows(pool.cve_id), E.rows(sb.cve_id)
        g_st = R.text_test_score(Etr, pool.y, Ete)
        if text == "G2":
            cols = cols + ["txt_g"]
            SIGNALS["description_text"]["cols"] = ["txt", "txt_g"]
    actual, occluded, neutral = [], {g: [] for g in SIGNALS}, []
    for seed in C.SEEDS:
        oof = R.text_oof(Xtr, pool.y, fold_seed=seed)
        if text == "tfidf":
            tr, te = C.frame(pool, cols, oof, kind), C.frame(sb, cols, st, kind)
        else:
            g_oof = R.text_oof(Etr, pool.y.to_numpy(), fold_seed=seed)
            if text == "G1":
                tr, te = C.frame(pool, cols, g_oof, kind), C.frame(sb, cols, g_st, kind)
            else:
                base = [c for c in cols if c != "txt_g"]
                tr = C.frame(pool, base, oof, kind).assign(txt_g=g_oof)
                te = C.frame(sb, base, st, kind).assign(txt_g=g_st)
        neu = {c: (0.0 if c in FLAGS + ["anyx", "nx"] else float(tr[c].median())) for c in cols}
        copies = [te] + [te.assign(**{c: neu[c] for c in SIGNALS[g]["cols"]}) for g in SIGNALS]
        p = C.fit_score(kind, tr, pool.y, pd.concat(copies, ignore_index=True), seed).reshape(len(copies), len(te))
        actual.append(p[0])
        for i, g in enumerate(SIGNALS, 1):
            occluded[g].append(p[i])
        neutral.append(neu)
    return np.array(actual), {g: np.mean(v, axis=0) for g, v in occluded.items()}, neutral, (g_st if text == "G1" else st)


def rank_rows(score, assigner, ids):
    """Ranks 1..n: capped top 500 in capped order, then the rest by score, ties by cve_id."""
    groups = pd.factorize(assigner)[0]
    top = cap.capped_top(score, groups, K, ids)
    order = np.lexsort((ids, -score))
    rest = order[~np.isin(order, top)]
    rank = np.empty(len(score), dtype=np.int64)
    rank[np.concatenate([top, rest])] = np.arange(1, len(score) + 1)
    return rank


def reasons(sb, delta, st):
    vals = {"epss": [None if pd.isna(e) else round(float(e), 5) for e in sb.epss],
            "public_exploit_code": sb.nx.astype(int).tolist(),
            "assigner_kev_history": [round(float(x), 4) for x in sb.asg_rate],
            "description_text": [round(float(x), 4) for x in st]}
    names = list(SIGNALS)
    D = np.column_stack([delta[g] for g in names])
    total = np.abs(D).sum(axis=1)  # over ALL signal groups, listed or not
    out = []
    for i in range(len(sb)):
        idx = [j for j in np.argsort(-np.abs(D[i]), kind="stable")[:3] if abs(D[i, j]) > ZERO]
        out.append(json.dumps([{"signal": names[j], "value": vals[names[j]][i],
                                "impact": round(float(abs(D[i, j]) / total[i]), 3) if total[i] > 0 else 0.0,
                                "direction": "up" if D[i, j] > 0 else "down"} for j in idx]))
    return out


def validate(scores, top500, sb_raw):
    n = len(sb_raw)
    assert list(scores.columns) == COLUMNS
    assert (scores.percentile == (100 * (1 - (scores["rank"] - 1) / n)).round(1)).all()
    assert all(scores[f].isin([0, 1]).all() for f in FLAGS)
    assert (scores.any_public_exploit == scores[FLAGS].max(axis=1)).all()
    assert scores.model_version.nunique() == 1 and scores.model_version.iloc[0] in MODEL_VERSION.values()
    assert len(scores) == n == 72670 and scores.cve_id.is_unique and set(scores.cve_id) == set(sb_raw.cve_id)
    assert sorted(scores["rank"]) == list(range(1, n + 1))
    assert (scores.in_top500 == (scores["rank"] <= TOP).astype(int)).all()
    exp = np.where(scores["rank"] <= 100, "P0", np.where(scores["rank"] <= TOP, "P1", "P2"))
    assert (scores.priority == exp).all()
    t = scores[scores.in_top500 == 1]
    assert t.assigner.value_counts().max() <= K
    # Inside the top 500 and below it, rank follows score (ties by cve_id).
    for part in (t, scores[scores.in_top500 == 0]):
        p = part.sort_values("rank")
        assert (np.diff(p.score.to_numpy()) <= 0).all()
    # Every row outside the top 500 that scores above the 500th row's... is there only because its assigner was full.
    skipped = scores[(scores.in_top500 == 0) & (scores.score > t.score.min())]
    assert skipped.assigner.isin(t.assigner.value_counts()[lambda c: c == K].index).all()
    for r in scores.reasons:
        lst = json.loads(r)
        assert len(lst) <= 3 and all(x["signal"] in SIGNALS and x["direction"] in ("up", "down") for x in lst)
        assert all(0 <= x["impact"] <= 1 for x in lst) and sum(x["impact"] for x in lst) <= 1.003  # 3 roundings
    # top500.csv: one column, 500 unique ids, all in the scoreboard, equal to ranks 1-500.
    assert list(top500.columns) == ["cve_id"] and len(top500) == TOP and top500.cve_id.is_unique
    assert top500.cve_id.isin(sb_raw.cve_id).all()
    assert top500.cve_id.tolist() == scores.sort_values("rank").cve_id.head(TOP).tolist()


def write_claims(res):
    path = RESULTS / "claims_model_final.json"
    new = {}

    def add(key, text, value, unit):
        new["p7." + key] = {"text": text, "value": value, "unit": unit, "source_script": SCRIPT_REL,
                            "output_file": "results/scores_2026.csv", "status": "unverified", "verified_by": None}

    where = "Final 2026 ranking (C1, mean of seed sets 0-4, k=50 assigner cap)"
    if res.get("text_source", "tfidf") != "tfidf":
        where = where.replace("C1,", f"C1 with Granite text {res['text_source']},")
    add("train_rows", f"{where}: training rows (pool 2024-01..2025-09)", res["train_rows"], "count")
    add("train_positives", f"{where}: training positives (KEV additions to 2025-12-31)", res["train_positives"], "count")
    add("rows_scored", f"{where}: scoreboard rows scored", res["rows_scored"], "count")
    for i, (a, n) in enumerate(res["top10_assigners"], 1):
        add(f"top500.assigner_rank{i}.count", f"{where}: top-500 rows from assigner #{i} by count ({a})", n, "count")
    for k, text in (("share_any_public_exploit", "share of top-500 rows with any public exploit flag"),
                    ("share_epss_gt_0_1", "share of top-500 rows with EPSS > 0.1"),
                    ("share_unseen_assigner", "share of top-500 rows from assigners with no KEV row before the snapshot month")):
        add(f"top500.{k}", f"{where}: {text}", res[k], "fraction")
    for tier, n in res["tier_counts"].items():
        add(f"tier.{tier}.count", f"{where}: rows in priority tier {tier}", n, "count")
    old = json.loads(path.read_text()) if path.exists() else {}
    for key, c in new.items():
        prev = old.get(key)
        if prev and prev["text"] == c["text"] and math.isclose(prev["value"], c["value"], rel_tol=1e-9, abs_tol=1e-12):
            c["status"], c["verified_by"] = prev["status"], prev["verified_by"]
    path.write_text(json.dumps(new, indent=2) + "\n")
    return len(new)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", choices=["tfidf", "G1", "G2"], default="tfidf",
                    help="text score source; G1/G2 only if granite.py's pre-registered rule adopted it")
    ap.add_argument("--emb", default=str(ROOT / "data_cache" / "granite_embeddings.parquet"))
    a = ap.parse_args()
    t0 = time.time()
    tick = lambda msg: print(f"[{time.time() - t0:5.0f}s] {msg}", flush=True)
    pool = load_pool()
    sb, ref = cap.score_2026(pool)  # the preview path, per seed set
    tick("scoreboard rows built (cap.score_2026)")
    actual, occluded, neutral, st = fit_all(pool, sb, a.text, a.emb)
    if a.text == "tfidf":  # the preview path is TF-IDF only
        assert np.array_equal(actual, np.array(ref)), "refit differs from cap.score_2026"
    score = actual.mean(axis=0)
    delta = {g: score - occluded[g] for g in SIGNALS}
    tick("fits and occlusion done")

    ids = R.id_codes(sb)
    rank = rank_rows(score, sb.assigner.to_numpy(), ids)
    priority = np.where(rank <= TIERS[0][0], "P0", np.where(rank <= TIERS[1][0], "P1", "P2"))
    scores = pd.DataFrame({"cve_id": sb.cve_id, "published": sb.published, "snapshot_month": sb.snapshot_month,
                           "assigner": sb.assigner, "score": score, "rank": rank, "in_top500": (rank <= TOP).astype(int),
                           "priority": priority, "epss": sb.epss, "any_public_exploit": sb.anyx.astype(int),
                           "reasons": reasons(sb, delta, st)}).sort_values("rank").reset_index(drop=True)
    # Dashboard contract (docs/INTERFACES_dashboard.md sections 1 and 3): extra columns, nothing above changes.
    flags = sb.set_index("cve_id").loc[scores.cve_id, FLAGS].astype(int).reset_index(drop=True)
    scores = scores.assign(percentile=(100 * (1 - (scores["rank"] - 1) / len(scores))).round(1), **flags,
                           model_version=MODEL_VERSION[a.text])[COLUMNS]
    top500 = scores.loc[scores["rank"] <= TOP, ["cve_id"]]
    sb_raw = pd.read_csv(data_dir() / "scoreboard_2026.csv", usecols=["cve_id"], dtype={"cve_id": str})
    validate(scores, top500, sb_raw)
    scores.to_csv(RESULTS / "scores_2026.csv", index=False)
    top500.to_csv(RESULTS / "top500.csv", index=False)
    # Re-read from disk and validate what was written, not only the in-memory frames.
    validate(pd.read_csv(RESULTS / "scores_2026.csv", dtype={"cve_id": str, "published": str, "snapshot_month": str}),
             pd.read_csv(RESULTS / "top500.csv", dtype={"cve_id": str}), sb_raw)
    tick("scores_2026.csv and top500.csv written and validated")

    med = lambda c: float(np.median([n[c] for n in neutral]))
    neutral_value = {"epss": med("epss_f"), "public_exploit_code": 0,
                     "assigner_kev_history": med("asg_rate"), "description_text": med("txt")}
    vocab = {"_note": ("Reasons come from occlusion: each signal is set to its neutral value and the change in the CVE's "
                       "priority score (mean over 5 seed sets) is measured; the up to 3 largest changes are listed. The score "
                       "ranks CVEs; it is not a probability of exploitation."),
             "_direction": DIRECTION,
             "_impact": ("share of the CVE's total occlusion effect: |score change for this signal| divided by the sum of "
                         "|score change| over all four signals for that CVE, 0-1, rounded to 3 decimals (0 if every change "
                         "is 0). A relative share for this CVE only, not a probability and not comparable across CVEs as "
                         "an absolute size.")}
    for g, s in SIGNALS.items():
        vocab[g] = {"label": s["label"], "value_meaning": s["value"], "direction_meaning": DIRECTION,
                    "neutral_value": neutral_value[g],
                    "neutral_rule": "0 for every flag" if g == "public_exploit_code" else "median over the training rows",
                    "model_columns_set_to_neutral": s["cols"],
                    "neutral_values_per_column_seed_set_0": {c: neutral[0][c] for c in s["cols"]}}
    if a.text != "tfidf":
        vocab["description_text"]["value_meaning"] += (
            " (Granite embedding text model)" if a.text == "G1" else
            " (TF-IDF text model; the Granite text score txt_g is occluded together with it)")
        vocab["_text_source"] = a.text
    (RESULTS / "signal_vocabulary.json").write_text(json.dumps(vocab, indent=2) + "\n")

    t = scores[scores.in_top500 == 1].merge(sb[["cve_id", "asg_kev"]], on="cve_id")
    res = {"train_rows": len(pool), "train_positives": int(pool.y.sum()), "rows_scored": len(scores),
           "top10_assigners": list(t.assigner.value_counts().head(10).items()),
           "share_any_public_exploit": float(t.any_public_exploit.mean()), "share_epss_gt_0_1": float((t.epss > 0.1).mean()),
           "share_unseen_assigner": float((t.asg_kev == 0).mean()),
           "tier_counts": scores.priority.value_counts().sort_index().to_dict()}
    if a.text != "tfidf":
        res["text_source"] = a.text
    C.write_meta(script=SCRIPT_REL, out="scores_2026.meta.json")
    mp = RESULTS / "scores_2026.meta.json"
    meta = json.loads(mp.read_text()) | {"model": cap.MODEL, "seed_sets": list(C.SEEDS), "score": "mean of the 5 seed-set scores",
                                         "assigner_cap_k": K, "tie_break": "cve_id ascending", "train_rows": res["train_rows"],
                                         "train_positives": res["train_positives"], "train_label_cap": "2025-12-31",
                                         "rows_scored": res["rows_scored"], "summary": res}
    if a.text != "tfidf":
        meta |= {"text_source": a.text, "granite_embeddings": a.emb}
    mp.write_text(json.dumps(meta, indent=2, default=lambda x: x.item()) + "\n")
    tick(f"wrote vocabulary, meta and {write_claims(res)} p7 claims")
    print(json.dumps(res, indent=1, default=lambda x: x.item()))


if __name__ == "__main__":
    main()
