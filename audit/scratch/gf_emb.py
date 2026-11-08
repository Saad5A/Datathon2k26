"""Granite-final audit: embedding integrity. Does not import src/. Reads raw CSV directly."""
import hashlib, json, re, numpy as np, pandas as pd
R = "/Users/aahmad/Working/datathon/code/Datathon2k26/"; S = R + "audit/scratch/"
out = {}
h = hashlib.sha256(open(R + "data_cache/descriptions_to_embed.parquet", "rb").read()).hexdigest()
meta = json.load(open(R + "data_cache/granite_embeddings.meta.json"))
wmeta = json.load(open(R + "data_cache/granite_embeddings_watsonx_subset.meta.json"))
out["input_sha256"] = h; out["sha_match_local_meta"] = h == meta["input_sha256"]; out["sha_match_watsonx_meta"] = h == wmeta["input_sha256"]
inp = pd.read_parquet(R + "data_cache/descriptions_to_embed.parquet")
E = pd.read_parquet(R + "data_cache/granite_embeddings.parquet")
M = np.stack(E.vector.to_numpy()).astype(np.float64)
out["emb_shape"] = list(M.shape); out["emb_ids_unique"] = bool(E.cve_id.is_unique)
out["finite"] = bool(np.isfinite(M).all())
n = np.linalg.norm(M, axis=1); out["norm_min"], out["norm_max"] = float(n.min()), float(n.max())
out["emb_ids_eq_input_ids"] = set(E.cve_id) == set(inp.cve_id)
pool = pd.read_parquet(S + "p3_pool.parquet")
sb = pd.read_csv(R + ".data/data/scoreboard_2026.csv", usecols=["cve_id"], dtype=str)
ids = set(E.cve_id)
out["pool_missing"] = int((~pool.cve_id.isin(ids)).sum()); out["sb_missing"] = int((~sb.cve_id.isin(ids)).sum())
out["pool_rows"], out["sb_rows"] = len(pool), len(sb)
out["n_extra_ids"] = len(ids - set(pool.cve_id) - set(sb.cve_id))
# masked text equals my masking of raw descriptions
W = re.compile(r"exploited in the wild|actively exploited|known to be exploited|has been exploited|"
               r"may have been exploited|is being exploited|CISA|KEV", re.I)
v = pd.read_csv(R + ".data/data/vulnerabilities.csv", usecols=["cve_id", "description"], dtype=str)
v = v.drop_duplicates("cve_id")
mine = inp[["cve_id", "text"]].merge(v, on="cve_id", how="left")
mine["m"] = [W.sub(" ", s) for s in mine.description.fillna("")]
out["text_eq_my_masked_raw"] = int((mine.m == mine.text).sum()); out["text_rows"] = len(mine)
out["texts_with_wording_left"] = int(mine.text.str.contains(W).sum())
out["raw_with_wording"] = int(mine.description.fillna("").str.contains(W).sum())
# identical text -> identical vector (sanity)
Ei = E.set_index("cve_id"); inp_i = inp.set_index("cve_id")
# watsonx consistency
Wx = pd.read_parquet(R + "data_cache/granite_embeddings_watsonx_subset.parquet")
out["wx_rows"] = len(Wx); out["wx_unique"] = bool(Wx.cve_id.is_unique)
A = np.stack(Wx.vector.to_numpy()).astype(np.float64)
B = M[Ei.index.get_indexer(Wx.cve_id)]
assert (Ei.index.get_indexer(Wx.cve_id) >= 0).all()
cos = (A * B).sum(1) / np.linalg.norm(A, axis=1) / np.linalg.norm(B, axis=1)
out["wx_cos_min"], out["wx_cos_mean"] = float(cos.min()), float(cos.mean())
out["wx_n_cos_ge_0_99995"] = int((cos >= 0.99995).sum())
out["wx_max_abs_diff"] = float(np.abs(A - B).max()); out["wx_n_bit_identical"] = int((A == B).all(1).sum())
out["wx_norm_min_max"] = [float(np.linalg.norm(A, axis=1).min()), float(np.linalg.norm(A, axis=1).max())]
# negative control: cosine of random pairs
rng = np.random.default_rng(0); j = rng.permutation(len(B))
out["wx_cos_shuffled_mean"] = float(((A * B[j]).sum(1)).mean())
print(json.dumps(out, indent=1)); json.dump(out, open(S + "gf_emb_result.json", "w"), indent=1)
