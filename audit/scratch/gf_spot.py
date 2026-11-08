"""Granite-final audit: re-embed 30 random rows with the cached open-weights model (offline) and compare; unseen-assigner check."""
import os, json, numpy as np, pandas as pd
os.environ["HF_HUB_OFFLINE"] = "1"
R = "/Users/aahmad/Working/datathon/code/Datathon2k26/"; S = R + "audit/scratch/"; D = R + ".data/data/"
out = {}
inp = pd.read_parquet(R + "data_cache/descriptions_to_embed.parquet"); E = pd.read_parquet(R + "data_cache/granite_embeddings.parquet").set_index("cve_id")
pick = inp.sample(30, random_state=7)
try:
    from sentence_transformers import SentenceTransformer
    m = SentenceTransformer("ibm-granite/granite-embedding-278m-multilingual", revision="a9cb5338491faf32b73dd17b714a31821c021bbf", device="cpu")
    m.max_seq_length = 512
    V = m.encode(pick.text.tolist(), normalize_embeddings=True)
    B = np.stack(E.loc[pick.cve_id].vector.to_numpy())
    cos = (V * B).sum(1); out["spot_cos_min"], out["spot_n"] = float(cos.min()), len(cos)
except Exception as e:
    out["spot_error"] = repr(e)[:300]
# unseen-assigner rows in top500: any KEV row of ANY publication year before the snapshot month?
s = pd.read_csv(R + "results/scores_2026.csv", dtype=str); sb = pd.read_parquet(S + "gf_sb.parquet")
t = s[s.in_top500 == "1"].merge(sb[["cve_id", "asg_kev"]], on="cve_id"); u = t[t.asg_kev == 0]
v = pd.read_csv(D + "vulnerabilities.csv", usecols=["cve_id", "assigner"], dtype=str)
k = pd.read_csv(D + "known_exploited.csv", usecols=["cve_id", "date_added"], dtype=str).merge(v, on="cve_id")
out["unseen_rows"] = len(u)
out["unseen_rows_with_any_prior_kev_any_year"] = int(sum(((k.assigner == a) & (k.date_added < m + "-01")).any() for a, m in zip(u.assigner, u.snapshot_month)))
print(json.dumps(out, indent=1)); json.dump(out, open(S + "gf_spot_result.json", "w"), indent=1)
