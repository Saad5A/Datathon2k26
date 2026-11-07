"""Compare p5.cap.* claims with the auditor's f_cap_result.json / f_2026_result.json; check meta code hashes."""
import json, hashlib, numpy as np
R = "/Users/aahmad/Working/datathon/code/Datathon2k26/"; S = R + "audit/scratch/"
cl = json.load(open(R + "results/claims_model.json")); a = json.load(open(S + "f_cap_result.json")); b = json.load(open(S + "f_2026_result.json"))
mine = {}
for f in ("fold1", "fold2"):
    for k in ("none", "100", "50"):
        per = a[f][k]["per_seed"]
        mine[f"p5.cap.{f}.k{k}.top500_expected"] = np.median([r["expected"] for r in per])
        mine[f"p5.cap.{f}.k{k}.top500_cve_id"] = np.median([r["by_id"] for r in per])
        mine[f"p5.cap.{f}.k{k}.largest_assigner_share"] = np.median([r["max_share"] for r in per])
        mine[f"p5.cap.{f}.k{k}.top500_expected.min"] = min(r["expected"] for r in per)
        mine[f"p5.cap.{f}.k{k}.top500_expected.max"] = max(r["expected"] for r in per)
for k, v in a["mean"].items():
    mine[f"p5.cap.selection.k{k}.mean_expected_top500"] = v
mine["p5.cap.selection.chosen_k"] = int(a["chosen"])
for k in ("none", "100", "50"):
    mine[f"p5.cap.preview2026.k{k}.largest_assigner_share"] = b[k]["median_largest"]
res = {}
for key in sorted(k for k in cl if k.startswith("p5.cap.")):
    m = mine.get(key); ok = m is not None and abs(m - cl[key]["value"]) <= 1e-6; res[key] = bool(ok)
    print(f"{key:55s} mine={m} claimed={cl[key]['value']} {'OK' if ok else 'MISMATCH/UNCHECKED'}")
print("p5.cap claims", len(res), "ok", sum(res.values()), "mine not in claims:", set(mine) - set(res))
for meta in ("assigner_cap.meta.json", "model_candidates.meta.json"):
    m = json.load(open(R + "results/" + meta))
    bad = [f for f, h in m["code_sha256"].items() if hashlib.sha256(open(R + "src/model/" + f, "rb").read()).hexdigest() != h]
    print(meta, "git_dirty", m["git_dirty"], "commit", m["git_commit"][:7], "code files differing from working tree:", bad)
json.dump(res, open(S + "f_capcheck_result.json", "w"), indent=1)
