# Team file: ui-dashboard  (web dashboard)
Only the agent for this area edits THIS file. Read the other three with `tools/kb.sh show`.

<!-- STATUS-START -->
STATUS: not started
PHASE: scaffold the app against docs/sample_scores_2026.csv (DUMMY data)
LAST_UPDATED: 2026-11-07T20:50Z
BLOCKED_ON: none
NEXT: Build landing chart page and fix-first list from the sample schema
ASKS: model-ranking: tell me when real results/*.json exist; triage-playbook-gemini: playbook file location and format
<!-- STATUS-END -->

## 1. Mission and owned paths
Build and deploy the public web app: first-minute backtest chart, fix-first list, CVE detail pages (with the Gemini playbook), 2026-shift page, methodology and leakage page, top500 download. Point the GoDaddy domain (code MLHSD91) at it.

Owned paths (edit only these; shared files change via small PRs): `web/`

## 2. Deliverables
| Item | Path | Status | Consumers |
|---|---|---|---|
| landing chart: ours vs CVSS vs EPSS vs exploit-then-EPSS with intervals | web/ | not started | judges |
| fix-first list with search and assigner filter | web/ | not started | judges |
| CVE detail page with signals and AI-generated playbook (labelled) | web/ | not started | judges |
| why-2026-is-different page | web/ | not started | judges |
| methodology and leakage page | web/ | not started | judges |
| deployed public URL and domain | web/ | not started | everyone |

## 3. What I need from others
| Need | From | Status |
|---|---|---|
| results/*.json and scores_2026.csv | model-ranking | waiting |
| results/top500_enriched.csv and per-CVE playbooks | triage-playbook-gemini | waiting |
| display metadata / DB | data-engineering-db | waiting |
| hosting choice and domain DNS | human | open |

## 4. Contracts I promise or rely on
- docs/INTERFACES.md section 4: render every number from results files; never hardcode statistics; show only claims with status verified in the demo build; say "Priority Score"/"Rank", never probability or % chance; label Gemini text AI-generated.

## 5. Facts and decisions others must know
- Use docs/sample_scores_2026.csv (DUMMY data) to build against the schema until real scores exist; never ship dummy data.

## 6. Blockers and risks
- (none yet)

## 7. Changelog (append-only, newest first; format: YYYY-MM-DDTHH:MMZ | what changed | files | DECISION/ASK tag if any)
- 2026-11-07T20:50Z | file created with initial plan | docs/kb/team/ui-dashboard.md |
