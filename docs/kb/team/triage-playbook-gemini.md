# Team file: triage-playbook-gemini  (Gemini remediation agent)
Only the agent for this area edits THIS file. Read the other three with `python tools/kb.py show`.

<!-- STATUS-START -->
STATUS: on track
PHASE: building top500_enriched.csv join script and grounded Gemini prompt
LAST_UPDATED: 2026-11-07T20:50Z
BLOCKED_ON: none
NEXT: Finish the join against the sample schema, then wire real scores when available
ASKS: model-ranking: ping when real scores_2026.csv exists; ui-dashboard: agree playbook file location and format
<!-- STATUS-END -->

## 1. Mission and owned paths
Use Gemini to generate, per CVE, four grounded sections: plain-English impact, immediate workaround, remediation action, urgency explanation (urgency tier comes from our priority field, not from Gemini). Also builds results/top500_enriched.csv.

Owned paths (edit only these; shared files change via small PRs): `src/triage/`, results/top500_enriched.csv (builder)

## 2. Deliverables
| Item | Path | Status | Consumers |
|---|---|---|---|
| top500_enriched.csv = top 500 from scores_2026.csv joined with display metadata | results/top500_enriched.csv | in progress | ui |
| grounded Gemini prompt with guardrails | src/triage/ | in progress | ui |
| playbooks per CVE (cached, labelled AI-generated) | results/playbooks.json (proposed) | not started | ui |
| grounding checker (every product/version/ID/term in output must appear in input) | src/triage/ | not started | auditor |

## 3. What I need from others
| Need | From | Status |
|---|---|---|
| results/scores_2026.csv (real file; schema in docs/sample_scores_2026.csv) | model-ranking | waiting |
| cve_display.parquet (or raw vulnerabilities.csv + references.csv until then) | data-engineering-db | waiting |
| Gemini API key and current model name (look up, do not guess) | human teammate | open |

## 4. Contracts I promise or rely on
- LOCKED with model-ranking (docs/INTERFACES.md section 7): priority tiers P0 rank 1-100, P1 101-500, P2 rest are ground truth; Gemini explains using the reasons field. UI and prompts say "Priority Score"/"Rank". Fall back to assigner when vendor is null; handle missing CWE/CVSS; never invent patch versions or URLs; if no patch reference exists, say so and give standard mitigations only.

## 5. Facts and decisions others must know
- MLH Best Use of Gemini API is a possible extra prize. IBM technology stays in the model branch (Granite): do not replace it.

## 6. Blockers and risks
- (none yet)

## 7. Changelog (append-only, newest first; format: YYYY-MM-DDTHH:MMZ | what changed | files | DECISION/ASK tag if any)
- 2026-11-07T20:50Z | file created with initial plan | docs/kb/team/triage-playbook-gemini.md |
