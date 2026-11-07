# IBM technology in this project

Status (2026-11-07): Granite embeddings PREPARED, NOT YET RUN. No watsonx.ai call has been made and nothing has been
embedded. No result from Granite exists yet; when it does, it is compared with TF-IDF on the held-out fold and reported
honestly, including if it does not help.

## What we use, and for what
| Technology | Use | Status |
|---|---|---|
| IBM Granite embedding model `granite-embedding-278m-multilingual` | Turn each CVE description (exploitation wording masked, same text as the TF-IDF model) into a 768-number vector; a small logistic regression on the vectors becomes an alternative text signal, compared with TF-IDF on the held-out fold | prepared, not yet run |
| watsonx.ai (IBM Cloud, Toronto `ca-tor`) via the `ibm-watsonx-ai` Python SDK | Hosted inference for the embedding model (provider `WATSONX`) | prepared, not yet run; SDK not installed (awaiting approval) |
| Hugging Face `ibm-granite` open weights via `sentence-transformers` | Same model run locally / on Colab (provider `LOCAL`) | prepared, not yet run |

Code: `cloud/make_embed_input.py` (input file), `cloud/embed_granite.py` (provider switch, batching, truncation,
retry, disk cache keyed by sha256(model_id + text), token budget guard), `cloud/README.md` (steps for the human).
The ranking model itself stays in scikit-learn.

## Model IDs (looked up 2026-11-07, not guessed)
| Where | Exact ID | Dimension | Max input tokens | Source |
|---|---|---|---|---|
| watsonx.ai, `ca-tor` and `us-south` | `ibm/granite-embedding-278m-multilingual` | 768 | 512 | live model list `GET https://ca-tor.ml.cloud.ibm.com/ml/v1/foundation_model_specs?version=2024-07-25&filters=function_embedding` (public, no credentials; lifecycle "available" since 2025-01-09 in ca-tor) and the docs table [1] |
| Hugging Face (LOCAL) | `ibm-granite/granite-embedding-278m-multilingual`, pinned revision `a9cb5338491faf32b73dd17b714a31821c021bbf` | 768 (`hidden_size`) | 512 (`sentence_bert_config.json`) | [4]; modules: Transformer, CLS pooling, Normalize; license Apache-2.0 |

Other embedding models on watsonx.ai `ca-tor` (same live list): `ibm/slate-125m-english-rtrvr-v2` (768, deprecated
2026-05-05, withdrawn 2027-01-12), `ibm/slate-30m-english-rtrvr-v2` (384, deprecated), `intfloat/multilingual-e5-large`
(1024, not IBM). Granite is the only non-deprecated IBM embedding model there. `ibm/granite-embedding-107m-multilingual`
appears in older docs but is NOT in the current ca-tor or us-south list. Newer Granite English R2 models
(`ibm-granite/granite-embedding-english-r2`, 768-dim, 8192 tokens) exist on Hugging Face but are not on the watsonx.ai
list, so we use the 278m model to keep both providers on the same model.
UNKNOWN: whether the watsonx.ai deployment uses exactly the same weights as the Hugging Face revision above, and
whether watsonx.ai vectors come back L2-normalised (the script normalises both).

## SDK (ibm-watsonx-ai 1.9.1, docs [2], [3])
- `Credentials(url=..., api_key=...)`; Toronto URL `https://ca-tor.ml.cloud.ibm.com` [3].
- `ibm_watsonx_ai.foundation_models.Embeddings(model_id=, credentials=, project_id=, params=, batch_size=1000 default,
  concurrency_limit=5 default (max 10), max_retries=10 default, retry on 429/503/504/520)`; `embed_documents(texts)`
  returns `list[list[float]]` [2].
- `ibm_watsonx_ai.metanames.EmbedTextParamsMetaNames.TRUNCATE_INPUT_TOKENS` truncates long inputs [2].
  UNVERIFIED: whether 512 counts the special tokens (if the API rejects 512, lower it in `embed_granite.py`).
- Our code was written against these docs but NOT executed (SDK not installed).

## Plan limits (docs [5])
- watsonx.ai Runtime Lite (free) plan: foundation-model inferencing 300,000 tokens per month (1,000 tokens = 1 RU),
  rate limit 2 inference requests per second. Essentials/Standard: billed per token, 8 requests per second.
- Price for this model: $0.0001 per 1,000 tokens (class C1) [1].
- UNKNOWN: whether the organiser's "free trial" sign-up gives Lite-plan limits or something larger; the human must
  check the plan page in their account.
- Our estimate (characters / 4): about 16.8 million tokens for all 147,818 descriptions (`results/embed_input_summary.json`),
  about 56 times the Lite monthly allowance. So on Lite, watsonx.ai can embed only about 2,000 descriptions per month;
  the full set runs on the same Granite model via Hugging Face (Colab GPU or laptop).

## Doc URLs
1. Supported encoder foundation models (watsonx.ai, Toronto docs): https://ca-tor.dai.cloud.ibm.com/docs/content/wsj/analyze-data/fm-models-embed.html?context=wx (same content at https://dataplatform.cloud.ibm.com/docs/content/wsj/analyze-data/fm-models-embed.html?context=wx)
2. SDK Embeddings: https://ibm.github.io/watsonx-ai-python-sdk/v1.9.1/fm_embeddings.html
3. SDK setup for IBM Cloud (regional URLs, Credentials): https://ibm.github.io/watsonx-ai-python-sdk/v1.9.1/setup_cloud.html
4. Hugging Face model card: https://huggingface.co/ibm-granite/granite-embedding-278m-multilingual
5. watsonx.ai Runtime service plans: https://ca-tor.dai.cloud.ibm.com/docs/content/wsj/getting-started/wml-plans.html?context=wx
6. PyPI: https://pypi.org/project/ibm-watsonx-ai/ (1.9.1, released 2026-11-05; source/samples https://github.com/IBM/watsonx-ai-samples)
7. sentence-transformers API (v6.2): https://sbert.net/docs/package_reference/sentence_transformer/SentenceTransformer.html
