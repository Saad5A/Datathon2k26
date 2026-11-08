"""Set status/verified_by only, for claims re-derived and PASSed in audit/2026-11-07-phase3-fixes-cap.md."""
import json, subprocess
R = "/Users/aahmad/Working/datathon/code/Datathon2k26/"; REP = "audit/2026-11-07-phase3-fixes-cap.md"
fm = R + "results/claims_model.json"; c = json.load(open(fm))
old = json.loads(subprocess.run(["git", "-C", R, "show", "c2963e0:results/claims_model.json"], capture_output=True, text=True).stdout)
paired = json.load(open(R + "audit/scratch/f_paired_result.json")); cap = json.load(open(R + "audit/scratch/f_capcheck_result.json"))
ok = set()
ok |= {k for k in c if k.startswith("p3.") and k in old and old[k]["status"] == "verified" and c[k]["status"] != "verified"
       and abs(old[k]["value"] - c[k]["value"]) <= 1e-12}
n_ret = len(ok)
held = {k for k in paired if ".paired." in k and ".ci95_" in k and not k.endswith(".seed0")}
ok |= {k for k, v in paired.items() if v and k not in held}
ok |= {k for k, v in cap.items() if v}
for k in ok:
    c[k]["status"], c[k]["verified_by"] = "verified", REP
json.dump(c, open(fm, "w"), indent=2); open(fm, "a").write("\n")
fd = R + "results/claims_model_drift.json"; d = json.load(open(fd))
for k in ("leakage.solo_auc.txt_masked_tfidf", "leakage.solo_auc.asg_rate_24m"):
    d[k]["status"], d[k]["verified_by"] = "verified", REP
json.dump(d, open(fd, "w"), indent=2); open(fd, "a").write("\n")
print("retexted", n_ret, "paired/unseen", sum(1 for k in paired if paired[k] and k not in held), "held", len(held), "cap", sum(cap.values()), "total model", len(ok))
