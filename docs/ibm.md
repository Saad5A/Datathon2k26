# IBM technology in this project

Status (2026-11-08): Granite embeddings RUN, tested under a rule we wrote down before seeing results, and audited.
Granite is part of the final ranking, but it gave **no measurable gain**. It is used because the track requires
IBM technology, and its mean AUC was within the pre-set 0.01 of C1's (fold 2 alone: 0.868 vs 0.880).

## What actually ran
| Technology | What ran | Evidence |
|---|---|---|
| watsonx.ai (IBM Cloud, Toronto `ca-tor`), SDK `ibm-watsonx-ai` 1.9.1, model `ibm/granite-embedding-278m-multilingual` | A teammate embedded 1,966 masked CVE descriptions in two runs: 1,500 rows (`--limit 1500`) and 466 rows (`--ids`, an evaluation slice) | `data_cache/granite_embeddings_watsonx_subset.meta.json`, `data_cache/granite_embeddings_watsonx_evalslice.meta.json`; claim `p6.granite_subset.n_vectors` = 1966, verified in `audit/2026-11-07-granite-subset.md` |
| Same model, open weights from Hugging Face (`ibm-granite/granite-embedding-278m-multilingual`, revision `a9cb533`), via `sentence-transformers` on an Apple GPU (`mps`) | All 147,818 descriptions (75,148 backtest pool + 72,670 scoreboard 2026), 768 numbers each | `data_cache/granite_embeddings.meta.json`; integrity checks in `audit/2026-11-08-granite-final.md` section 3 |

- **Free quota.** After those two runs the account's Lite token quota was used up: a later 20-text dry run returned
  `token_quota_reached`. The coordinator reported this; no log file in the repo records it (UNVERIFIED by a file).
  This is why the full set ran on the open weights instead of watsonx.ai.
- **Same input for both providers.** Both used the same input file (sha256 `2fc1cd5f...e276`, in every meta).
  Exploitation wording was masked exactly as in the TF-IDF text model.
- **watsonx.ai and local vectors agree.** On the 1,500 CVEs both providers embedded, the minimum cosine similarity
  is 0.999982 and the mean is 0.999988. A shuffled-pair control gives 0.636.
  - This is verified in `audit/2026-11-08-granite-final.md` section 3, as audit text, not as a ledger entry.
  - That the watsonx vectors really came from watsonx.ai rests on the teammate's meta files (UNCHECKED by the audit).
- **Code.** `cloud/make_embed_input.py` (input), `cloud/embed_granite.py` (provider switch WATSONX/LOCAL, batching,
  truncation to 512 tokens, retry, disk cache, token budget guard), `cloud/README.md` (steps).

## How Granite is used in the model (pre-registered test, LOG.md "PRE-REGISTRATION, Granite text ...")
- G1 = our base model C1 with a Granite text score instead of the TF-IDF text score. G2 = C1 with both text scores.
- Rule, fixed before results: adopt the better of G1 and G2 if its mean AUC over the two backtest folds is at least
  C1's minus 0.01.
- Result (`results/claims_model_granite.json`, all 87 `p6.granite.*` claims verified in
  `audit/2026-11-08-granite-final.md`):

  | Model | Mean AUC over the two folds |
  |---|---|
  | C1 | 0.870 |
  | G1 | 0.837 |
  | G2 | 0.871 |

- **G2 adopted, no measurable gain.** The 0.0013 difference from C1 is far smaller than the seed-to-seed spread
  (about 0.03).
  - Top 500, G2 vs C1: fold 1 is 20 vs 22, fold 2 is 11 vs 11.
  - Granite alone (G1) is worse.
- **Final files use G2.** `results/top500.csv` and `results/scores_2026.csv` come from G2. The 19 `p7.*` claims in
  `results/claims_model_final.json` are verified, and an independent refit reproduces both files exactly.
- **Wording rule for the write-up.** Say "adopted by the pre-set IBM tie-break, no measurable gain". Never say Granite
  "improves" accuracy, AUC or hits.

## Not used / not done
- Granite instruct model explanations: no instruct model was run. `docs/examples/explanations_top30_OFFLINE_TEMPLATE_not_granite.json`
  is a template draft, not Granite output and not AI-generated. `cloud/explain_granite_top100.py` exists but has not been run.
- watsonx AutoAI, watsonx Orchestrate, vLLM / Red Hat AI Inference Server, Granite TimeSeries: not used.

## Model IDs (looked up 2026-11-07, not guessed)
| Where | Exact ID | Dimension | Max input tokens | Source |
|---|---|---|---|---|
| watsonx.ai `ca-tor` and `us-south` | `ibm/granite-embedding-278m-multilingual` | 768 | 512 | live list `GET https://ca-tor.ml.cloud.ibm.com/ml/v1/foundation_model_specs?version=2024-07-25&filters=function_embedding` (public; "available" since 2025-01-09 in ca-tor) and docs [1] |
| Hugging Face | `ibm-granite/granite-embedding-278m-multilingual`, revision `a9cb5338491faf32b73dd17b714a31821c021bbf` | 768 | 512 | [4]; CLS pooling + normalise; Apache-2.0 |

Other embedding models listed in `ca-tor`: `ibm/slate-125m-english-rtrvr-v2` and `ibm/slate-30m-english-rtrvr-v2`
(both deprecated 2026-05-05) and `intfloat/multilingual-e5-large` (not IBM). `ibm/granite-embedding-107m-multilingual`
appears only in older docs.
UNKNOWN: whether watsonx.ai serves exactly the Hugging Face revision above. The near-1.0 cosine agreement suggests
the same model, but it does not prove the same revision.

## SDK and limits
- SDK [2][3]: `Credentials(url=, api_key=)`, `foundation_models.Embeddings(model_id=, credentials=, project_id=, params=)`,
  `embed_documents(texts)`. Truncation uses `EmbedTextParamsMetaNames.TRUNCATE_INPUT_TOKENS` (we set 512; the two watsonx
  runs completed with it).
- Lite (free) plan [5]: 300,000 foundation-model tokens per month and 2 inference requests per second. The full set
  is an estimated 16.8 million tokens (characters / 4; `results/embed_input_summary.json`, claim unverified).
- Price [1]: $0.0001 per 1,000 tokens.
- UNKNOWN: whether the organiser's trial sign-up has exactly Lite limits.

## Doc URLs
1. Supported encoder models: https://ca-tor.dai.cloud.ibm.com/docs/content/wsj/analyze-data/fm-models-embed.html?context=wx
2. SDK Embeddings: https://ibm.github.io/watsonx-ai-python-sdk/v1.9.1/fm_embeddings.html
3. SDK setup (regional URLs): https://ibm.github.io/watsonx-ai-python-sdk/v1.9.1/setup_cloud.html
4. Model card: https://huggingface.co/ibm-granite/granite-embedding-278m-multilingual
5. watsonx.ai Runtime plans: https://ca-tor.dai.cloud.ibm.com/docs/content/wsj/getting-started/wml-plans.html?context=wx
6. PyPI: https://pypi.org/project/ibm-watsonx-ai/ (1.9.1, 2026-11-05)
7. sentence-transformers API: https://sbert.net/docs/package_reference/sentence_transformer/SentenceTransformer.html
