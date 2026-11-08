"""Granite-final audit: compare auditor G2 refit (gf_final_scores.npz) with the producer's final files; contract; claims."""
import csv, json, numpy as np, pandas as pd
R = "/Users/aahmad/Working/datathon/code/Datathon2k26/"; S = R + "audit/scratch/"; D = R + ".data/data/"
z = np.load(S + "gf_final_scores.npz"); sb = pd.read_parquet(S + "gf_sb.parquet")
score = z["actual"].mean(axis=0); out = {}
order = sorted(range(len(score)), key=lambda i: (-score[i], sb.cve_id.iat[i]))
used, top = {}, []; asg = sb.assigner.tolist()
for i in order:
    if used.get(asg[i], 0) >= 50: continue
    used[asg[i]] = used.get(asg[i], 0) + 1; top.append(i)
    if len(top) == 500: break
mine = sb.cve_id.iloc[top].tolist()
with open(R + "results/top500.csv") as f: rows = list(csv.reader(f))
prod = [r[0] for r in rows[1:]]
out["top500_header"], out["top500_ncols"], out["top500_n"], out["top500_unique"] = rows[0], sorted({len(r) for r in rows}), len(prod), len(set(prod))
sbr = pd.read_csv(D + "scoreboard_2026.csv", dtype=str)
out["top500_in_scoreboard"] = int(pd.Series(prod).isin(sbr.cve_id).sum())
out["top500_overlap_mine"] = len(set(mine) & set(prod)); out["top500_same_order"] = mine == prod
s = pd.read_csv(R + "results/scores_2026.csv", dtype={"cve_id": str, "published": str, "snapshot_month": str})
out["cols"] = list(s.columns); out["rows"], out["unique"] = len(s), int(s.cve_id.nunique())
out["set_eq_scoreboard"] = set(s.cve_id) == set(sbr.cve_id)
out["rank_perm"] = sorted(s["rank"]) == list(range(1, len(s) + 1))
out["top500_eq_rank1_500"] = prod == s.sort_values("rank").cve_id.head(500).tolist()
out["priority_ok"] = bool((s.priority == np.where(s["rank"] <= 100, "P0", np.where(s["rank"] <= 500, "P1", "P2"))).all())
out["in_top500_ok"] = bool((s.in_top500 == (s["rank"] <= 500).astype(int)).all())
out["tier_counts"] = s.priority.value_counts().to_dict()
T = s[s.in_top500 == 1]; out["max_per_assigner_top500"] = int(T.assigner.value_counts().max())
m = sb.assign(my=score).merge(s[["cve_id", "score", "rank", "reasons"]], on="cve_id")
out["max_abs_score_diff"] = float((m.my - m.score).abs().max())
rest = [i for i in order if i not in set(top)]
myrank = np.empty(len(score), int); myrank[np.array(top + rest)] = np.arange(1, len(score) + 1)
out["rank_mismatch_all"] = int((myrank != m["rank"].to_numpy()).sum())
# reasons: all rows
vocab = json.load(open(R + "results/signal_vocabulary.json")); sigs = {k for k in vocab if not k.startswith("_")}
out["vocab_signals"] = sorted(sigs); out["vocab_text_source"] = vocab.get("_text_source")
out["vocab_desc_cols"] = vocab["description_text"]["model_columns_set_to_neutral"]
G = ["epss", "public_exploit_code", "assigner_kev_history", "description_text"]
Dl = np.column_stack([score - z[g] for g in G])
bad_parse = mism = 0
for i in range(len(sb)):
    L = json.loads(m.reasons.iat[i])
    bad_parse += not (len(L) <= 3 and all(set(x) == {"signal", "value", "direction"} and x["signal"] in sigs and x["direction"] in ("up", "down") for x in L))
    idx = [j for j in np.argsort(-np.abs(Dl[i]), kind="stable")[:3] if abs(Dl[i, j]) > 1e-9]
    val = {"epss": None if pd.isna(sb.epss.iat[i]) else round(float(sb.epss.iat[i]), 5), "public_exploit_code": int(sb.nx.iat[i]),
           "assigner_kev_history": round(float(sb.asg_rate.iat[i]), 4), "description_text": round(float(z["st"][i]), 4)}
    mineR = [{"signal": G[j], "value": val[G[j]], "direction": "up" if Dl[i, j] > 0 else "down"} for j in idx]
    mism += mineR != L
out["reasons_bad_parse"], out["reasons_mismatch_all_rows"] = bad_parse, mism
# claims
Tm = sb.iloc[top]; vc = Tm.assigner.value_counts()
pool = pd.read_parquet(S + "p3_pool.parquet")
mc = {"p7.train_rows": len(pool), "p7.train_positives": int(pool.y.sum()), "p7.rows_scored": len(sb),
      "p7.top500.share_any_public_exploit": float(Tm.anyx.gt(0).mean()), "p7.top500.share_epss_gt_0_1": float((Tm.epss > 0.1).mean()),
      "p7.top500.share_unseen_assigner": float((Tm.asg_kev == 0).mean())}
for t, n in pd.Series(np.where(myrank <= 100, "P0", np.where(myrank <= 500, "P1", "P2"))).value_counts().items():
    mc[f"p7.tier.{t}.count"] = int(n)
cl = json.load(open(R + "results/claims_model_final.json")); cres = {}
for i, (a, n) in enumerate(vc.head(10).items(), 1):
    k = f"p7.top500.assigner_rank{i}.count"; mc[k] = int(n)
    cres[k + ".name_in_text"] = a in cl[k]["text"]
for k, c in cl.items():
    cres[k] = "PASS" if k in mc and abs(mc[k] - c["value"]) <= (0 if c["unit"] == "count" else 1e-9) else f"FAIL mine={mc.get(k)} claimed={c['value']}"
out["claims"] = cres; out["mine_claim_values"] = mc
out["assigner_count_ties_top10"] = vc.head(12).to_dict()
# change vs previously verified TF-IDF files (git 558960b)
import subprocess, io
old = pd.read_csv(io.StringIO(subprocess.run(["git", "-C", R, "show", "558960b:results/top500.csv"], capture_output=True, text=True).stdout), dtype=str)
out["overlap_with_verified_tfidf_top500"] = len(set(old.cve_id) & set(prod))
# no excluded fields in vocab / meta columns
print(json.dumps(out, indent=1, default=str)); json.dump(out, open(S + "gf_compare_result.json", "w"), indent=1, default=str)
