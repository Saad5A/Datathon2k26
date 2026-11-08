> **Note (2026-11-08, feat/model-ranking):** `main` had replaced this file with the dashboard contract, now kept unchanged as [`INTERFACES_dashboard.md`](INTERFACES_dashboard.md). The two disagree on the scores file (location `results/` vs `outputs/`; 11 vs 17 columns; `reasons` fields and signal names). The model branch delivers the contract below, which is verified. Team to reconcile; until then the dashboard must map the delivered `results/scores_2026.csv`.

# Branch ownership and interfaces (model <-> Gemini sections LOCKED 2026-11-07 15:30; data and UI teammates still to confirm)

| Branch | Owner area | Owns (only edit these) | Produces |
|---|---|---|---|
| feat/model-ranking | ML ranking | `src/model/`, `cloud/`, `results/`, `audit/` | scores, top500.csv, backtest + drift + leakage results |
| feat/data-engineering-db | Data / DB | `src/data/`, `db/`, `data_cache/` schemas, `docs/features.md` | clean loaders, DB tables, shared base tables |
| feat/ui-dashboard | Web UI | `web/` | the public app |
| feat/triage-playbook-gemini | Gemini triage agent | `src/triage/` | grounded fix playbooks per CVE |

Shared and edited only via small PRs to main: `CLAUDE.md`, `tools/`, `docs/INTERFACES.md`, `LOG.md` (append-only, prefix lines with your branch name).

## 1. Model -> everyone (files in `results/`)
- `scores_2026.csv` (all 72,670 scoreboard CVEs, i.e. not on the KEV list at their snapshot month; not guaranteed unexploited): `cve_id, published, snapshot_month, assigner, score, rank, in_top500, priority, epss, any_public_exploit, reasons`. `score` is a RANKING score, not a calibrated probability (about 0.15% of CVEs are later exploited), so the UI and Gemini must say "priority score"/"rank", never "X% chance of exploit". `priority` is a fixed rule computed here, not by an LLM: P0 = rank 1-100, P1 = rank 101-500, P2 = everything else (thresholds proposed; team to confirm). `reasons` is a JSON string: a list of up to 3 `{"signal": "assigner_kev_history", "value": 0.07, "direction": "up"}` objects. Signals are named from a fixed vocabulary in `results/signal_vocabulary.json`. The triage agent and the UI may use ONLY these fields as facts about the model.
- `top500.csv`: single column `cve_id` (the judged submission).
- `backtest_summary.json`: `{ "<method>": {"top500":..,"top250":..,"auc":..,"avg_precision":..,"median_rank":..,"ci95":{"top500":[lo,hi]}} }` for methods cvss3, epss, exploit_then_epss, assigner_only, ours (+ ablations); plus `pool_size`, `n_positives`, `split` description.
- `drift_summary.json`: monthly volume, assigner mix 2025 vs 2026, missing-data rates.
- `leakage_table.csv`: `column, used_in_model (yes/no), solo_auc, reason`.
- `claims_model.json`: claims ledger entries (see CLAUDE.md).

## 2. Data -> model
Until the data branch delivers, the model branch reads raw CSVs and keeps its own feature code in `src/model/`. When delivered, the model switches to `data_cache/cve_base.parquet` (one row per CVE: `cve_id, published, assigner, description, cvss3_score, attack_vector, ... cwe_ids`) and `data_cache/kev.parquet` (`cve_id, date_added, vendor`). Data branch: never reshape or drop rows silently; document every cleaning step in `docs/features.md`. If you load a database, keep `scores_2026.csv` loadable into it as table `cve_scores`.

## 3. Triage (Gemini) rules
Input per CVE: the NVD description, `reasons`, `score`, `rank`, assigner. Output: a short playbook labelled AI-generated. Must not invent affected versions, patches, CVE facts or URLs. Grounding check: every product/version/ID/term in the output must appear in the input; otherwise discard. IBM technology must still be genuinely used elsewhere (Granite embeddings in the model branch): do not remove it.

## 4. UI rules
Render every number from `results/*.json|csv`; never hardcode statistics; show only claims whose status is `verified` in the demo build.

## 5. Display metadata (owner: data branch; model branch does NOT duplicate it)
Gemini and the UI also need NVD fields for display. The data branch provides one row per CVE keyed by `cve_id` (`data_cache/cve_display.parquet` and/or a DB view): `description, cvss3_score, cvss3_severity, attack_vector, cwe_ids, cwe_names, vendor, product, references` (list of `{url, tags}`; patch/advisory links for citing). These are for DISPLAY only; the model does not use CVSS/CWE/product as features. Many 2026 CVEs have no product list or blank CWE/CVSS (about two thirds of Aug-Sep 2026 CVEs lack products): nulls must stay null, and `vendor` may fall back to `assigner` only if labelled as such. A joined export `results/top500_enriched.csv` = scores + display metadata for the top 500 (built by the data branch from our files).

## 6. Gemini output rules (owner: triage branch)
Four sections per CVE: Plain-English impact, Immediate workaround, Remediation action, Urgency. Urgency comes from `priority` (do not let the LLM decide it); it may only explain it using `reasons`. Impact is grounded in the description. Workaround/remediation: only generic, standard mitigations or links present in `references`; never invent patch versions, product names, URLs or CVE facts; if no patch reference exists, say "no vendor patch reference in our data; check the vendor advisory". Everything is labelled AI-generated; run the grounding check from section 3.

## 7. Decisions log
- LOCKED (model + triage branches): priority tiers P0 = rank 1-100, P1 = rank 101-500, P2 = rest, computed by the model branch; Gemini treats `priority` as ground truth and explains it from `reasons`.
- LOCKED: UI and prompts say "Priority Score" / "Rank", never probability or "% chance".
- LOCKED: Gemini falls back to `assigner` when vendor is null, handles missing CWE/CVSS, never invents patch versions or URLs; if no patch reference exists it says so and gives standard mitigations only.
- LOCKED: `results/top500_enriched.csv` is built by the triage teammate (join of top 500 from `scores_2026.csv` with `cve_display.parquet` or raw `vulnerabilities.csv` + `references.csv`). Display fields are never used as model features.
- OPEN: data and UI teammates confirm sections 2 and 4. `docs/sample_scores_2026.csv` is a DUMMY file (fake ids, fake values) so others can code against the schema before real scores exist; never put it in results/.
