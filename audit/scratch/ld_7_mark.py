"""Auditor: set status/verified_by only, for claims that PASSed in audit/2026-11-07-leakage-drift.md."""
import json, copy
P = "/Users/aahmad/Working/datathon/code/Datathon2k26/results/claims_model_drift.json"
L = json.load(open(P)); before = copy.deepcopy(L)
FAIL = {"drift.no_prior_kev_share.2025_pool", "drift.no_prior_kev_share.2026_scoreboard"}
for k, c in L.items():
    if k not in FAIL:
        c["status"] = "verified"; c["verified_by"] = "audit/2026-11-07-leakage-drift.md"
for k in L:  # nothing else changed
    assert {f: v for f, v in L[k].items() if f not in ("status", "verified_by")} == {f: v for f, v in before[k].items() if f not in ("status", "verified_by")}
json.dump(L, open(P, "w"), indent=2); open(P, "a").write("\n")
print(sum(c["status"] == "verified" for c in L.values()), "verified of", len(L))
