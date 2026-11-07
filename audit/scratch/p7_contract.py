"""Phase 7 audit: items 1-3 (submission validity, contract, time safety sample) from raw files. Plain pandas/python."""
import json, csv, numpy as np, pandas as pd
R = "/Users/aahmad/Working/datathon/code/Datathon2k26/"; D = R + ".data/data/"
out = {}
# ---- item 1 ----
with open(R + "results/top500.csv") as f:
    rows = list(csv.reader(f))
out["top500_header"] = rows[0]; ids = [r[0] for r in rows[1:]]
out["top500_ncols_set"] = sorted({len(r) for r in rows})
out["top500_n"], out["top500_unique"] = len(ids), len(set(ids))
sbr = pd.read_csv(D + "scoreboard_2026.csv", dtype=str)
out["top500_in_scoreboard"] = int(pd.Series(ids).isin(sbr.cve_id).sum())
s = pd.read_csv(R + "results/scores_2026.csv", dtype=str, keep_default_na=False)
s["rank_i"] = s["rank"].astype(int)
out["top500_eq_rank1_500"] = ids == s.sort_values("rank_i").cve_id.head(500).tolist()
kev = pd.read_csv(D + "known_exploited.csv", dtype=str)
kd = dict(zip(kev.cve_id, kev.date_added))
sm = dict(zip(sbr.cve_id, sbr.snapshot_month))
# on KEV at snapshot month: added on/before month end
def mend(m):
    y, mo = int(m[:4]), int(m[5:7]); y2, mo2 = (y + 1, 1) if mo == 12 else (y, mo + 1)
    return str(np.datetime64(f"{y2:04d}-{mo2:02d}-01") - np.timedelta64(1, "D"))
out["top500_on_kev_by_snapshot_end"] = sum(1 for c in ids if c in kd and kd[c] <= mend(sm[c]))
out["top500_on_kev_ever"] = sum(1 for c in ids if c in kd)
out["scoreboard_on_kev_ever"] = int(sbr.cve_id.isin(kev.cve_id).sum())
# ---- item 2 ----
exp_cols = ["cve_id", "published", "snapshot_month", "assigner", "score", "rank", "in_top500", "priority", "epss",
            "any_public_exploit", "reasons"]
out["cols_ok"] = list(s.columns[:-1]) == exp_cols
out["n_rows"], out["unique"] = len(s), int(s.cve_id.nunique())
out["set_eq_scoreboard"] = set(s.cve_id) == set(sbr.cve_id)
out["rank_perm"] = sorted(s.rank_i) == list(range(1, len(s) + 1))
pr = ["P0" if r <= 100 else "P1" if r <= 500 else "P2" for r in s.rank_i]
out["priority_ok"] = bool((s.priority == pr).all())
out["tier_counts"] = s.priority.value_counts().to_dict()
out["in_top500_ok"] = bool((s.in_top500.astype(int) == (s.rank_i <= 500)).all())
vocab = json.load(open(R + "results/signal_vocabulary.json"))
sigs = {k for k in vocab if not k.startswith("_")}
bad, lens = 0, {}
for r in s.reasons:
    L = json.loads(r)
    ok = isinstance(L, list) and len(L) <= 3 and all(isinstance(x, dict) and set(x) == {"signal", "value", "direction"}
                                                     and x["signal"] in sigs and x["direction"] in ("up", "down") for x in L)
    bad += not ok; lens[len(L)] = lens.get(len(L), 0) + 1
out["reasons_bad"], out["reasons_len_hist"] = bad, lens
m = s.merge(sbr, on="cve_id", suffixes=("", "_sb"))
e1 = pd.to_numeric(m.epss, errors="coerce"); e2 = pd.to_numeric(m.epss_sb, errors="coerce")
out["epss_mismatch"] = int(((e1 - e2).abs() > 1e-12).sum() + (e1.isna() != e2.isna()).sum())
F = ["exploitdb", "metasploit", "nuclei", "poc_github"]
anyx = (m[F].apply(pd.to_numeric).fillna(0).max(axis=1) > 0).astype(int)
out["any_public_exploit_mismatch"] = int((anyx != m.any_public_exploit.astype(int)).sum())
out["snapshot_mismatch"] = int((m.snapshot_month != m.snapshot_month_sb).sum())
out["published_mismatch_vs_scoreboard"] = int((m.published.str[:10] != m.published_sb.str[:10]).sum())
v = pd.read_csv(D + "vulnerabilities.csv", usecols=["cve_id", "published", "assigner"], dtype=str)
m2 = s.merge(v, on="cve_id", suffixes=("", "_v"))
out["assigner_mismatch"] = int((m2.assigner != m2.assigner_v.fillna("")).sum())
out["published_mismatch_vs_vuln"] = int((m2.published.str[:10] != m2.published_v.str[:10]).sum())
out["published_after_snapshot_month"] = int((m.published.str[:7] > m.snapshot_month).sum())
out["snapshot_months"] = m.snapshot_month.value_counts().sort_index().to_dict()
# score monotone within top500 and outside
t = s[s.rank_i <= 500].sort_values("rank_i"); o = s[s.rank_i > 500].sort_values("rank_i")
out["mono_top"] = bool((np.diff(t.score.astype(float)) <= 0).all()); out["mono_rest"] = bool((np.diff(o.score.astype(float)) <= 0).all())
out["max_assigner_top500"] = int(t.assigner.value_counts().max())
# ---- item 3: assigner KEV history sample, recomputed with a python loop over raw rows ----
rng = np.random.default_rng(7)
months = sorted(s.snapshot_month.unique())
samp = []
for mo in months:
    pool = s[s.snapshot_month == mo]
    samp += pool.sample(min(4, len(pool)), random_state=int(rng.integers(1e6))).cve_id.tolist()
samp += t.sample(10, random_state=3).cve_id.tolist()
vrow = dict(zip(v.cve_id, zip(v.published.str[:10], v.assigner)))
kev_asg = [(vrow[c][1], d) for c, d in kd.items() if c in vrow and vrow[c][0] >= "2021-01-01"]
pub_list = [(p, a) for p, a in vrow.values() if isinstance(p, str) and p >= "2021-01-01"]
srow = s.set_index("cve_id")
chk = []
for c in samp:
    a, mo = srow.at[c, "assigner"], srow.at[c, "snapshot_month"]; st = mo + "-01"
    k = sum(1 for aa, d in kev_asg if aa == a and d < st)
    n = sum(1 for p, aa in pub_list if aa == a and p < st)
    chk.append({"cve_id": c, "month": mo, "assigner": a, "kev": k, "n": n, "rate": round(k / (n + 20), 4)})
out["asg_sample"] = chk
json.dump(out, open(R + "audit/scratch/p7_contract_result.json", "w"), indent=1, default=str)
print(json.dumps({k: v for k, v in out.items() if k != "asg_sample"}, indent=1, default=str))
print("sample n", len(chk))
