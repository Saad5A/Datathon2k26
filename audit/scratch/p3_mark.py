"""Set status/verified_by only on p3.* claims that I re-derived, that matched, and whose text describes the number."""
import json
R = "/Users/aahmad/Working/datathon/code/Datathon2k26/"; S = R + "audit/scratch/"
ok = {}
for f in ("p3_boot_result.json", "p3_extra_result.json"):
    ok.update(json.load(open(S + f)))
assert all(ok.values()), [k for k, v in ok.items() if not v]
# Reproduced exactly, but the number is from seed set 0 while the claim text does not say so (headline is the seed median).
HOLD = {f"p3.{f}.paired.{m}.{s}" for f in ("fold1", "fold2") for m in ("auc", "top500_expected") for s in ("diff", "ci95_lo", "ci95_hi")}
HOLD |= {f"p3.{f}.unseen_assigner.{k}" for f in ("fold1", "fold2") for k in ("auc", "top500_rows_from_subset", "top500_hits_from_subset")}
assert HOLD <= set(ok) and len(HOLD) == 18
path = R + "results/claims_model.json"; cl = json.load(open(path)); n = 0
for k in ok:
    assert k.startswith("p3.")
    if k in HOLD: continue
    cl[k]["status"], cl[k]["verified_by"] = "verified", "audit/2026-11-07-phase3.md"; n += 1
open(path, "w").write(json.dumps(cl, indent=2) + "\n")
p3 = [k for k in cl if k.startswith("p3.")]
print("re-derived", len(ok), "held", len(HOLD), "verified", n, "p3 total", len(p3),
      "p3 unverified", sum(cl[k]["status"] != "verified" for k in p3))
