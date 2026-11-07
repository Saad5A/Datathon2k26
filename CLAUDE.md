# Project rules (read every session)

We are a beginner-ML student team building the IBM "Before the Breach" entry (see AGENT_PROMPT_IBM.md for the full mission). Winning depends on being CORRECT and HONEST, not just impressive. These rules override speed.

## Non-negotiables
1. **No number without evidence.** Every figure in any write-up, slide, web page, video script or chat summary must come from a script we can rerun, and must be registered in `results/claims.json` (see "Claims ledger"). If it is not registered AND verified, it does not get published.
2. **Nobody grades their own work.** Work is produced by one subagent and checked by the `auditor` subagent in a fresh context. The auditor re-derives key numbers with a DIFFERENT code path and tries to break conclusions. A claim is `verified` only after an audit report in `audit/` says so.
3. **Too good to be true = leakage until proven otherwise.** If validation AUC > 0.93 or top-500 hits jump suddenly, stop and hunt for leakage before celebrating.
4. **Time-safe only.** A feature for a CVE may use only information dated on or before the end of its snapshot month. Never use the excluded NVD fields (nvd_status, n_affected_cpes, n_references, blank-score patterns, references.csv news/threat links) as model features.
5. **We have no 2026 labels.** Never claim a 2026 accuracy. Claims about 2026 are limited to distributions, drift, and the predicted ranking itself.
6. **Report uncertainty.** Only ~52 positives in the 2025 test: always give intervals (bootstrap) and say a single hit is ~2%.
7. **Granite/LLM text is generated, not evidence.** Explanations may only restate facts present in that CVE's own record and our model's signals, and are labelled AI-generated.
8. **Say "I don't know"** and mark things `unverified` rather than guessing. Do not invent library functions, model IDs, columns or statistics: check docs/data first.
9. **Secrets:** never commit or print API keys; `.env` is gitignored.

## Claims ledger
`results/claims*.json` (each branch writes its own file, e.g. `results/claims_model.json`): `{ "<id>": {"text": "...", "value": <number>, "unit": "count|fraction|percent|ratio", "source_script": "src/...", "output_file": "results/...", "status": "unverified|verified", "verified_by": "audit/<report>.md"} }`
Scripts write their outputs to `results/`, and the producing agent registers claims as `unverified`. Only the `auditor` flips status to `verified`.
Run `python tools/check_claims.py WRITEUP.md DEVPOST.md DEMO_SCRIPT.md DEVTO_POST.md` before anything is published: it fails if a document contains a number that no verified claim supports.

## Branches
Four branches own separate folders (docs/INTERFACES.md). Stay in your lane; shared files change only via small PRs. Commit often to YOUR branch, pull main regularly, never force-push.

## Team (subagents in .claude/agents/)
data-engineer, modeler, ibm-integrator, webapp-builder, storyteller, auditor. The main agent orchestrates: parallelize independent work, send every deliverable to the auditor, loop until the auditor passes it or reports blockers to the human. Keep LOG.md updated (decision, why, result, who).
