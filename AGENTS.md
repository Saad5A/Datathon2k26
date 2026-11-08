# Project rules for ALL AI coding agents (Claude Code, Cursor, Copilot, Gemini CLI, Codex, any other). Read every session.

We are a beginner-ML student team building the IBM "Before the Breach" entry (see AGENT_PROMPT_IBM.md for the full mission). Winning depends on being CORRECT and HONEST, not just impressive. These rules override speed.

## Knowledge base
Before working, read `docs/kb/README.md` (index of shared facts, each tagged SOURCE / MEASURED-UNAUDITED / VERIFIED / UNKNOWN). Add new facts to it with tag and source; only the auditor sets VERIFIED.

## Coordination (mandatory; keeps four agents in sync)
Run `python tools/kb.py show` at the start of every session, before any task that depends on another branch, and after each phase: it prints every teammate's status, deliverables and ASKS. AFTER EVERY UPDATE (finished task, commit, changed assumption or contract, new blocker, new file others consume) update YOUR team file `docs/kb/team/<your-area>.md` (STATUS block, deliverable rows, changelog line) and run `python tools/kb.py publish <your-area> "message"`. Edit only your own team file. Areas: model-ranking, data-engineering-db, ui-dashboard, triage-playbook-gemini. Details: docs/kb/README.md.

## Non-negotiables
1. **No number without evidence.** Every figure in any write-up, slide, web page, video script or chat summary must come from a script we can rerun, and must be registered in `results/claims*.json` (see "Claims ledger"). If it is not registered AND verified, it does not get published.
2. **Nobody grades their own work.** Work is produced by one agent/role and checked by the `auditor` role in a fresh context (a fresh subagent, or a brand-new chat session that has not seen the producer's reasoning). The auditor re-derives key numbers with a DIFFERENT code path and tries to break conclusions. A claim is `verified` only after an audit report in `audit/` says so.
3. **Too good to be true = leakage until proven otherwise.** If validation AUC > 0.93 or top-500 hits jump suddenly, stop and hunt for leakage before celebrating.
4. **Time-safe only.** A feature for a CVE may use only information dated on or before the end of its snapshot month. Never use the excluded NVD fields (nvd_status, n_affected_cpes, n_references, blank-score patterns, references.csv news/threat links) as model features.
5. **We have no 2026 labels.** Never claim a 2026 accuracy. Claims about 2026 are limited to distributions, drift, and the predicted ranking itself.
6. **Report uncertainty.** Only ~52 positives in the 2025 test: always give intervals (bootstrap) and say a single hit is ~2%.
7. **Granite/LLM text is generated, not evidence.** Explanations may only restate facts present in that CVE's own record and our model's signals, and are labelled AI-generated.
8. **Say "I don't know"** and mark things `unverified` rather than guessing. Do not invent library functions, model IDs, columns or statistics: check docs/data first.
9. **Secrets:** never commit or print API keys; `.env` is gitignored.

## Protected files (any agent, any tool: read before editing)
These are audited. Do NOT edit, overwrite, regenerate or delete them unless the human owner of `feat/model-ranking` asks you to in this session:
`results/top500.csv`, `results/scores_2026.csv`, `results/signal_vocabulary.json`, `results/backtest_summary.json`, `results/leakage_table.csv`, `results/drift_summary.json`, every `results/claims*.json` (only the auditor may change `status`/`verified_by`), everything under `audit/`, `JUDGE_QA.md`, `docs/writeup_model.md`, `LEARNING.md`, `LOG.md` (append only).
- Work on your OWN branch (e.g. `feat/ibm-granite`) and open a PR into `feat/model-ranking`; do not push directly to `feat/model-ranking`.
- New results go in NEW files and are registered as `unverified` claims. Never call a number "verified", a "gain" or an "improvement" until an audit report in `audit/` says so.
- Never call output "Granite" or "AI-generated" unless an IBM Granite model actually produced it (check the `provider`/`model_id` fields).
- Granite adoption is decided ONLY by the pre-registered test in `src/model/granite.py` (LOG.md "PRE-REGISTRATION, Granite text and per-assigner cap"), on all rows. Subset comparisons are exploratory.

## Claims ledger
`results/claims*.json` (each branch writes its own file, e.g. `results/claims_model.json`): `{ "<id>": {"text": "...", "value": <number>, "unit": "count|fraction|percent|ratio", "source_script": "src/...", "output_file": "results/...", "status": "unverified|verified", "verified_by": "audit/<report>.md"} }`
Scripts write their outputs to `results/`, and the producing agent registers claims as `unverified`. Only the `auditor` flips status to `verified`.
Run `python tools/check_claims.py WRITEUP.md DEVPOST.md DEMO_SCRIPT.md DEVTO_POST.md` before anything is published: it fails if a document contains a number that no verified claim supports.

## Branches
Four branches own separate folders (docs/INTERFACES.md). Stay in your lane; shared files change only via small PRs. Commit often to YOUR branch, pull main regularly, never force-push.

## Team roles (tool-neutral)
Roles are plain Markdown files in `.claude/agents/` (data-engineer, modeler, ibm-integrator, webapp-builder, storyteller, auditor). Any tool can use them:
- If your tool supports subagents (Claude Code), spawn them, parallelize independent work, and send every deliverable to the auditor.
- If not (Cursor, Copilot, Gemini CLI, Codex, ...), open a SEPARATE chat/session per role and paste that role file as its instructions. The auditor must always be a fresh session that only sees the code, data paths and claim list, never the producer's conclusions.
Loop until the auditor passes a deliverable or reports blockers to the human. Keep LOG.md updated (decision, why, result, who).

## Tool notes (Windows, Mac, Linux)
Helpers are Python so they run anywhere: use `python` (or `py` on Windows). No bash is required. Paths in docs use forward slashes. If your tool cannot run terminal commands, ask the human to run `python tools/kb.py show` and paste the output, and to run `python tools/kb.py publish <area> "message"` after you edit your team file in the kb worktree.
