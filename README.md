# Datathon2k26: Before the Breach

[TAGLINE]

This is our student entry for the IBM track "Before the Breach" at Sheridan Datathon 2026. We rank the 72,670 CVEs (published software vulnerabilities) on the 2026 scoreboard by how likely each is to be added to CISA's Known Exploited Vulnerabilities list (KEV). Each CVE is scored using only what was known at the end of its snapshot month, apart from today's description and assigner fields. The judged submission is `results/top500.csv`.

The score orders the list. It is not a probability of attack. The full write-up is in `docs/writeup_model.md`, and likely judge questions are answered in `JUDGE_QA.md`.

## What we found
- **A hidden leak in NIST fields.** All 52 later KEV-listed CVEs in our 2025 test had NIST status "Analyzed", a product list, and a filled CVSS3 score and CWE. Among the other test CVEs, only 50.1% were "Analyzed" and 64.9% had a product list. We do not use these fields.
- **The first-pass "win" was inflated.** Its 25 vs 18-19 top-500 result came from training labels that overlapped the test period and from seed luck. With time-safe labels and a pre-registered test, our model roughly ties "exploit code first, then EPSS" in fold 1 (22 vs 18) and loses in fold 2 (11 vs 15). Its AUC (how well it orders the whole list) is higher in every fold and seed. The gain is borderline, though: for seed set 0 the paired interval includes zero. We do not claim to beat the baselines at the judges' metric.
- **2026 looks different.** There are about twice as many rows as in the same 2025 months (72,670 vs 35,280). GitHub advisories rose from 5.6% to 15.0% of rows and VulnCheck from 1.1% to 9.3%. In August-September, 66-68% of CVEs have no product list.
- **IBM Granite was adopted with no measurable gain.** A pre-registered rule added a Granite text score because its mean AUC was within a pre-set margin of the base model (0.871 vs 0.870). Granite alone scored lower (0.837).
- **We make no 2026 accuracy claim,** because we have no 2026 labels.

## IBM technology
We use IBM's Granite multilingual embedding model, run on the open weights locally and on a subset through IBM watsonx.ai. Its text score is part of the final model. Details, model IDs and evidence are in `docs/ibm.md`.

## How to reproduce
1. Create a virtual environment with `python3.12` and install the locked versions:
   ```
   python3.12 -m venv .venv
   .venv/bin/pip install -r src/model/requirements.lock
   ```
2. Unzip the IBM datathon data into `data/`, or point the `IBM_DATA_DIR` environment variable at the folder that holds `known_exploited.csv` and the other files.
3. Run the whole pipeline:
   ```
   .venv/bin/python run_all.py
   ```
   This rebuilds every file in `results/`, stopping at the first failure. `python run_all.py --from <step>` resumes from a step.

The Granite step runs only if `data_cache/granite_embeddings.parquet` exists. That file is produced by `cloud/embed_granite.py` (it needs `sentence-transformers` or `ibm-watsonx-ai`); see `cloud/README.md`. Without it, the pipeline keeps the TF-IDF-only files.

## Repo map
- `src/model/`: the model code: pool and labels, checks, candidate models, assigner cap, leakage, drift, final scoring and Granite test. `src/model/FEATURES.md` documents every feature.
- `results/`: the outputs.
  - `top500.csv`: the submission (one column, `cve_id`).
  - `scores_2026.csv`: every scoreboard CVE with score, rank, priority tier and up to three reasons.
  - `signal_vocabulary.json`: what each reason signal means.
  - `backtest_summary.json`: backtest metrics for our model and the baselines, with claim ids.
  - `leakage_table.csv`: every column considered, whether we use it, and its solo AUC.
  - `drift_summary.json`: how 2026 differs from 2025.
  - `model_candidates.json`: the pre-registered candidate comparison.
  - `assigner_cap.json`: the per-assigner cap test.
  - `granite_comparison.json`: the pre-registered Granite test.
  - `first_pass_repro.json`: the reproduced first pass and its sensitivity checks.
  - `reverse_time.json`: a reverse-time check. It is not a time-safe evaluation and is not used as evidence.
  - `claims*.json`: the claims ledger.
  - `*.meta.json`: run provenance (commit, code hashes, versions).
- `audit/`: independent audit reports. `audit/scratch/` holds the auditors' own scripts.
- `cloud/`: Granite embedding scripts and the step-by-step guide (`cloud/README.md`).
- `docs/`: the write-up (`writeup_model.md`), IBM details (`ibm.md`) and branch interfaces (`INTERFACES.md`). The shared knowledge base `docs/kb/` lives on the `knowledge-base` branch.
- `LOG.md`: the decision log, including pre-registrations.
- `LEARNING.md`: a plain-English guide for beginners.
- `JUDGE_QA.md`: answers to likely judge questions.
- `tools/`: `check_claims.py` and the knowledge-base helper `kb.py`.

## How the numbers are checked
- Every number we publish is registered in `results/claims*.json`, with the script and output file that produced it.
- A separate auditor, working in a fresh context, re-derives the numbers with its own code and only then marks a claim `verified`. The reports are in `audit/`.
- `python3 tools/check_claims.py <files>` fails if a document contains a number that no verified claim supports.

## Team branches
- `feat/model-ranking`: this branch. The ranking model, backtest, leakage and drift analysis, Granite test, and audits.
- `feat/ui-dashboard`: a web dashboard (`dashboard/`), merged into `main` through pull requests.
- `feat/triage-playbook-gemini`: a Gemini triage-playbook pipeline and a Streamlit presentation app.
- `feat/ibm-granite`: a teammate's Granite and watsonx.ai work (Colab embedding path and Granite explanations).
- `feat/data-engineering-db`: listed in `docs/INTERFACES.md`. We found no such branch on the remote.

## Limits
- KEV is a proxy for "exploited". It lists confirmed attacks only, so a CVE not on KEV may still have been attacked.
- Our 2025 test has only 52 positives, so one hit is about 2%. We always report ranges.
- Descriptions are today's text, not the text at the snapshot month. We mask known exploitation wording, but other later edits cannot be checked.
- We have no 2026 labels and make no claim about 2026 accuracy.
