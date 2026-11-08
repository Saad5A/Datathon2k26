"""Granite-final audit: set status/verified_by for re-derived PASS claims only; confirm nothing else changed."""
import json, copy
R = "/Users/aahmad/Working/datathon/code/Datathon2k26/"; S = R + "audit/scratch/"; REP = "audit/2026-11-08-granite-final.md"
g = json.load(open(S + "gf_claims_result.json"))["results"]; f = json.load(open(S + "gf_compare_result.json"))["claims"]
for fn, res in (("results/claims_model_granite.json", g), ("results/claims_model_final.json", f)):
    c = json.load(open(R + fn)); before = copy.deepcopy(c); n = 0
    for k, v in c.items():
        if res.get(k) == "PASS":
            v["status"], v["verified_by"] = "verified", REP; n += 1
    for k in c:
        assert {a: b for a, b in c[k].items() if a not in ("status", "verified_by")} == \
               {a: b for a, b in before[k].items() if a not in ("status", "verified_by")}
    assert set(c) == set(before)
    open(R + fn, "w").write(json.dumps(c, indent=2) + "\n"); print(fn, n, "of", len(c), "verified")
