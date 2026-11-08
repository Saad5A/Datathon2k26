"""Dashboard-columns audit of results/scores_2026.csv (1fd5083) vs the verified version (5a78fcc). Plain csv/pandas, no src/."""
import csv, io, json, math, subprocess, numpy as np, pandas as pd
R = "/Users/aahmad/Working/datathon/code/Datathon2k26/"; S = R + "audit/scratch/"; D = R + ".data/data/"
git = lambda spec: subprocess.run(["git", "-C", R, "show", spec], capture_output=True, text=True, check=True).stdout
out = {}
rd = lambda t: pd.read_csv(io.StringIO(t), dtype=str, keep_default_na=False)
old, new = rd(git("5a78fcc:results/scores_2026.csv")), pd.read_csv(R + "results/scores_2026.csv", dtype=str, keep_default_na=False)
out["old_blob_eq_verified_bf11016"] = git("5a78fcc:results/scores_2026.csv") == git("bf11016:results/scores_2026.csv")
out["top500_identical_to_5a78fcc"] = open(R + "results/top500.csv").read() == git("5a78fcc:results/top500.csv")
out["rows_old_new"] = [len(old), len(new)]; out["same_row_order"] = old.cve_id.tolist() == new.cve_id.tolist()
O, N = old.set_index("cve_id"), new.set_index("cve_id").loc[old.cve_id]
out["col_mismatch_counts"] = {c: int((O[c] != N[c]).sum()) for c in old.columns if c not in ("cve_id", "reasons")}
strip = lambda s: [{k: v for k, v in x.items() if k != "impact"} for x in json.loads(s)]
out["reasons_mismatch_ignoring_impact"] = int(sum(strip(a) != json.loads(b) for a, b in zip(N.reasons, O.reasons)))
out["reasons_key_order_new"] = sorted({tuple(x) for s in N.reasons for x in json.loads(s)})
# contract column order (docs/INTERFACES_dashboard.md section 1 code block)
doc = open(R + "docs/INTERFACES_dashboard.md").read().split("## 1.")[1].split("```")[1].strip()
out["column_order_matches_contract"] = list(new.columns) == doc.split(",")
# percentile
rk = new["rank"].astype(int); n = len(new)
exp = [round(100 * (1 - (r - 1) / n), 1) for r in rk]
out["percentile_mismatch"] = int(sum(abs(float(p) - e) > 1e-9 for p, e in zip(new.percentile, exp)))
out["percentile_rank1_last"] = [new.percentile[rk == 1].iat[0], new.percentile[rk == n].iat[0]]
# flags vs scoreboard
sb = pd.read_csv(D + "scoreboard_2026.csv", dtype=str, keep_default_na=False).set_index("cve_id").loc[new.cve_id]
F = ["exploitdb", "metasploit", "nuclei", "poc_github"]
out["scoreboard_flag_values"] = {f: sorted(sb[f].unique().tolist()) for f in F}
out["flag_mismatch"] = {f: int((pd.to_numeric(sb[f].replace("", "0")).astype(int).to_numpy() != new[f].astype(int).to_numpy()).sum()) for f in F}
out["any_or_mismatch"] = int((new[F].astype(int).max(axis=1) != new.any_public_exploit.astype(int)).sum())
out["model_version_values"] = new.model_version.unique().tolist()
# impact: all rows from the auditor's own G2 refit (gf_final.py), with a 20-row printed spot-check
z = np.load(S + "gf_final_scores.npz"); gsb = pd.read_parquet(S + "gf_sb.parquet")
score = z["actual"].mean(axis=0); G = ["epss", "public_exploit_code", "assigner_kev_history", "description_text"]
Dl = np.abs(np.column_stack([score - z[g] for g in G])); tot = Dl.sum(1)
pos = {c: i for i, c in enumerate(gsb.cve_id)}
bad = rng_bad = 0; spot = []
pick = set(np.random.default_rng(20).choice(len(new), 20, replace=False).tolist())
for k, (c, s) in enumerate(zip(new.cve_id, new.reasons)):
    i = pos[c]
    for x in json.loads(s):
        mine = round(float(Dl[i, G.index(x["signal"])] / tot[i]), 3) if tot[i] > 0 else 0.0
        bad += abs(mine - x["impact"]) > 1e-12; rng_bad += not (0 <= x["impact"] <= 1)
        if k in pick: spot.append([c, x["signal"], x["impact"], mine])
out["impact_mismatch_all_rows"], out["impact_out_of_range"] = bad, rng_bad
out["impact_spot_20_rows"] = spot; out["impact_spot_mismatch"] = sum(abs(a[2] - a[3]) > 1e-12 for a in spot)
# parse.ts emulation: preScored (every score numeric) and fullyRanked (rank, percentile numeric, priority P0-2, unique ranks)
def num(v):
    v = v.strip()
    if v == "": return None
    try: f = float(v)
    except ValueError: return None
    return f if math.isfinite(f) and v.lower() not in ("nan", "inf", "-inf", "infinity") else None
with open(R + "results/scores_2026.csv", newline="", encoding="utf-8") as fh:
    recs = list(csv.DictReader(fh))
out["parse_preScored"] = all(num(r["score"]) is not None for r in recs)
out["parse_fullyRanked"] = out["parse_preScored"] and all(num(r["rank"]) is not None and num(r["percentile"]) is not None
                                                          and r["priority"].strip().upper() in ("P0", "P1", "P2") for r in recs) \
    and len({num(r["rank"]) for r in recs}) == len(recs)
out["score_range"] = [min(float(r["score"]) for r in recs), max(float(r["score"]) for r in recs)]
out["any_reason_value_not_num_str_null"] = int(sum(not (x["value"] is None or isinstance(x["value"], (int, float, str)))
                                                   for r in recs for x in json.loads(r["reasons"])))
print(json.dumps({k: v for k, v in out.items() if k != "impact_spot_20_rows"}, indent=1)); print(spot[:8])
json.dump(out, open(S + "gf_dash_result.json", "w"), indent=1, default=str)
