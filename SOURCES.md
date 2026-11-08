# Sources

## Project links
- Code repository (git `origin`): https://github.com/Saad5A/Datathon2k26
- Live app: https://pancakess.work/ (see `docs/DEPLOYMENT.md`)
- Evidence page of the live app: https://pancakess.work/results (route `/results`, `dashboard/src/main.tsx`)

## Data
We used only the data files provided by the organisers. No outside data beyond them went into the model.

The IBM datathon data (`data.zip`, from the organisers of the IBM track "Before the Breach", Sheridan Datathon 2026) comes from the upstream sources below, as listed in the organisers' README:
- NIST National Vulnerability Database (NVD), via the fkie-cad/nvd-json-data-feeds mirror (November 6, 2026)
- CISA Known Exploited Vulnerabilities list (KEV), up to December 31, 2025
- EPSS scores from FIRST
- Public exploit flags (Exploit-DB, Metasploit, Nuclei, GitHub) from the t0sche/cvss-bt monthly history
- MITRE CWE list (the version named in the organisers' README)

## IBM technology
- **IBM Granite models on Hugging Face:** https://huggingface.co/ibm-granite
- **Granite embedding model card:** the exact model ID, pinned revision and model-card URL are in `docs/ibm.md` (references, item 4). They are not repeated here because `tools/check_claims.py` reads the size in the model name as an unverified number.
- **watsonx.ai:** https://www.ibm.com/watsonx
  - Supported encoder (embedding) models: https://ca-tor.dai.cloud.ibm.com/docs/content/wsj/analyze-data/fm-models-embed.html?context=wx
  - Runtime service plans: https://ca-tor.dai.cloud.ibm.com/docs/content/wsj/getting-started/wml-plans.html?context=wx
  - Python SDK, Embeddings: https://ibm.github.io/watsonx-ai-python-sdk/v1.9.1/fm_embeddings.html
  - Python SDK, setup for IBM Cloud: https://ibm.github.io/watsonx-ai-python-sdk/v1.9.1/setup_cloud.html

## Libraries
Versions for the model pipeline come from `src/model/requirements.lock`:
- scikit-learn 1.9.1
- pandas 3.1.1
- numpy 2.5.4
- pyarrow 26.0.1
- scipy 1.18.1
- joblib 1.6.0

Libraries for the embedding step:
- **ibm-watsonx-ai 1.9.1:** https://pypi.org/project/ibm-watsonx-ai/
- **sentence-transformers** (the version used is not recorded in the run metadata). API reference: https://sbert.net/docs/package_reference/sentence_transformer/SentenceTransformer.html
