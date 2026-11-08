"""Set status/verified_by only, for keys that matched in u_check (plus tie-safe first-pass-order keys listed below)."""
import json, sys
R = "/Users/aahmad/Working/datathon/code/Datathon2k26/"; S = R + "audit/scratch/"
P = R + "results/claims_model.json"
cl = json.load(open(P)); before = json.loads(json.dumps(cl))
ok = json.load(open(S + "u_check_result.json"))["ok"]
keys = [k for k, v in ok.items() if v] + sys.argv[1:]
keys = [k for k in keys if cl[k]["status"] != "verified"]
for k in keys:
    cl[k]["status"] = "verified"; cl[k]["verified_by"] = "audit/2026-11-07-remaining.md"
for k in cl:  # only status/verified_by may differ
    assert {f for f in cl[k] if cl[k].get(f) != before[k].get(f)} <= {"status", "verified_by"}, k
json.dump(cl, open(P, "w"), indent=2, ensure_ascii=False); open(P, "a").write("\n")
print("marked", len(keys), "now unverified", sum(v["status"] != "verified" for v in cl.values()))
