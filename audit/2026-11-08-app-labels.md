# Audit: app label fix (server/ + dashboard/), branch fix/granite-labels-and-submission-docs

Date: 2026-11-08. Auditor: fresh auditor subagent (this session never saw the producer's reasoning).
Scope: uncommitted working tree vs origin/main (53a1363) for server/, dashboard/src, src/, scripts/, results/, docs/examples.
WRITEUP.md, DEVPOST.md, DEMO_SCRIPT.md, SOURCES.md, docs/RETRIEVAL.md were out of scope (another agent is editing them).
Scratch outputs: audit/scratch/al_* (API responses, server log, check script).

## 1. Data provenance: PASS (one new defect found, see 1d)

a. `git show origin/main:results/granite_explanations_top100.json`: 30 rows (not 100). `provider` = `offline_template` for 30/30, no `model_id`, yet
   `is_ai_generated: true` on every row. It was template text. Removing it from results/ is correct. The copy in
   docs/examples/explanations_top30_OFFLINE_TEMPLATE_not_granite.json is byte-identical (cmp) and was already on origin/main.
b. results/gemini_explanations_top100.json: 30 rows, `provider: GEMINI`, `model_id: gemini-2.5-flash (...)`, `generation_mode: live`.
   I re-ran `scripts/build_gemini_from_granite.synthesize()` on the origin/main template file plus results/scores_2026.csv
   (audit/scratch/al_check_gemini.py). Result: 30/30 rows match exactly on gemini_technical_summary, gemini_executive_summary,
   gemini_triage_playbook and granite_technical_rationale. That script is a Python f-string template and calls no API.
   The only Gemini API caller in the repo is src/remediation_agent.py, and it writes the playbook cache and the sample file, not this one.
   `generation_mode` is not written by the script. `git log -S` shows it was added by hand in commit d5016e8
   (author Saad, 2026-11-08, "feat(ui): 3D pancake stack..."). So the "live Gemini" label was false. The server now rejects
   rows that carry `source_granite`: 0 Gemini rows load (/api/health `gemini_explanations: false`). PASS.
c. results/granite_summaries_top100.json: 100 rows. (summary_source, model_id, ai_generated) =
   (granite, granite4.2:3b, True) for 94 rows and (template, deterministic-template, False) for 6. Labels match summary_source. PASS.
d. NEW DEFECT (FAIL, must fix): the summaries were built against the pre-G2 ranking. Their `rank` matches the old template file
   for 30/30 rows but differs from the submitted scores_2026.csv (model_version G2) for 97/100 rows. `priority` differs for 11 rows.
   Only 89 of the current top 100 have a summary. Missing: ranks 48, 70, 72, 75, 81, 82, 83, 92, 94, 95, 98.
   11 summaries are for CVEs now ranked 101 to 427. The served `why_this_rank` text therefore contradicts the rank shown next to it.
   Example: /api/explanations/CVE-2026-50229 returns `rank: 22` with granite.why_this_rank "Rank 17, priority P0".
   The UI copy "summaries cover the top 100" and the claims_ibm.json "top100" wording are also wrong.

## 2. Server behaviour: FAIL (labels on one route)

Setup: a scratch venv outside the repo with only server/requirements.txt installed, then `uvicorn server.app:app`. The log has no errors and `load_errors: []`.
- /api/health: 100 explanations, 0 playbooks, Gemini off. No crash from the removed files.
- /api/explanations/CVE-2026-10523: source granite, model_id granite4.2:3b, is_ai_generated true, label "AI-generated (IBM Granite instruct, run locally), unaudited". PASS.
- /api/explanations/CVE-2026-50229 (template fallback): source/provider template, is_ai_generated false, label "Template fallback (not AI-generated)". PASS.
  Minor: it is still nested under the `granite` key with `available.granite: true`. The UI keys off is_ai_generated, so the display is correct.
- ?model=gemini returns 404 "No Gemini executive brief". A missing CVE returns 404. PASS.
- /api/models/comparison: `mean_delta_auc_vs_tfidf: null`, note "Exploratory subset, not comparable". Counts 94/6. No lift claimed. PASS.
- /api/stats/summary: all three fold deltas are null. No lift claimed. PASS.
- FAIL: POST /api/gemini/refine-action for template-fallback CVE-2026-50229 (granite_divergence and custom_refinement) returns content
  containing "Granite summary (AI-generated): Improper Neutralization ..." although that text is the deterministic template.
  This happens because `_synthesize_refine` hard-codes "Granite summary (AI-generated)" and never checks the explanation's `source`.
  It also accepts the client-supplied `granite_rationale` (the dashboard sends it from PancakeSecDashboard.tsx:152 and CveInspectionDrawer.tsx:186)
  and labels whatever arrives as Granite.
  Fix: label from `store.explanations[cve]["is_ai_generated"]` ("Granite summary (AI-generated)" vs "Template summary (no AI)"), and ignore or separately label `body.granite_rationale`.
- Other breakage: scripts/verify_dashboard_integrity.py:44 still reads the removed file and now raises FileNotFoundError. It is not in CI.
  README.md:89 and docs/IBM_USAGE.md:27 still name results/granite_explanations_top100.json and `ibm/granite-3-8b-instruct`. Update all three.

## 3. Protected files: PASS

`git diff origin/main --stat` shows no change to results/top500.csv, scores_2026.csv, signal_vocabulary.json, backtest_summary.json,
leakage_table.csv, drift_summary.json, claims*.json, JUDGE_QA.md, docs/writeup_model.md, LEARNING.md, AGENTS.md or LOG.md.
audit/: audit/2026-11-07-docs-and-process.md has 62 additions and 0 deletions (numstat). Everything else under audit/ is new untracked scratch.
Note: data_cache/granite_embeddings.meta.json, which models.py now reads, is untracked. In a fresh clone or deploy, `embedding_model_id` is null (no crash).

## 4. Dashboard build: PASS (wording: FAIL on 2 strings)

`npm ci` ran with the lockfile unchanged. `npx tsc -b` reported no errors (exit 0). `npx vitest run`: 5 files, 23 tests passed. `npm run build` succeeded.
Grep of dashboard/src:
- No "Exploit Score", "Gemini synthes", "% chance" or "improve" overclaims.
- "lift" occurs only as 3D hover variables and the honest "G2 is not an improvement" text.
- "probability" occurs only in disclaimers.
- No hard-coded IP. The domain pancakess.work is used.
Still wrong:
- PancakeSecDashboard.tsx:638 has the table header "Public Weaponization". The cell itself says "Public exploit code".
- PancakeSecDashboard.tsx:242 has the header "Watsonx Subset Embeddings" (see 5).

## 5. UI numbers not backed by a verified claim: FAIL

- Header "Watsonx Subset Embeddings 233,097 tokens" comes from data_cache/granite_embeddings_watsonx_subset.meta.json. There is no claim for it.
  It describes an exploratory subset, not the submitted model. The G2 embeddings are LOCAL sentence-transformers, 15,793,616 est. tokens per the untracked meta.
- Header "Audit Corpus 1,500 CVEs" is `total_analyzed_cves`, which is the watsonx subset `n_rows`. There is no claim for it and the label is wrong.
- The "94 AI-generated / 6 template fallbacks" counts (ModelComparisonCard, /api/stats) match claims_ibm.json `granite_explanations.*`, but those claims are UNVERIFIED and defect 1d applies.
  They are acceptable as plain file counts only once 1d is fixed.
- "P0 Critical Tier 100 / 500" is supported by verified claim p7.tier.P0.count = 100 (claims_model_final.json).
- The adoption_note "adopted by a pre-registered rule; no measurable gain" has no single claim id. UNCHECKED here.

## Required fixes before PR
1. Regenerate results/granite_summaries_top100.json from the current G2 scores_2026.csv top 100 (cloud/explain_granite_ollama.py).
   If that is not possible, stop serving `why_this_rank`, `rank` and `priority` from it, and change the "top 100" wording to "89 of the current top 100".
2. In refine-action, label the summary by its real source and do not label client-supplied text as Granite.
3. Remove or relabel the header token and "Audit Corpus" numbers. Rename "Public Weaponization" to "Public exploit code".
4. Fix scripts/verify_dashboard_integrity.py, README.md:89 and docs/IBM_USAGE.md:27. Commit data_cache/granite_embeddings.meta.json or tolerate its absence in the UI.

Claims status: no claims*.json status changed. Nothing here verifies granite_explanations.* (defect 1d).
