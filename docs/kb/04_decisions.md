# Decisions log (append only)

| Date | Decision | Why | Source |
|---|---|---|---|
| 2026-11-07 | Team enters the IBM track (not ElevenLabs/NASA/Tangerine) | Team preference; we measured real signal in a quick backtest; fallback is ElevenLabs if the harness is not reproduced by about 6 pm Saturday | planning chat |
| 2026-11-07 | Time-based split: train on 2024 snapshots, validate on 2025-01..09; second rolling fold; candidates fixed before looking at validation; refit on all labelled data for 2026 | Mentor advised a held-out set; a random split would leak the future | AGENT_PROMPT_IBM.md |
| 2026-11-07 | Preferred final model: signals (EPSS, exploit flags) + recent-window assigner KEV history + text score; avoid NVD analysis fields | Best first-pass result and avoids fields filled in after attacks | 02 |
| 2026-11-07 | Cap how many top-500 slots one assigner may take; justify by backtest | 2026 mix shifted toward assigners such as Chrome admin and GitHub | 02 |
| 2026-11-07 | IBM tech = Granite embeddings via watsonx.ai (or local/Colab fallback), owned by the model branch; watsonx training/AutoAI use is optional | IBM track requires real IBM tech; mentors recommend watsonx.ai | PROMPT_MODEL_RANKING.md |
| 2026-11-07 | Four branches: feat/model-ranking, feat/data-engineering-db, feat/ui-dashboard, feat/triage-playbook-gemini; contracts in docs/INTERFACES.md | Parallel work | INTERFACES.md |
| 2026-11-07 | Priority tiers P0 rank 1-100, P1 101-500, P2 rest, computed by the model branch; UI/Gemini say "Priority Score"/"Rank", never probability | Scores are not calibrated; base rate about 0.15% | INTERFACES.md section 7 (locked with Gemini teammate) |
| 2026-11-07 | Every published number must be a verified claim; auditor is independent | Prevent hallucination and unsupported conclusions | CLAUDE.md |
