"""Phase 7 audit: compare auditor refit (p7_scores.npz) with producer outputs; own cap walk; claims; occlusion reasons."""
import json, numpy as np, pandas as pd
R = "/Users/aahmad/Working/datathon/code/Datathon2k26/"; S = R + "audit/scratch/"
z = np.load(S + "p7_scores.npz"); sb = pd.read_parquet(S + "p7_sb.parquet")
score = z["actual"].mean(axis=0)
prev = np.load(S + "f_2026_scores.npy")  # earlier audit's independent run
out = {"max_abs_vs_earlier_audit_run": float(np.abs(prev - z["actual"]).max())}
# own cap walk (plain python)
order = sorted(range(len(score)), key=lambda i: (-score[i], sb.cve_id.iat[i]))
used, top = {}, []
asg = sb.assigner.tolist()
for i in order:
    if used.get(asg[i], 0) >= 50: continue
    used[asg[i]] = used.get(asg[i], 0) + 1; top.append(i)
    if len(top) == 500: break
mine = sb.cve_id.iloc[top].tolist()
prod = pd.read_csv(R + "results/top500.csv", dtype=str).cve_id.tolist()
s = pd.read_csv(R + "results/scores_2026.csv", dtype={"cve_id": str})
out["top500_overlap"] = len(set(mine) & set(prod)); out["top500_same_order"] = mine == prod
m = sb.assign(my=score).merge(s[["cve_id", "score", "rank", "reasons"]], on="cve_id")
out["max_abs_score_diff"] = float((m.my - m.score).abs().max())
rest = [i for i in order if i not in set(top)]
myrank = np.empty(len(score), int); myrank[np.array(top + rest)] = np.arange(1, len(score) + 1)
out["rank_mismatch_all"] = int((myrank[m.index] != m["rank"].to_numpy()).sum())
T = sb.iloc[top]
vc = T.assigner.value_counts()
out["top10_assigners"] = list(vc.head(10).items())
out["n_assigners_at_12"] = vc[vc == 12].index.tolist()
out["share_any_public_exploit"] = float(T.anyx.gt(0).mean()); out["share_epss_gt_0_1"] = float((T.epss > 0.1).mean())
out["share_epss_missing"] = float(T.epss.isna().mean())
out["share_unseen_assigner"] = float((T.asg_kev == 0).mean())
pool = pd.read_parquet(S + "my_pool2.parquet"); out["train_rows"], out["train_pos"] = len(pool), int(pool.y.sum())
# occlusion reasons for 10 random top-500 rows
G = ["epss", "public_exploit_code", "assigner_kev_history", "description_text"]
rng = np.random.default_rng(11); pick = rng.choice(top, 10, replace=False)
srow = s.set_index("cve_id"); rs = []
for i in pick:
    d = {g: score[i] - z[g][i] for g in G}
    idx = sorted(G, key=lambda g: -abs(d[g]))[:3]
    val = {"epss": None if pd.isna(sb.epss.iat[i]) else round(float(sb.epss.iat[i]), 5), "public_exploit_code": int(sb.nx.iat[i]),
           "assigner_kev_history": round(float(sb.asg_rate.iat[i]), 4), "description_text": round(float(z["st"][i]), 4)}
    mineR = [{"signal": g, "value": val[g], "direction": "up" if d[g] > 0 else "down"} for g in idx if abs(d[g]) > 1e-9]
    theirs = json.loads(srow.at[sb.cve_id.iat[i], "reasons"])
    rs.append({"cve_id": sb.cve_id.iat[i], "match": mineR == theirs, "deltas": {g: round(float(d[g]), 5) for g in G}, "mine": mineR, "theirs": theirs})
out["reasons_check"] = rs; out["reasons_match"] = sum(r["match"] for r in rs)
# all-row reasons comparison (bonus)
allm = 0
D = np.column_stack([score - z[g] for g in G])
for k, (i, r) in enumerate(zip(range(len(sb)), m.reasons)):
    pass
json.dump(out, open(S + "p7_compare_result.json", "w"), indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x))
print(json.dumps({k: v for k, v in out.items() if k != "reasons_check"}, indent=1, default=str))
for r in rs: print(r["cve_id"], r["match"], r["deltas"])
