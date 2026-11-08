# Judge Q&A (model, leakage, backtest, 2026, IBM)

Every number here comes from a verified entry in `results/claims*.json`. Audit reports are in `audit/`.

**1. What exactly does your model predict?**
For each 2026 scoreboard CVE, it predicts how likely the CVE is to be added to CISA's KEV list (Known Exploited Vulnerabilities) after its snapshot month, using only what was known at the end of that month. The output is a ranking score. It is not a probability, so we never say "X% chance of attack". KEV is a proxy for "exploited": a CVE that is not on KEV may still have been attacked.

**2. Which columns did you use, and which did you leave out?**
Used: `epss`, `exploitdb`, `metasploit`, `nuclei` and `poc_github` at the snapshot month, from `exploit_signals_2024.csv`/`exploit_signals_2025.csv` and `scoreboard_2026.csv`. From `vulnerabilities.csv` we used `assigner`, `description` (exploitation wording masked) and `published` (CVEs published 2021+ for assigner history). From `known_exploited.csv` we used `date_added`, counting only rows before the snapshot month for features. The same masked `description` is also turned into IBM Granite embeddings. `in_kev` serves only to drop CVEs already on KEV. Nothing else. Left out: `nvd_status`, `n_affected_cpes`, `n_references`, `last_modified`, `cwe_ids`, every `cvss2_*`, `cvss3_*` and `cvss4_*` column, `attack_vector` through `availability_impact` (so no blank-score patterns), and all of `references.csv`, `affected_products.csv` and `weakness_types.csv`. The description and assigner are today's values, not snapshot-month values. An independent refit by our auditor reproduced every 2026 score exactly from the allowed columns alone.

**3. What is the "hidden leak" you found?**
In our 2025 backtest, every one of the 52 later KEV-listed CVEs had NIST status "Analyzed", a product list, and a filled CVSS3 score and CWE. Among the other test CVEs, only 50.1% were "Analyzed" and 64.9% had a product list. The organisers' README explains why: NIST reviews attacked CVEs first, so these columns can partly record that an attack was already noticed. In this backtest, the affected-product count alone scores a higher AUC than EPSS (0.767 vs 0.707; the intervals overlap).

**4. Is 52 out of 52 really "all"? That is a small sample.**
Yes, it is small. With 52 cases, the lower end of the confidence interval for the true share is about 93%, not 100%. The finding also comes from 2025 data only. We cannot measure the size of the leak for 2026 because we have no 2026 labels.

**5. Does your model beat the standard baselines?**
On AUC, our estimate is higher, but the gain is borderline. AUC is the chance that a random exploited CVE is ranked above a random non-exploited one. Our model's AUC is higher than "exploit code first, then EPSS" in both folds and every seed set (0.860 vs 0.768, and 0.880 vs 0.809). For seed set 0, though, the paired bootstrap interval on the gain includes zero in both folds. On top-500 hits it roughly ties in fold 1 (22 vs 18, with seeds ranging 15-22) and loses in fold 2 (11 vs 15). The final model, G2 (C1 plus a Granite text score), shows the same pattern: 20 vs 18 in fold 1 and 11 vs 15 in fold 2. We do not claim to beat the baselines at the judges' metric.

**6. Your first pass showed 25 vs 18-19 in the top 500. Where did that go?**
Two things inflated it. First, its training labels used KEV additions from the test period itself: keeping only labels known before testing cuts the training positives from 65 to 40 and the top-500 count to 21. Second, 25 was the best of 10 seed sets (range 21-25). Our own sensitivity checks found both, and the independent audit confirmed them. We publish the corrected result.

