# Team file: model-ranking  (ML ranking + IBM technology)
Only the agent for this area edits THIS file. Read the other three with `python tools/kb.py show`.

<!-- STATUS-START -->
STATUS: on track
PHASE: Phase 3 trained; audit running; final-ranking decision with human next
LAST_UPDATED: 2026-11-07T21:58Z
BLOCKED_ON: none
NEXT: Phase 3 audit verdict, then decide final 2026 ranking method with the human
ASKS: data-engineering-db: do not feed src/features.py output to the model (not time-safe); ui-dashboard: results/leakage_table.csv and results/drift_summary.json are on origin/feat/model-ranking, display only verified claims
<!-- STATUS-END -->

## 1. Mission and owned paths
Build the model that ranks vulnerabilities by likelihood of exploitation, produce the judged `top500.csv`, and own ALL IBM technology integration (Granite embeddings via watsonx.ai or local/Colab, optional watsonx training/AutoAI). Master prompt: PROMPT_MODEL_RANKING.md.

Owned paths (edit only these; shared files change via small PRs): `src/model/`, `cloud/`, `results/`, `audit/`, `docs/ibm.md`

## 2. Deliverables
| Item | Path | Status | Consumers |
|---|---|---|---|
| scores_2026.csv (all 72,670 scoreboard CVEs: cve_id, published, snapshot_month, assigner, score, rank, in_top500, priority, epss, any_public_exploit, reasons) | results/scores_2026.csv | not started | triage, ui, data |
| top500.csv (cve_id only; the judged file) | results/top500.csv | not started | judges, ui, triage |
| signal vocabulary for reasons | results/signal_vocabulary.json | not started | triage, ui |
| backtest summary (ours vs CVSS vs EPSS vs exploit-then-EPSS, with intervals) | results/backtest_summary.json | not started | ui |
| drift summary (2025 vs 2026 volume, assigner mix, missing data) | results/drift_summary.json | delivered (committed cecfbc5, audit running; not verified yet) | ui |
| leakage table (column, used?, solo AUC, reason) | results/leakage_table.csv | delivered (committed cecfbc5, audit running; not verified yet) | ui, write-up |
| claims ledger | results/claims_model.json | exists, all unverified | everyone (check_claims) |
| IBM tech documentation | docs/ibm.md | not started | write-up, Devpost |
| Granite embeddings (cloud step) | data_cache/granite_embeddings.parquet | not started | model |

## 3. What I need from others
| Need | From | Status |
|---|---|---|
| cve_base.parquet / kev.parquet (optional; model has its own loaders until delivered) | data-engineering-db | optional |
| Watsonx.ai trial account, API key, usage limits | human teammate | pending |
| Confirmation of INTERFACES sections 2 and 4 | data, ui | open |

## 4. Contracts I promise or rely on
- docs/INTERFACES.md sections 1, 3, 6, 7 (LOCKED with triage): priority P0 rank 1-100, P1 101-500, P2 rest; wording "Priority Score"/"Rank", never probability.
- No 2026 labels exist: we make no 2026 accuracy claims.

## 5. Facts and decisions others must know
- Backtest first-pass numbers (unaudited) are in docs/kb/02_findings_first_pass.md; target to reproduce: best model 25 hits in top 500 on the 2025 backtest versus 19 for the best baseline.
- Model features avoid NVD fields filled in after attacks (nvd_status, n_affected_cpes, n_references, blank-score patterns, references links).

## 6. Blockers and risks
- (none yet)

## 7. Changelog (append-only, newest first; format: YYYY-MM-DDTHH:MMZ | what changed | files | DECISION/ASK tag if any)
- 2026-11-07T21:58Z | Pushed feat/model-ranking to origin (89e6dc9): harness, audits, Phase 3 results, leakage_table.csv, drift_summary.json. Numbers: use only claims with status verified | results/, audit/, src/model/
- 2026-11-07T21:56Z | Phase 3 trained (unaudited): pre-registered rule picked C1 (HGB signals + assigner history + masked text). It does not beat exploit-then-EPSS on top-500 in the backtest; ranking-quality gain is smaller and uncertain. Phase 3 audit running; leakage/drift fixes in progress | results/model_candidates.json
- 2026-11-07T21:51Z | results/leakage_table.csv and results/drift_summary.json exist on feat/model-ranking (not pushed yet), claims in results/claims_model_drift.json all unverified; audit running. ui-dashboard: schema is ready to code against, do not display numbers until verified | results/leakage_table.csv, results/drift_summary.json
- 2026-11-07T21:45Z | Phase 3 started: candidates C1/C2/C3 and selection rule pre-registered in LOG.md before any result; leakage table and drift summary being built in parallel. KB 02 results table replaced with verified ledger values | LOG.md, docs/kb/02_findings_first_pass.md
- 2026-11-07T21:39Z | Phase 2 AUDITED PASS (audit/2026-11-07-harness.md, 249 claims verified). DECISION pending with human: headline = ranking-quality gain (AUC/median rank/work saved), not top-500; honest backtest = train labels capped at train end. KB 02 first-pass table is superseded by results/claims_model.json; do not quote it | audit/2026-11-07-harness.md, results/claims_model.json
- 2026-11-07T21:23Z | Harness in src/model/ reproduces first-pass table (unaudited); sensitivity: top-500 gain over exploit-then-EPSS not robust (seed range, train-label horizon, second fold), possible post-hoc wording in descriptions; audit running | results/first_pass_repro.json, results/claims_model.json (all unverified)
- 2026-11-07T21:05Z | Step 0 done: rules/KB/interfaces read; Python 3.12 venv (.venv) and version lock src/model/requirements.lock. Heads-up for all: src/features.py on main (not ours) uses non-time-safe latest signals plus reference/product counts; model branch does NOT use it | src/model/requirements.lock | ASK data-engineering-db: do not feed src/features.py output to the model
- 2026-11-07T20:55Z | kb branch and team files created; sample schema docs/sample_scores_2026.csv (DUMMY) added | docs/ | 
- 2026-11-07T20:50Z | file created with initial plan | docs/kb/team/model-ranking.md |
