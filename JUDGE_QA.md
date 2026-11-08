# Judge Q&A (model, leakage, backtest, 2026, IBM)

Every number here comes from a verified entry in `results/claims*.json`. Audit reports are in `audit/`.

**1. What exactly does your model predict?**
For each 2026 scoreboard CVE, it predicts how likely the CVE is to be added to CISA's KEV list (Known Exploited Vulnerabilities) after its snapshot month, using only what was known at the end of that month. The output is a ranking score. It is not a probability, so we never say "X% chance of attack". KEV is a proxy for "exploited": a CVE that is not on KEV may still have been attacked.

**2. Which columns did you use, and which did you leave out?**
We used EPSS and the four public-exploit flags (Exploit-DB, Metasploit, Nuclei, GitHub) as of the snapshot month. We also used the assigner's KEV history, counted only from KEV rows dated before the snapshot month, and the description with exploitation wording masked. We left out `nvd_status`, `n_affected_cpes`, `n_references`, blank-score patterns, all of `references.csv`, `affected_products.csv`, and the NIST-filled CVSS, CWE and attack-vector fields. An independent refit by our auditor reproduced every 2026 score exactly from the allowed columns alone.

**3. What is the "hidden leak" you found?**
In our 2025 backtest, every one of the 52 later-exploited CVEs had NIST status "Analyzed", a product list, and a filled CVSS3 score and CWE. Across all 2025 test CVEs, 35% had no product list. NIST reviews attacked CVEs first, so these columns partly record that someone already noticed an attack. The affected-product count alone ranks better than EPSS (AUC 0.767 vs 0.707).

**4. Is 52 out of 52 really "all"? That is a small sample.**
Yes, it is small. With 52 cases, the lower end of the confidence interval for the true share is about 93%, not 100%. The finding also comes from 2025 data only. We cannot measure the size of the leak for 2026 because we have no 2026 labels.

**5. Does your model beat the standard baselines?**
On AUC, yes. AUC is the chance that a random exploited CVE is ranked above a random non-exploited one. Our model's AUC is higher than "exploit code first, then EPSS" in both folds and every seed set (0.860 vs 0.768, and 0.880 vs 0.809). For seed set 0, though, the paired bootstrap interval on the gain includes zero in both folds. On top-500 hits it roughly ties in fold 1 (22 vs 18, with seeds ranging 15-22) and loses in fold 2 (11 vs 15). We do not claim to beat the baselines at the judges' metric.

**6. Your first pass showed 25 vs 18-19 in the top 500. Where did that go?**
Two things inflated it. First, its training labels used KEV additions from the test period itself: keeping only labels known before testing cuts the training positives from 65 to 40 and the top-500 count to 21. Second, 25 was the best of 10 seed sets (range 21-25). Our audit caught both problems, and we publish the corrected result.

**7. Why did you pick the model on AUC rather than top-500 hits?**
With 32-52 exploited CVEs per fold, top-500 hits move by several hits from the random seed alone, and the ranking of methods flipped between folds. AUC uses the whole list, so it is steadier. We fixed this rule, and the three candidates, in LOG.md before running anything. The rule picked C1 (mean AUC 0.870, against 0.848 and 0.836).

**8. How do you know your model is not leaking too?**
Every feature except the description text is built only from data dated before the end of the snapshot month, and the auditor checked this with its own code. When we shuffle the training labels, test AUC drops to about chance (fold 1 mean 0.532, fold 2 mean 0.506), so the model is not reading the answer from somewhere else. The one residual risk is the description text, covered next.

**9. Isn't the description text itself a leak?**
Partly, possibly. The description is today's text, and some 2025 descriptions already said "actively exploited" (6 of the 52 positives). We mask that wording before the text model sees it. The masked text score alone reaches AUC 0.8225, so most of our signal comes from text, and any later edits we cannot detect would affect it.

**10. How many hits do you expect in 2026?**
We do not know, and we make no 2026 accuracy claim. Our KEV file ends with 2025, and only the judges can count 2026 hits. We can say how 2026 differs from 2025 and what our model ranked. For reference, the README's standard rankings found 6 to 8 in the 2026 top 500.

**11. How is 2026 different from your test data?**
There are about twice as many rows as in the same 2025 months (72,670 vs 35,280). GitHub advisories make up 15.0% of rows (from 5.6%) and VulnCheck 9.3% (from 1.1%). In August-September, 66-68% of CVEs have no product list. That matters for anyone who uses product lists, even though we do not. Assigners with no prior KEV entry make up 23.8% of rows, down from 36.2%, and the 2026 figure is an upper bound.

**12. Why cap each assigner at 50 of the top 500? Does it help?**
In the backtest it is neutral, not an improvement: fold 1 drops from 22 to 20 hits, and fold 2 rises from 11 to 12. Our pre-set rule was to take the strictest cap within one hit of the best. We chose that rule because the 2026 assigner mix shifted and we did not want one issuer to fill the list. In the final top 500, three assigners (VulnCheck, Apache, Oracle) reach the cap of 50.

**13. What are the "reasons" next to each CVE?**
For each CVE we reset one signal at a time to a neutral value and measure how much the score moves. The up to three biggest moves are listed as reasons, each marked "up" or "down". They explain our model's score. They are not evidence that the CVE is being attacked. One row has an empty list because no signal changes its score.

**14. Where is the IBM technology?**
We have prepared IBM Granite embeddings of the masked descriptions, run through watsonx.ai or the open Granite weights, to test against our TF-IDF text signal. TF-IDF is word-count text scoring. A teammate is running this now, so there are no results yet. The test rule is pre-registered in LOG.md, and we will report the result whether or not Granite helps.

**15. Why should we trust any of your numbers?**
Every published number is registered in a claims ledger with the script that produced it. A separate auditor, working in a fresh context, re-derived each one with different code before marking it verified. The auditor also found the problems behind our first-pass result, and we kept those corrections. With 52 test positives, one hit is about 2%, so we always show ranges.