**7. Why did you pick the model on AUC rather than top-500 hits?**
With 32-52 exploited CVEs per fold, top-500 hits move by several hits from the random seed alone, and the ranking of methods flipped between folds. AUC uses the whole list, so it is steadier. We fixed this rule, and the three candidates, in LOG.md before running Phase 3 (the 2025 data had already been used in our first pass, where we compared about a dozen variants and C1 reuses the winner's inputs). The rule picked C1 (mean AUC 0.870, against 0.848 and 0.836).

**8. How do you know your model is not leaking too?**
Apart from the description text and the assigner field itself (both today's values), every input is built only from data dated before the end of the snapshot month. When we shuffle the training labels, test AUC drops to about chance (fold 1 mean 0.532, fold 2 mean 0.506). That shows no path from the test labels into the model bypasses training. The auditor checked the time safety of each feature separately, with its own code. The one residual risk is the description text, covered next.

**9. Isn't the description text itself a leak?**
Partly, possibly. The description is today's text, and 6 of the 52 positives already contained exploitation wording such as "actively exploited", "exploited in the wild", "CISA" or "KEV". We mask that wording before the text model sees it. The masked text score alone reaches AUC 0.8225, so text is our strongest single input; dropping it, or dropping the exploit/EPSS signals, clearly hurts. Later edits that we cannot detect would affect it.

**10. How many hits do you expect in 2026?**
We do not know, and we make no 2026 accuracy claim. Our KEV file ends with 2025, and only the judges can count 2026 hits. We can say how 2026 differs from 2025 and what our model ranked. For reference, the organisers report that standard rankings found 6 to 8 in the 2026 top 500.

**11. How is 2026 different from your test data?**
There are about twice as many rows as in the same 2025 months (72,670 vs 35,280). GitHub advisories make up 15.0% of rows (from 5.6%) and VulnCheck 9.3% (from 1.1%). In August-September, 66-68% of CVEs have no product list. That matters for anyone who uses product lists, even though we do not. Assigners with no prior KEV entry make up 23.8% of rows, down from 36.2%, and the 2026 figure is an upper bound.

**12. Why cap each assigner at 50 of the top 500? Does it help?**
In the backtest it is neutral, not an improvement (tested with C1; not re-tested with G2): fold 1 drops from 22 to 20 hits, and fold 2 rises from 11 to 12. Our pre-set rule was to take the strictest cap within one hit of the best. We chose that rule because the 2026 assigner mix shifted and we did not want one issuer to fill the list. In the final top 500, two assigners (VulnCheck and Apache) reach the cap of 50. These counts depend on our assigner-history window (CVEs published 2021+).

**13. What are the "reasons" next to each CVE?**
For each CVE we reset one signal at a time to a neutral value and measure how much the score moves. The up to three biggest moves are listed as reasons, each marked "up" or "down". They explain our model's score. They are not evidence that the CVE is being attacked. In the final model, the description reason shows the TF-IDF text score, and the Granite text score is reset together with it.

**14. Where is the IBM technology, and did it help?**
We used IBM's Granite multilingual embedding model (exact ID in `docs/ibm.md`) to turn every masked description into a list of numbers that captures its meaning. We ran the open weights locally, and also sent a subset of 1,966 descriptions through IBM watsonx.ai; on the 1,500 descriptions also embedded locally, the auditor found the vectors match. That they came from watsonx.ai rests on the run metadata. Our pre-registered test compared G1 (Granite text instead of TF-IDF) and G2 (both) with C1. The rule adopted G2 because its mean AUC was within the pre-set 0.01 of C1's (fold 2 alone: 0.868 vs 0.880), a tie-break we declared in advance in favour of IBM technology. There was no measurable gain. Mean AUC is 0.871 vs 0.870; per fold it is 0.874 vs 0.860 and 0.868 vs 0.880; top-500 is 20 vs 22 and 11 vs 11. Granite alone (G1) was clearly lower, with mean AUC 0.837. An exploratory subset check also exists, but it is not comparable; see the audit.

**15. Why should we trust any of your numbers?**
Every published number is registered in a claims ledger with the script that produced it. A separate auditor, working in a fresh context, re-derived each one with different code before marking it verified, apart from two comparison-only checks. The auditor confirmed the problems behind our first-pass result, and we kept those corrections. With 52 test positives, one hit is about 2%, so we always show ranges.
