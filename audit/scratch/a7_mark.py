"""Set status/verified_by only for claims re-derived and PASSed. Touches no other field."""
import json
R = "/Users/aahmad/Working/datathon/code/Datathon2k26/"; S = R + "audit/scratch/"
ok = {}
for f in ("a2_result.json", "a4_result.json", "a5_result.json", "a6_result.json"):
    ok.update(json.load(open(S + f)))
assert all(ok.values()), [k for k, v in ok.items() if not v]
ok.update({f"pool.{k}": True for k in ("pool_rows", "pool_positives", "train_rows", "train_positives", "test_rows", "test_positives")})
# Reproduced, but the value is one arbitrary order inside a tied group (tie range in the audit report): not verified.
TIE_DEPENDENT = {f"primary.{m}.{k}" for m, ks in {
    "cvss3": ("top500_first_pass_order", "top1000_first_pass_order", "median_rank_first_pass_order"),
    "epss": ("median_rank_first_pass_order",),
    "exploit_then_epss": ("top500_first_pass_order", "median_rank_first_pass_order"),
    "assigner_only": ("top500_first_pass_order", "median_rank_first_pass_order"),
    "hgb_signals": ("top500_first_pass_order", "top1000_first_pass_order", "median_rank_first_pass_order"),
    "hgb_signals_assigner": ("top500_first_pass_order", "median_rank_first_pass_order")}.items() for k in ks}
assert len(TIE_DEPENDENT) == 13 and TIE_DEPENDENT <= set(ok)
path = R + "results/claims_model.json"; cl = json.load(open(path)); n = 0
for k in ok:
    if k in TIE_DEPENDENT: continue
    cl[k]["status"], cl[k]["verified_by"] = "verified", "audit/2026-11-07-harness.md"; n += 1
open(path, "w").write(json.dumps(cl, indent=2) + "\n")
print("re-derived", len(ok), "verified", n, "total claims", len(cl), "unverified", sum(c["status"] != "verified" for c in cl.values()))
