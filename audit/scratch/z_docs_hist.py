"""Auditor (docs/process): walk git history of results/claims*.json; flag any claim whose value or text
changed while it stayed 'verified' (i.e. changed after verification without a status reset)."""
import json, subprocess
R = "/Users/aahmad/Working/datathon/code/Datathon2k26"
g = lambda *a: subprocess.run(["git", "-C", R, *a], capture_output=True, text=True).stdout
commits = g("log", "--reverse", "--format=%h", "--", "results/").split()
prev, flags, nver = {}, [], {}
for c in commits:
    files = [f for f in g("ls-tree", "--name-only", c, "results/").split() if f.split("/")[-1].startswith("claims")]
    cur = {}
    for f in files:
        try: d = json.loads(g("show", f"{c}:{f}"))
        except Exception: continue
        for k, v in d.items(): cur[f + ":" + k] = (v.get("value"), v.get("text"), v.get("status"), v.get("verified_by"))
    for k, (val, txt, st, vb) in cur.items():
        if k in prev:
            pv, pt, ps, pvb = prev[k]
            if ps == "verified" and st == "verified" and (pv != val or pt != txt):
                flags.append((c, k, pv, val, pt != txt))
            if ps == "verified" and k not in cur: pass
    gone = [k for k in prev if k not in cur and prev[k][2] == "verified"]
    if gone: print(c, "verified claims removed:", len(gone), gone[:5])
    nver[c] = sum(1 for v in cur.values() if v[2] == "verified")
    prev = cur
print("commits", len(commits), {c: n for c, n in nver.items()})
print("changed-while-verified:", len(flags))
for f in flags[:20]: print(f)
