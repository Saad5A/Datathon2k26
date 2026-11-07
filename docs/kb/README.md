# Knowledge base (all agents: read this index first, every session)

Shared facts for the Sheridan Datathon 2026 IBM-track project. Keep it short, accurate and sourced.

## Reliability tags (every fact carries one)
- **[SOURCE]** stated in an official document (path or URL given). Trust, but still check if it matters to a number we publish.
- **[MEASURED-UNAUDITED]** computed by our first-pass scripts (`_probe/ibm/*.py`). Plausible, NOT yet independently verified. Do not publish until the auditor verifies and the claim is registered.
- **[VERIFIED]** re-derived by the auditor (audit report path given).
- **[UNKNOWN]** we do not know yet. Never fill the gap from memory; ask the human.

## Files
| File | What |
|---|---|
| 00_event_and_rules.md | Event, judging, IBM track rules, benchmark, submission, MLH prizes |
| 01_data_guide.md | The IBM data files, columns, quirks, and which fields leak |
| 02_findings_first_pass.md | What our probes found (numbers, tagged), including known caveats |
| 03_primer.md | Plain-English glossary: security terms and ML terms |
| 04_decisions.md | Decisions made, why, and by whom (links to INTERFACES.md) |
| 05_ibm_tech.md | IBM technologies, links, what we plan to use, what must be looked up |
| 06_pitfalls.md | Known traps in the data and in our process |
| 07_open_questions.md | Unknowns and who can answer |
| team/model-ranking.md, team/data-engineering-db.md, team/ui-dashboard.md, team/triage-playbook-gemini.md | One status file per teammate/agent: status, deliverables, needs, asks, changelog (see Coordination protocol) |

## Update protocol
1. Append, do not rewrite history: add the fact, its tag and source; if you change one, note the change under "Changelog" at the bottom of that file with date and your branch.
2. Never promote a tag yourself: only the auditor sets [VERIFIED].
3. If a fact here conflicts with raw data or a document, trust the source, fix the KB, and tell the human.
4. Edit via small commits on your own branch; add new facts to the file that owns the topic.

_Created 2026-11-07 by the model-ranking planning session._

## Coordination protocol (the `knowledge-base` branch is the shared bus)
Team files live on the `knowledge-base` git branch, checked out in a sibling worktree so your feature branch is never disturbed. One helper does everything:
- `tools/kb.sh show` : pull latest and print the STATUS block of all four team files. RUN THIS at the start of every session, before starting anything that depends on another branch, and after finishing each phase.
- `tools/kb.sh show <area>` : print one full team file.
- `tools/kb.sh sync` : update the worktree and print its path. Edit YOUR team file inside that path (`docs/kb/team/<area>.md`) and nothing else.
- `tools/kb.sh publish <area> "short message"` : commit and push only your team file.
**After EVERY update** (a finished task, a commit, a changed assumption or contract, a new blocker, a new file others will consume), update your team file (STATUS block, deliverable rows, a changelog line) and publish it. If you need something from another branch, add it to ASKS and to "What I need" in YOUR file; check the other files' ASKS for lines addressed to you. Never edit another area's file. Tag cross-team decisions `DECISION` in your changelog and tell the human so they are promoted to 04_decisions.md and docs/INTERFACES.md.
Areas: model-ranking, data-engineering-db, ui-dashboard, triage-playbook-gemini.
