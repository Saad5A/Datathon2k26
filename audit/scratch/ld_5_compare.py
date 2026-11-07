"""Auditor: compare every number in drift_summary.json with ld_4_result.json; claims ledger values vs mine."""
import json
R = "/Users/aahmad/Working/datathon/code/Datathon2k26/"; S = R + "audit/scratch/"
d = json.load(open(R + "results/drift_summary.json")); o = json.load(open(S + "ld_4_result.json"))
bad = []
def cmp(name, a, b, tol):
    if abs(float(a) - float(b)) > tol: bad.append((name, a, b))
mv = d["monthly_volume"]
for k, x in mv["cves_published_per_month_vulnerabilities_csv"].items(): cmp("vol" + k, x, o["vuln_published_per_month"][k], 0)
assert set(mv["cves_published_per_month_vulnerabilities_csv"]) == set(o["vuln_published_per_month"])
for k, x in mv["pool_rows_per_snapshot_month_2025"].items(): cmp("pool" + k, x, o["pool_rows_by_month"][k], 0)
for k, x in mv["scoreboard_rows_per_snapshot_month_2026"].items(): cmp("sb" + k, x, o["sb_rows_by_month"][k], 0)
assert set(mv["scoreboard_rows_per_snapshot_month_2026"]) == set(o["sb_rows_by_month"])
am = d["assigner_mix"]
cmp("distinct25", am["distinct_assigners"]["2025_pool"], o["distinct"]["2025"], 0); cmp("distinct26", am["distinct_assigners"]["2026_scoreboard"], o["distinct"]["2026"], 0)
assert [r["assigner"] for r in am["top15_2025_pool"]] == o["top15_25"], "top15 2025 order"
assert [r["assigner"] for r in am["top15_2026_scoreboard"]] == o["top15_26"], "top15 2026 order"
for r in am["top15_2025_pool"] + am["top15_2026_scoreboard"]:
    if r["assigner"] in o["share"]:
        cmp("share25 " + r["assigner"], r["share_2025_pool"], o["share"][r["assigner"]][0], 5e-7); cmp("share26 " + r["assigner"], r["share_2026_scoreboard"], o["share"][r["assigner"]][1], 5e-7)
md = d["missing_data_by_snapshot_month"]
for per, mine_by, mine_all in [("2025_pool", o["miss25_by_month"], o["miss25_all"]), ("2026_scoreboard", o["miss26_by_month"], o["miss26_all"])]:
    for m, row in md[per].items():
        ref = mine_all if m == "all" else mine_by[m]
        for k in ref: cmp(f"{per} {m} {k}", row[k], ref[k], 5e-7)
np_ = d["assigner_no_prior_kev_share"]; mine = o["noprior"]["all_kev"]
for m, x in np_["2025_pool"].items(): cmp("np25 " + m, x, mine["2025_all"] if m == "all" else mine["2025_by_month"][m], 5e-7)
for m, x in np_["2026_scoreboard"].items(): cmp("np26 " + m, x, mine["2026_all"] if m == "all" else mine["2026_by_month"][m], 5e-7)
print("drift_summary mismatches:", bad)
# ledger
L = json.load(open(R + "results/claims_model_drift.json")); L1 = json.load(open(S + "ld_1_result.json"))
def mine_for(cid):
    if cid.startswith("leakage.solo_auc."): return L1[cid.split(".")[-1]]["oriented"], 5e-5
    if cid == "drift.pool_rows_2025": return 35280, 0
    if cid == "drift.scoreboard_rows.total": return 72670, 0
    if cid.startswith("drift.scoreboard_rows."): return o["sb_rows_by_month"][cid.split(".")[-1]], 0
    if cid.startswith("drift.distinct_assigners."): return o["distinct"]["2025" if "2025" in cid else "2026"], 0
    if cid.startswith("drift.assigner_share."):
        a = {"github_advisories": "security-advisories@github.com", "vulncheck": "disclosure@vulncheck.com"}[cid.split(".")[2]]
        return o["share"][a][0 if "2025" in cid else 1], 1e-9
    if cid.startswith("drift.no_prior_kev_share."): return o["noprior"]["all_kev"]["2025_all" if "2025" in cid else "2026_all"], 5e-7
    parts = cid.split(".")
    if parts[0] == "drift" and parts[2] in ("2025_pool", "2026_scoreboard"):
        if parts[3] == "all": return o["miss25_all" if parts[2] == "2025_pool" else "miss26_all"][parts[1]], 5e-7
        return o["miss26_by_month"][parts[3]][parts[1]], 5e-7
    return None, None
res = {}
for cid, c in L.items():
    try: m, tol = mine_for(cid)
    except KeyError: m, tol = None, None
    ok = m is not None and abs(float(m) - float(c["value"])) <= tol
    res[cid] = (c["value"], m, ok); print(f"{cid:58s} claimed {c['value']!s:22s} mine {m!s:22s} {'MATCH' if ok else 'DIFF'}")
print("n", len(res), "match", sum(r[2] for r in res.values()))
json.dump(res, open(S + "ld_5_result.json", "w"), indent=1)
