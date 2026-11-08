# Team file: data-engineering-db  (data / database)
Only the agent for this area edits THIS file. Read the other three with `python tools/kb.py show`.

<!-- STATUS-START -->
STATUS: not started
PHASE: waiting on confirmation of INTERFACES sections 2 and 4
LAST_UPDATED: 2026-11-07T20:50Z
BLOCKED_ON: none
NEXT: Build cve_display.parquet (description, CVSS, vendor/product, CWE, references; nulls stay null)
ASKS: model-ranking: tell me when real results/scores_2026.csv is ready; model-ranking and ui: confirm INTERFACES sections 2 and 4
<!-- STATUS-END -->

## 1. Mission and owned paths
Own the data loaders and database: clean, documented base tables from the raw IBM files, and display metadata for the dashboard and Gemini. Never silently drop or reshape rows; document every cleaning step in docs/features.md.

Owned paths (edit only these; shared files change via small PRs): `src/data/`, `db/`, `data_cache/` schemas, `docs/features.md`

## 2. Deliverables
| Item | Path | Status | Consumers |
|---|---|---|---|
| cve_base.parquet (one row per CVE: cve_id, published, assigner, description, cvss3_score, attack_vector, ..., cwe_ids) | data_cache/cve_base.parquet | not started | model (optional) |
| kev.parquet (cve_id, date_added, vendor) | data_cache/kev.parquet | not started | model |
| cve_display.parquet (description, cvss3_score, cvss3_severity, attack_vector, cwe_ids, cwe_names, vendor, product, references as list of {url, tags}); nulls stay null | data_cache/cve_display.parquet | not started | triage, ui |
| database loading of results/scores_2026.csv as table cve_scores | db/ | not started | ui, triage |
| feature/cleaning documentation | docs/features.md | not started | model, auditor |

## 3. What I need from others
| Need | From | Status |
|---|---|---|
| results/scores_2026.csv (real file; sample schema in docs/sample_scores_2026.csv) | model-ranking | waiting |
| Decision on database (Postgres/Tiger Data or other) and hosting | data teammate | open |

## 4. Contracts I promise or rely on
- docs/INTERFACES.md section 5: display fields are for DISPLAY only and never used as model features. Many 2026 CVEs lack product lists/CWE/CVSS: keep nulls; vendor may fall back to assigner only if labelled so.

## 5. Facts and decisions others must know
- NVD files are today's versions (leak-prone). See docs/kb/01_data_guide.md and 06_pitfalls.md.

## 6. Blockers and risks
- (none yet)

## 7. Changelog (append-only, newest first; format: YYYY-MM-DDTHH:MMZ | what changed | files | DECISION/ASK tag if any)
- 2026-11-07T20:50Z | file created with initial plan | docs/kb/team/data-engineering-db.md |
