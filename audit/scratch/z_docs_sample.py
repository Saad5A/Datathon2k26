"""Auditor (docs/process): 30 random verified claims (seed 20261107); does the verified_by report quote the value?"""
import json, glob, random, re
R = "/Users/aahmad/Working/datathon/code/Datathon2k26/"
C = {}
for f in glob.glob(R + "results/claims*.json"): C.update(json.load(open(f)))
ver = sorted(k for k, v in C.items() if v["status"] == "verified")
random.seed(20261107); S = random.sample(ver, 30)
def forms(x):
    x = float(x); out = set()
    if x == int(x): out |= {f"{int(x)}", f"{int(x):,}"}
    for d in (1, 2, 3, 4, 6):
        s = f"{x:.{d}f}"; out |= {s, s.lstrip("0") if s.startswith("0.") else s, s.replace("-0.", "-.")}
        if abs(x) < 1: out.add(f"{100*x:.{max(d-2,0)}f}%")
    return out
hit = 0
for k in S:
    v = C[k]; txt = open(R + v["verified_by"]).read()
    f = [s for s in forms(v["value"]) if re.search(r"(?<![\d.])" + re.escape(s) + r"(?!\d)", txt)]
    hit += bool(f); print(("QUOTED " if f else "notquoted ") + k, v["value"], v["verified_by"].split("/")[-1], f[:2])
print("quoted", hit, "of 30")
