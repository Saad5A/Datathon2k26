# MISSION

You are the lead engineer for a 3-4 person student team (beginners at ML) competing in the Sheridan Datathon 2026 (Nov 7-8, Sheridan College), IBM track "Before the Breach". Build and finish the ENTIRE project end to end: analysis, model, top500.csv, web app, deployment, write-up, demo script, and Devpost/DEV text. Goal: win an award. Judging is Discovery 35% (non-obvious, evidence-backed finding), Data Use 25% (sound analysis, cleaned and questioned data, honest limits), Communication 25% (story clear in the first minute; charts and demo support it), Impact 15% (useful to a real security team, realistic next step). Optimize every decision against these. Never state a number in the write-up that was not produced by code you can rerun.

# TEAM SPLIT (updated)
Four teammates each own a branch (see docs/INTERFACES.md): feat/model-ranking (ML), feat/data-engineering-db (data/DB), feat/ui-dashboard (web), feat/triage-playbook-gemini (Gemini triage agent). Each person runs their own Claude Code agent and executes ONLY the phases for their branch: model-ranking = phases 1-5 and 7 plus the Granite embeddings in 6; data-engineering = data loaders/DB (supports 2-3); ui-dashboard = phase 8; triage-gemini = the explanation/playbook part of 6 (using Gemini, grounded on model reasons); packaging (phase 9) is shared. Stay inside your owned folders. Your branch prompt is PROMPT_<NAME>.md; this file is the shared context and rules.

# READ FIRST (all under ~/Working/datathon/)
- IBM/README.md and IBM/DATA_DICTIONARY.md (rules, benchmark, leakage warnings)
- IBM/data.zip (already unzipped at _probe/ibm/data/; do not modify originals)
- _probe/ibm/build.py, model1.py, model2.py (our first-pass backtest; reuse and clean up). bt.pkl and v_2021plus.pkl are caches.
- Sheridan Datathon -Opening.pdf (MLH sponsor prizes)

# THE TASK (from the README)
Rank vulnerabilities by likelihood of being exploited, using only what was known at the end of each CVE's snapshot_month. Judges check how many of our top 500 from scoreboard_2026.csv (72,670 CVEs, Jan-Sep 2026, not on KEV at snapshot) were later added to CISA KEV through Nov 4, 2026. Their baselines find 6 (EPSS), 7 (CVSS3), 8 (exploit code then EPSS) of 500. We must use at least one IBM technology (Granite models on Hugging Face, e.g. embeddings and an instruct model; watsonx.ai if we get an account). Submit top500.csv with ONE column: cve_id. Deliverables on Devpost: 2-3 min demo video, code repo, short write-up, links to outside data, and the top 500.

# WHAT WE ALREADY FOUND (2025 backtest: train on CVEs published 2024, test on Jan-Sep 2025; pool 35,280, 52 later-exploited; label = added to KEV after snapshot month-end within 12 months, capped at 2025-12-31)
| Approach | top500 | AUC | AvgPrec | median rank of exploited |
| CVSS3 | 6 | .73 | .006 | 7884 |
| EPSS | 8 | .71 | .031 | 3376 |
| exploit flag then EPSS | 19 | .77 | .047 | 2496 |
| assigner KEV-rate only | 13 | .75 | .011 | 6075 |
| HGB signals+assigner+text-LR score | 25 | .886 | .105 | 829 |
| HGB all + structured CVSS/CWE | 21 | .883 | .114 | 1103 |
| LEAKY: + n_affected_cpes (never use) | 27 | .913 | .132 | 421 |
Takeaways: (1) ranking-quality gain is real (AUC .77 to .89; exploited CVEs surface ~3x earlier), but the top-500 count gain is small and noisy (52 positives; one hit ~2%), so report ranges and never promise a score. (2) "assigner" (who issued the CVE; known at publish time) KEV history is the strongest new signal; all 52 test positives came from assigners with a prior KEV. (3) TF-IDF text model learned sensible phrases: "remote unauthenticated", "windows kernel", "sharepoint", "outlook", ".net framework". (4) Leakage is measurable: n_affected_cpes alone AUC .77; adding it adds hits. (5) 2026 DISTRIBUTION SHIFT: ~4k CVEs/month in 2025 vs 12-15k in Aug-Sep 2026; assigner mix changed (GitHub advisories 15% vs 5.6%, VulnCheck 9.3% vs 1.1%, Oracle 4.2% vs 0.7%, Chrome 4.0% vs 0.3%); 66-68% of Aug-Sep 2026 CVEs have no product list vs 30-40% in 2025; 25% of the 2026 pool is from assigners with no past KEV. A naive vendor score could flood the top 500 with Chrome/Microsoft. This shift is our best Discovery story.

