"""Compare r_result.json with rev.* claims; EPSS coverage by month; future-knowledge indicator; forward-copy check."""
import json, numpy as np, pandas as pd
R = "/Users/aahmad/Working/datathon/code/Datathon2k26/"; S = R + "audit/scratch/"
me = json.load(open(S + "r_result.json")); cl = json.load(open(R + "results/claims_model_reverse.json"))
out = {"rows": [], "fail": [], "pass": []}


def chk(key, val, tol=1e-6):
    c = cl[key]["value"]; ok = abs(c - val) <= tol and "reverse-time (not time-safe)" in cl[key]["text"]
    out["rows"].append(f"{key:58s} mine={val!r:22.20s} claimed={c!r:22.20s} {'OK' if ok else 'MISMATCH'}")
    (out["pass"] if ok else out["fail"]).append(key)


for k in ("train_rows", "train_positives", "test_rows", "test_positives"):
    chk(f"rev.{k}", me[k])
for k in ("top500_cve_id", "top500_best", "top500_worst", "top250_cve_id", "auc", "avg_precision", "median_rank_cve_id", "work50_cve_id"):
    chk(f"rev.C1.{k}.median", me["C1_median"][k])
    for n, b in me["baselines"].items():
        chk(f"rev.{n}.{k}", b[k])
for k in ("auc", "top500_cve_id"):
    chk(f"rev.C1.{k}.min", me["C1_min"][k]); chk(f"rev.C1.{k}.max", me["C1_max"][k])
for n, c in me["ci"].items():
    for k, (lo, hi) in c.items():
        chk(f"rev.{n}.ci95_lo.{k}", lo); chk(f"rev.{n}.ci95_hi.{k}", hi)

# ---- future-knowledge indicator, own code (assigner from all vulnerabilities rows) ----
v = pd.read_csv(R + ".data/data/vulnerabilities.csv", usecols=["cve_id", "assigner"], dtype=str)
kev = pd.read_csv(R + ".data/data/known_exploited.csv", usecols=["cve_id", "date_added"], dtype=str)
kv = kev.merge(v, on="cve_id", how="inner").dropna(subset=["assigner"])
asg25 = set(kv[kv.date_added.str[:4] == "2025"].assigner)
p = pd.read_parquet(S + "p3_pool.parquet")
te = p[(p.month >= "2024-01") & (p.month <= "2024-12")]; pos = te[te.y == 1]
ind = {"assigner_has_2025_kev": int(pos.assigner.isin(asg25).sum()), "own_kev_2025": int((pos.kev_date.str[:4] == "2025").sum()),
       "own_kev_before_2025-09-01_(enters_some_train_row_asg_kev)": int((pos.kev_date < "2025-09-01").sum()),
       "own_kev_before_2025-01-01_(enters_every_train_row_asg_kev)": int((pos.kev_date < "2025-01-01").sum()),
       "neg_assigner_has_2025_kev_share": float(te[te.y == 0].assigner.isin(asg25).mean()),
       "n_assigners_with_2025_kev": len(asg25)}
chk("rev.indicator.positives_whose_assigner_has_kev_additions_dated_2025", ind["assigner_has_2025_kev"])
chk("rev.indicator.positives_own_kev_date_in_2025", ind["own_kev_2025"])
out["indicator"] = ind

# ---- EPSS coverage, flags, by month and year ----
p["yr"] = p.month.str[:4]
p["epss_blank"] = p.epss.isna(); p["anyx_"] = p[["exploitdb", "metasploit", "nuclei", "poc_github"]].fillna(0).max(axis=1)
g = p.groupby("month").agg(rows=("y", "size"), pos=("y", "sum"), epss_blank=("epss_blank", "mean"), anyx=("anyx_", "mean"),
                           epss_med=("epss", "median"))
out["by_month"] = g.round(4).reset_index().to_dict("records")
gy = p.groupby("yr").agg(epss_blank=("epss_blank", "mean"), anyx=("anyx_", "mean"))
out["by_year"] = gy.round(4).to_dict()
posr = p[p.y == 1]
out["pos_epss_blank_by_year"] = posr.groupby("yr").epss_blank.agg(["sum", "size"]).to_dict()
out["pos_anyx_by_year"] = posr.groupby("yr").anyx_.agg(["sum", "size"]).to_dict()
import mymetrics as M
for yr in ("2024", "2025"):
    q = p[(p.yr == yr) & (p.month <= ("2024-12" if yr == "2024" else "2025-09"))]
    e = q.epss.astype(float).to_numpy(); ok = ~np.isnan(e)
    out[f"epss_auc_{yr}_all_blank_as_-1"] = float(M.auc(q.y.to_numpy(), np.nan_to_num(e, nan=-1)))
    out[f"epss_auc_{yr}_nonblank_only"] = float(M.auc(q.y.to_numpy()[ok], e[ok]))

# ---- forward fold-1 numbers copied into reverse_time.json vs p3 claims (verified?) ----
rt = json.load(open(R + "results/reverse_time.json"))["forward_fold1"]; pc = json.load(open(R + "results/claims_model.json"))
fw = []
for k in ("top500_cve_id", "auc", "work50_cve_id"):
    for stat in ("median", "min", "max"):
        key = f"p3.fold1.C1.{k}.{stat}"
        if key in pc:
            fw.append((key, rt["C1"][stat][k], pc[key]["value"], pc[key]["status"], abs(rt["C1"][stat][k] - pc[key]["value"]) < 1e-9))
for n, e in rt["baselines"].items():
    for k in ("top500_cve_id", "auc"):
        key = f"p3.fold1.{n}.{k}"
        if key in pc:
            fw.append((key, e["median"][k], pc[key]["value"], pc[key]["status"], abs(e["median"][k] - pc[key]["value"]) < 1e-9))
for k in ("train_rows", "test_rows", "test_positives", "train_positives"):
    key = f"p3.fold1.{k}"
    if key in pc: fw.append((key, rt["fold"][k], pc[key]["value"], pc[key]["status"], rt["fold"][k] == pc[key]["value"]))
out["forward_copy"] = fw; out["forward_missing"] = rt["missing"]
json.dump(out, open(S + "r_check_result.json", "w"), indent=1, default=str)
print("\n".join(out["rows"])); print("PASS", len(out["pass"]), "FAIL", out["fail"])
print(json.dumps(ind)); print(g.round(3).to_string()); print(gy.round(4))
print("pos epss blank", out["pos_epss_blank_by_year"]); print("pos anyx", out["pos_anyx_by_year"])
print({k: v for k, v in out.items() if k.startswith("epss_auc")})
for r in fw: print(r)
print("missing", rt["missing"])
print("paired AUC diff C1-minus", me["paired_auc_diff_C1_minus"]); print("label window days", me["label_window_days"])
print("train pos by month", me["train_pos_by_month"]); print("test pos by month", me["test_pos_by_month"])
print("per seed", [(r["top500_cve_id"], round(r["auc"], 4), r["work50_cve_id"]) for r in me["C1_per_seed"]])
