# Judge Q&A (model, leakage, backtest, 2026, IBM Granite)

Numbers below are taken from committed `results/*.json` / `data_cache/*.meta.json` and verified ranking claims where noted. Granite subset metrics are **embedding-covered slices only** (`results/granite_subset_comparison.json` note).

---

## IBM Granite / watsonx

**Q. Why IBM Granite 278M multilingual instead of pure keyword / BM25-style text?**  
**A.** Keyword/TF-IDF counts surface terms; Granite `ibm/granite-embedding-278m-multilingual` maps masked descriptions to **768-d dense semantic vectors** (watsonx Toronto, L2-normalised). On the embedding-covered backtest slices, a logistic regression on Granite text beat TF-IDF text on AUC in both folds: fold1 **0.6981 vs 0.6794** (Δ **+0.0187**), fold2 **0.6392 vs 0.5923** (Δ **+0.0469**); mean Δ AUC **+0.0328**. Top-50 / top-100 hits also rose (e.g. fold1 top-100: **16 → 22**). We still keep structured signals (EPSS, exploit flags, assigner history) for ranking; Granite is the alternate **text** channel.

**Q. How do you handle cold-start CVEs with little exploit telemetry?**  
**A.** New CVEs often lack public exploit flags or strong EPSS. Dense embeddings place their descriptions near semantically similar past CVEs in latent space, so the text LR can still score them from wording alone. On covered fold1, Granite text Recall@500 was **0.9231** (48/52 positives in the top 500 of that covered pool) vs TF-IDF **0.8846**. Structured features remain available when present; embeddings do not invent KEV labels.

**Q. Token economics—how does 1,500 scale to the full corpus?**  
**A.** Subset meta: **1,500** rows, **233,097** estimated tokens this run, under the Lite **300,000**/month foundation-model budget. Eval slice added **~46,051** estimated tokens (466 rows). Full masked corpus estimate is ~**16.8M** tokens—about **56×** Lite monthly allowance—so full watsonx embedding needs a paid plan or **LOCAL/Colab** Hugging Face Granite (`cloud/README.md`). We cache to disk; reruns skip embedded texts.

**Q. Can teammates use the results without cloud credentials?**  
**A.** Yes. Commit/share `data_cache/granite_embeddings_watsonx_subset.parquet` (+ evalslice) and `results/granite_subset_comparison.json`. Evaluation reads local parquet only (`src/model/granite_subset_eval.py`). Explanations/playbooks are JSON under `results/`. No `WATSONX_*` env vars are required to **consume** artifacts—only to **extend** embeddings.

**Q. Where is the IBM technology in the demo?**  
**A.** Hybrid pipeline: local data prep → watsonx.ai `ca-tor` embeddings with Granite 278M multilingual → local ranking/eval. Artifacts: subset parquet (**1,500×768**), comparison JSON (**1,966** vectors combined), explanations in `results/granite_explanations_top100.json` (**30** committed rationales with `grounding_ok`), sample playbooks in `results/sample_playbooks.json`.

---

## Ranking model & leakage

**1. What exactly does your model predict?**  
For each 2026 scoreboard CVE, a **ranking / Priority Score** for later KEV addition using snapshot-month information only—not a probability (“X% chance”). KEV is a proxy for exploitation.

**2. Which columns did you use / leave out?**  
Used (as-of): EPSS and public exploit flags; assigner KEV history before snapshot; masked description text (TF-IDF and/or Granite on covered IDs). Left out leaky NIST completeness fields: `nvd_status`, `n_affected_cpes`, `n_references`, blank-score patterns, news/threat reference links, etc. (see leakage table / audits).

**3. What is the “hidden leak” you found?**  
In the 2025 backtest, all **52** later-KEV positives were NIST “Analyzed” with products/CVSS/CWE filled, while much of the negative pool was not—NIST reviews attacked CVEs first. Product-count solo AUC can exceed EPSS; we therefore exclude those columns.

**4. Does your full model beat standard baselines?**  
On the primary fold AUC, our selected ranking recipe is higher than exploit-then-EPSS; top-500 hits are noisy with 32–52 positives and can flip across folds/seeds. We report intervals and do not over-claim the judges’ top-500 metric. Granite’s lift above is **text-only on a Lite subset**, separate from the full structured C1 ranking story.

**5. How many hits do you expect in 2026?**  
**None claimed.** No 2026 labels for self-scoring. Organisers’ baseline reference ranks found on the order of 6–8 in a 2026 top 500.

**6. Why cap each assigner at 50 of the top 500?**  
Limits one CNA flooding the list after 2026 assigner-mix shift. Cap rule was pre-registered; several assigners hit 50 in the final top 500.

**7. What are the “reasons” next to each CVE?**  
Occlusion of signal groups (EPSS, public exploit, assigner history, description text): up to three largest score moves as JSON—explanations of the **model score**, not proof of active exploitation.

**8. Why should we trust the numbers?**  
Ranking claims are audited in `audit/` and ledgers under `results/claims_*.json`. Granite subset figures are taken verbatim from `granite_subset_comparison.json` / `claims_model_granite.json` and carry the **partial-coverage** caveat—do not treat them as a full-corpus adoption result until embeddings cover the whole pool.