# SPLIT POLICY (mentor advice, applied)
Never judge a model on data it trained on. Keep a held-out set that is only used to score. Because CVEs are time-ordered, use a TIME split, not a random 75/25 split (a random split lets the model peek at the future). Dev split: train on CVEs published in 2024 (65 positives), validate on 2025 Jan-Sep (52 positives). Decide the small set of candidate models BEFORE looking at validation results, to avoid fooling ourselves; any tuning uses cross-validation inside the training years only. Add a second rolling fold (train 2024-07..2025-03, test 2025-04..2025-09) and report both. Record the held-out numbers in LOG.md and freeze them. Only AFTER that, refit the chosen model on all labelled data (2024-2025) for the final 2026 predictions, because positives are scarce; state this clearly in the write-up and report the held-out numbers as the honest estimate.

# TEACH US (the team are ML beginners)
Create LEARNING.md in plain English, no jargon without definition, with a small example for each: what a row/feature/label is; why only ~0.15% of rows are positives and what that means; train vs validation and why a time split; overfitting; logistic regression; gradient-boosted trees; TF-IDF; embeddings; AUC, average precision, top-500 hits, median rank; what the leakage columns are and why they cheat. Also write a one-page "how to explain our model to a judge" crib sheet and likely judge questions with answers. Explain each phase briefly when you finish it.

