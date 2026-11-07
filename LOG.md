# Decision log (append-only; prefix lines with your branch name)

Format: `branch | local time | decision or event | why | result | who`

## Task and checkpoints (feat/model-ranking)
Rank `scoreboard_2026.csv` by likelihood of exploitation using only what was known at each CVE's snapshot month; judges count our top 500 later added to KEV through 2026-11-04. Judging: Discovery 35, Data Use 25, Communication 25, Impact 15. Checkpoints: harness reproduces the first-pass table and is audited by about 6 pm Sat (else fallback decision with the human); final model and files by about 10 pm Sat.

## Entries
- feat/model-ranking | 2026-11-07 16:05 | Python 3.12 venv in `.venv`, versions locked in `src/model/requirements.lock` | Homebrew default is 3.15 with no ML packages; only packages already in requirements.txt installed; pytest not in the manifest, so checks are plain asserts | env works | orchestrator
- feat/model-ranking | 2026-11-07 16:05 | Repaired kb worktree link with `git worktree repair ../Datathon2k26-kb` | Worktree was registered under another machine's path, so `kb.py publish` failed and `kb.py show` could not pull | publish works | orchestrator
- feat/model-ranking | 2026-11-07 16:05 | Do not use `src/features.py` (main) as model input | `latest_exploit_signals` takes the latest month rather than the snapshot month, and it builds reference and product counts, which are on the excluded list | model branch keeps its own code in `src/model/` | orchestrator
- feat/model-ranking | 2026-11-07 16:05 | 2025 test fold is not truly held out: the first pass compared many variants on it | Split policy says candidates are fixed before looking at validation; that was not possible for the first pass | must be disclosed in the write-up; next step is to choose how to get a cleaner estimate | orchestrator
