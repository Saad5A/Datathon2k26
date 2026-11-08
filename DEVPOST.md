# Devpost fields (paste-ready)

**Project name:** PancakeSec

**Tagline:** [TAGLINE]

---

## Inspiration
Security teams cannot patch every published software flaw (CVE), and many rank them by severity score (CVSS), which says how bad an attack could be, not whether anyone will attack. IBM's "Before the Breach" track asked the question teams actually face: what do we fix first? We wanted an answer that would hold up when someone checked our work, so we treated every exciting result as a possible mistake until it survived an independent audit.

## What it does
PancakeSec ranks the 72,670 CVEs on the 2026 scoreboard by how likely each is to be added to CISA's Known Exploited Vulnerabilities list (KEV), using only what was known at the end of each CVE's snapshot month, apart from the description text and assigner, which are today's values. The score is a ranking, not a chance of attack. The top 100 form tier P0 and the next 400 form tier P1; each CVE lists up to three "reasons", the signals that moved its score most. No assigner (the organisation that published the CVE) gets more than 50 of the top 500.

Along the way we found a hidden leak. In our 2025 backtest, all 52 CVEs later added to KEV had NIST status "Analyzed", against only 50.1% of the other test CVEs; 64.9% of the others had a product list, against all 52. The organisers' README notes that NIST reviews attacked CVEs first, so these fields partly record that an attack was already noticed. On its own, the product count scores a higher AUC than EPSS (0.767 vs 0.707; the intervals overlap). AUC is the chance that a random exploited CVE is ranked above a random non-exploited one; EPSS is a public score for how likely a CVE is to be exploited soon. A model that uses these fields looks strong in a backtest but would lean on something new CVEs do not have yet, so we left them out.

A web dashboard shows the ranked queue (as a 3D pancake stack or a table), each CVE's strongest reason, similar CVEs found with a separate, smaller Granite embedding model (retrieval only, not used for ranking), an evidence page with the backtest and its limits, and a download of `top500.csv`.

## How we built it
- **Data, all from the organisers' files.** Used: `epss`, `exploitdb`, `metasploit`, `nuclei` and `poc_github` at the snapshot month; `assigner`, `published` and `description` from `vulnerabilities.csv`, with exploitation wording ("actively exploited", "CISA", "KEV" and similar) masked; `date_added` from `known_exploited.csv`, counting only rows before the snapshot month for features; `in_kev` only to drop CVEs already on KEV. Excluded: `nvd_status`, `n_affected_cpes`, `n_references`, `last_modified`, `cwe_ids`, every `cvss2_*`, `cvss3_*` and `cvss4_*` column, `attack_vector` through `availability_impact` (so no blank-score patterns), and all of `references.csv`, `affected_products.csv` and `weakness_types.csv`.
- **Model.** Boosted decision trees (scikit-learn) on exploit signals, each assigner's KEV history, a text score from the masked description, and an IBM Granite text score. Final scores are averaged over five seed sets and refit on 75,148 rows (117 later KEV-listed).
- **Testing.** We trained on older CVEs and ranked later ones, using only KEV labels known at the end of training. Fold 1 tests on January-September 2025 (52 later KEV-listed CVEs), fold 2 on April-September 2025 (32). The candidates and selection rules were written in `LOG.md` before the results they govern.
- **IBM technology.** IBM's Granite multilingual embedding model turned every masked description into a list of numbers that captures its meaning. We ran the open weights locally, and also sent a subset of 1,966 descriptions through IBM watsonx.ai; on the descriptions embedded both ways, our auditor found the vectors match. A pre-registered rule, a tie-break declared in advance in favour of IBM technology, adopted the Granite version because its mean AUC was within 0.01 of the model without it. It brought no measurable gain: mean AUC 0.871 vs 0.870. A Granite instruct model, run locally, also wrote short plain-English summaries for the top tier; they are AI-generated, unaudited, and some are template fallbacks.
- **Audit.** A separate auditor, in a fresh context, re-derived every published number with its own code (apart from two comparison-only checks) before it entered our claims ledger as verified.
- **App.** A FastAPI backend serves the audited files; a React dashboard shows them. A Gemini integration exists in code but produced no outputs in this build.

## Challenges we ran into
- **Our first result was too good.** The first pass showed 25 vs 18-19 top-500 hits over the rule "exploit code first, then EPSS". It was inflated by training labels that overlapped the test period and by seed luck (21-25 across seeds). With time-safe labels, the model roughly ties that rule in fold 1 (22 vs 18; seeds 15-22) and is behind in fold 2 (11 vs 15). Its AUC is higher in every fold and seed (0.860 vs 0.768; 0.880 vs 0.809), but for seed set 0 the paired interval on that gain includes zero. We publish the corrected result.
- **Small numbers.** With 52 test positives, one hit is about 2%, so a one- or two-hit difference between methods means little. We report ranges and intervals.
- **Today's text.** Descriptions are today's versions, and 6 of the 52 positives already contained exploitation wording. We mask that wording, but later edits we cannot detect may remain.
- **A shifted 2026.** There are about twice as many rows as in the same 2025 months (72,670 vs 35,280). GitHub advisories rise from 5.6% to 15.0% of rows and VulnCheck from 1.1% to 9.3%. In August-September, 66-68% of CVEs have no product list.
- **The watsonx.ai free quota ran out** after the subset (recorded in our decision log, not in a saved output file), so the full set was embedded with the same model's open weights.

## Accomplishments that we're proud of
- Finding the hidden leak and keeping it out of the model.
- Catching our own inflated first result and publishing the honest one.
- Sticking to rules written before the results. An automated search over many model variants found none that passed our pre-registered adoption gate, so the submitted model stayed. Granite was adopted under a declared tie-break and we say plainly that it brought no measurable gain.
- An independent refit by our auditor reproduced the submitted 2026 scores and `top500.csv` exactly.

## What we learned
- Check what a column knows and when it knew it. A field that NIST fills in after an attack can make a model look far better in a backtest than it will be on new CVEs.
- A single top-500 count from one random seed is not a result. AUC over the whole list is steadier, and even that gain can be borderline.
- Writing the selection rule down first stops you from picking the winner after you see the scores.

## What's next
- Score the ranking against 2026 KEV additions once they are public. We have no 2026 labels, so we make no 2026 accuracy claim.
- Use snapshot-dated descriptions if a historical feed is available, to remove the "today's text" risk.
- Test how well the model handles assigners with no earlier KEV entry, where our backtest had very few exploited CVEs.
- Pre-register any new model search against a period it has never seen.

## Limits (please read)
- KEV is a proxy: it lists confirmed attacks only. A CVE not on KEV may still have been attacked.
- 52 positives in the 2025 test, so one hit is about 2%.
- No 2026 labels; no 2026 accuracy claim.
- Our first pass had already compared about a dozen variants on the 2025 period, so it is not fully held out.
- Descriptions and assigner are today's values; exploitation wording is masked, but only known wording.

## Built with
Python, pandas, NumPy, SciPy, scikit-learn, PyArrow, joblib, sentence-transformers, IBM Granite (embedding and instruct models), IBM watsonx.ai (`ibm-watsonx-ai` SDK), Ollama, FastAPI, Uvicorn, React, TypeScript, Vite, Tailwind CSS, Recharts, Three.js, Nginx, Let's Encrypt.

## Links
- Code repository: https://github.com/Saad5A/Datathon2k26
- Live app: https://pancakess.work/
- Evidence page: https://pancakess.work/results
- Submission file: `results/top500.csv` in the repository

## Outside data
None. We used only the data files provided by the organisers and the IBM Granite models; no other outside data went into the model.