# WATSONX.AI (IBM-recommended; mentors told us to use it)
We are signing up for the watsonx.ai free trial (Toronto region). Credentials will come as environment variables in a local .env file that MUST be in .gitignore and never committed or printed: WATSONX_APIKEY, WATSONX_URL, WATSONX_PROJECT_ID. Use the official ibm-watsonx-ai Python SDK and look up the CURRENT docs and available Granite model IDs (embedding and instruct) instead of guessing names. Use watsonx.ai for the Granite pieces (description embeddings, the plain-English explanations, the optional triage agent), batching requests, caching every response to disk, and respecting trial limits (estimate token/call usage first and tell me before spending a lot). Build a provider switch (WATSONX or LOCAL via Hugging Face ibm-granite models, or Colab per https://github.com/ibm-granite-community/granite-agent-cookbook) so the pipeline still runs if the trial is unavailable or runs out. The ranking model itself stays in scikit-learn so we control the time split and leakage rules. Optional cross-check only if time allows: run watsonx AutoAI on our feature table and report whether it agrees; never make it the main model. Document in the write-up exactly which IBM technologies were used and for what.

# TEAM OF SUBAGENTS (read CLAUDE.md and .claude/agents/ first)
You are the orchestrator. Do not do everything yourself: delegate to the subagents (data-engineer, modeler, ibm-integrator, webapp-builder, storyteller, auditor) and run independent work in parallel. Suggested flow: (1) data-engineer builds the harness; (2) auditor verifies it; (3) in parallel: modeler (candidate models + ablations), ibm-integrator (watsonx/Granite embeddings + grounded explanations), webapp-builder (skeleton fed by results JSON); (4) auditor reviews each in a fresh context, re-deriving numbers with a different code path; (5) fix, re-audit, loop until PASS; (6) storyteller writes from verified claims only; (7) auditor reviews the write-up and `python tools/check_claims.py` must exit 0. Nothing is published, quoted in the demo, or put in the app unless its claim is `verified`. Tell me when you are blocked or when an auditor FAIL cannot be fixed. Use the skills datathon-team-orchestration, evidence-first-verification and leakage-safe-backtest if they are available.

# PLAN (do in order; commit to git after each phase; keep a LOG.md of decisions and every result)
1. REPO + ENV: create ~/Working/datathon/ibm-before-the-breach/ (git init). Python venv, requirements.txt, Makefile or run_all.sh that reproduces everything from raw data. Check machine RAM/CPU first; read big CSVs with usecols/chunks.
2. BACKTEST HARNESS (reusable): time-safe feature builder; label function; rolling-origin evaluation (train 2024 -> test 2025; also 2024H2+2025H1 -> 2025Q3; and train 2025 -> test is not possible for 2026, so state that). Metrics: top-500 hits, also top-250 (matches the stricter 2026 cut, since the 2026 pool is ~2x larger), AUC, avg precision, median rank of exploited, and "work saved" = number of CVEs a team must fix to catch 50% of later-exploited, for CVSS vs EPSS vs ours. Bootstrap 95% intervals. Fixed seeds. Reproduce the table above first.
3. FEATURES (time-safe only): EPSS and 4 exploit flags at snapshot; assigner KEV rate/count computed with a RECENT window (e.g. last 24 months) and only from KEV rows added before the snapshot month; text signal (TF-IDF LR with out-of-fold stacking, then IBM Granite embeddings + logistic regression; compare); CVSS vector/CWE as an ABLATION only. PREFERRED FINAL MODEL = signals + assigner + text (it scored best AND avoids NVD fields filled in after attacks). Run a full ablation (drop each feature group) and a feature-importance view. Test on unseen-assigner CVEs. Handle blank epss. Keep models small and regularized (only ~65 train positives): logistic regression / shallow HGB; no huge tuning.
4. LEAKAGE AUDIT: a table of every column used and every column deliberately excluded (nvd_status, n_affected_cpes, n_references, blank-score patterns, references.csv news/threat-report links, affected_products availability) with the measured leak size (as above). This table goes in the write-up and the web app.
5. SHIFT-ROBUSTNESS: quantify 2026 vs 2025 drift (volume, assigner mix, missingness). Add a per-assigner cap/diversification rule in the final top 500 so no single assigner dominates; justify the cap by backtest (does it help or hurt?) and by the 2026 mix. Report the sensitivity.
6. IBM TECH (must be real, not decorative): use IBM Granite embedding model(s) from Hugging Face (ibm-granite) for descriptions, evaluate vs TF-IDF honestly (if it does not help, say so). Use a small Granite instruct model to write a 2-3 sentence plain-English "why this is high priority and what to do" for the top ~100 CVEs, grounded ONLY in that CVE's description and our model's top signals (no invented facts; label as AI-generated). Run CPU-friendly (batch, truncate, cache embeddings to disk; score candidates with the cheap model first and embed only the top ~20k). If a watsonx.ai account/API key becomes available, wire it as an option. Document exact model IDs.
7. FINAL PREDICTIONS: refit on all labelled 2024-2025 data per the SPLIT POLICY, score scoreboard_2026.csv using only its snapshot-month signals + description + assigner (join vulnerabilities.csv on cve_id), write top500.csv (single column cve_id, exactly 500 unique ids from the scoreboard). Also save top 5,000 with scores and reasons for the app. Validate the file programmatically.
8. WEB APP (deploy to a public URL; we will point our GoDaddy domain at it; Vultr VM or any free host; keep it simple and fast, precompute everything to JSON; a static site plus small API or pure static is fine): 
   - Landing: one chart that wins the first minute: "How many exploited vulnerabilities each ranking catches" (CVSS vs EPSS vs exploit-then-EPSS vs ours) from the backtest, plus the headline "work saved" number.
   - Fix-First list: ranked CVEs with score, key signals, filter by assigner/vendor/month, search by CVE id.
   - CVE detail page: signals, top contributing reasons, Granite plain-English summary, suggested action.
   - "Why 2026 is different" page: the shift charts (volume, assigner mix, missing product data).
   - Methodology and leakage page: columns used/excluded, backtest design, limits, confidence intervals.
   - Download top500.csv. Accessible, readable on a projector, dark/light safe.
9. PACKAGING: README.md (what/why/how to reproduce), WRITEUP.md (<=600 words: problem, approach, biggest finding, leakage, limits, impact), SOURCES.md (NIST NVD via fkie-cad mirror, CISA KEV, FIRST EPSS, t0sche/cvss-bt, MITRE CWE, IBM Granite model cards, any other), DEMO_SCRIPT.md (a 2:30 video script with exact shots and the first-60-seconds storyline), DEVTO_POST.md (draft of a DEV Writing Challenge post about the build, honest and practical), DEVPOST.md (paste-ready fields). Also generate presentation-ready PNG charts.

# HONESTY RULES (these also earn Data Use points)
- KEV is a proxy for "exploited"; a CVE not on KEV may still have been attacked.
- Small samples: report intervals; never claim certainty or a guaranteed score. The 2026 result may land anywhere in a wide range by luck.
- Do not use 2026 labels (we have none). Do not peek at scoreboard outcomes.
- If something fails or looks too good, investigate leakage before celebrating.

# CHECKPOINTS
- By about 6 pm Saturday: the backtest harness must reproduce the table above. If not, STOP and tell me so we can switch to the ElevenLabs track.
- By about 10 pm Saturday: final model, top500.csv, and a working local app.
- Sunday morning: deployment, write-up, video script, DEV post. Submit nothing yourself.

# WHAT YOU CANNOT DO FOR US (list these at the end with exact steps)
Record the demo video; create the Devpost submission and paste text; create IBM/watsonx and DEV accounts; register the GoDaddy domain (code MLHSD91) and set DNS to the deployed app; push to Entire/GitHub if credentials are needed; submit on Devpost. Also tell me which MLH prizes the finished project qualifies for (GoDaddy domain, DEV writing, Entire repo hosting, Vultr hosting, Gemini API only if used meaningfully; skip Solana) and the minimum extra work for each.

Work autonomously, keep a running task list, commit often, and give me a short status after each phase. Start with phase 1 and 2 now.
