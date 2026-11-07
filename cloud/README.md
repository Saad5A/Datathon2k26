# Cloud step: Granite embeddings of CVE descriptions

Model: IBM Granite `granite-embedding-278m-multilingual` (768 numbers per text, input up to 512 tokens).
Same model on both providers: watsonx.ai ID `ibm/granite-embedding-278m-multilingual`, Hugging Face ID
`ibm-granite/granite-embedding-278m-multilingual`. Sources and limits: `docs/ibm.md`.

Input: `data_cache/descriptions_to_embed.parquet` (147,818 CVEs, built by `cloud/make_embed_input.py`; exploitation
wording masked exactly like the TF-IDF model). Output: `data_cache/granite_embeddings.parquet` (`cve_id`, `vector`)
and `data_cache/granite_embeddings.meta.json`. All counts and times below are ESTIMATES (tokens = characters / 4).

The script caches every result in `data_cache/embed_cache/` (never committed). If it stops (crash, Ctrl-C, quota),
run the same command again: it continues where it stopped. `--estimate` prints counts and tokens without any call;
`--limit N` embeds only the first N rows (writes `*_subset.parquet`, not the main file).

## Option A: Colab GPU (recommended for the full set; free, about 10-25 min on a T4, estimate)
1. Open https://colab.research.google.com, New notebook. Runtime > Change runtime type > T4 GPU.
2. In the Files pane (left), upload `cloud/embed_granite.py` and `data_cache/descriptions_to_embed.parquet` to `/content`.
3. Run in a cell:
   ```
   !pip install -q -U sentence-transformers
   !python /content/embed_granite.py --provider LOCAL --limit 200 --in /content/descriptions_to_embed.parquet --out /content/test.parquet
   !python /content/embed_granite.py --provider LOCAL --in /content/descriptions_to_embed.parquet --out /content/granite_embeddings.parquet
   ```
   The first line downloads the model (about 1 GB). The second is a speed test; it prints texts/second.
   If the session disconnects, files in `/content` are lost: upload again and rerun (the run is short).
4. Download `granite_embeddings.parquet` and `granite_embeddings.meta.json` (Files pane, right-click > Download) and
   put both in `data_cache/` of the repo.

## Option B: watsonx.ai (IBM cloud API; Lite plan quota allows only about 2,000 descriptions per month)
The free Lite plan allows 300,000 tokens per month; the full set is about 16.8 million (estimate), so a full run
needs a paid plan (about $1.70 at $0.0001 per 1,000 tokens, estimate). The script refuses to start above
`--max-tokens` (default 250,000).
1. Sign up (Toronto): https://ca-tor.dai.cloud.ibm.com/registration/stepone?context=wx&preselect_region=true
2. Create a project. In the project: Manage > Services & integrations > associate the watsonx.ai Runtime service.
   Copy the project ID from Manage > General > Details.
3. Create an API key: https://cloud.ibm.com > Manage > Access (IAM) > API keys > Create.
4. In the repo root: copy `.env.example` to `.env` and fill in the three values (`WATSONX_URL=https://ca-tor.ml.cloud.ibm.com`
   for Toronto). Never commit or paste `.env`.
5. Check your plan's token allowance (watsonx.ai Runtime service plan / usage page) and tell the model agent.
6. Install the SDK after you approve it (not yet in requirements.txt): `.venv/bin/pip install ibm-watsonx-ai==1.9.1`
7. `.venv/bin/python cloud/embed_granite.py --provider WATSONX --limit 20` (dry run, about 2,200 tokens).
8. Quota-safe run: `.venv/bin/python cloud/embed_granite.py --provider WATSONX --limit 1500`, or a chosen list:
   `--ids some.csv` (a CSV with a `cve_id` column). Output lands in `data_cache/granite_embeddings_watsonx_subset.parquet`.
9. Full run, only if your plan allows it: add `--max-tokens 17000000`.

## Option C: this laptop CPU (fallback; roughly 1-2.5 hours, estimate)
1. Install the already-listed dependency after you approve it: `.venv/bin/pip install sentence-transformers`
   (pulls in PyTorch, about 1 GB).
2. `.venv/bin/python cloud/embed_granite.py --provider LOCAL --limit 200` (speed test; prints texts/second).
3. `.venv/bin/python cloud/embed_granite.py --provider LOCAL` (writes straight into `data_cache/`; Ctrl-C and rerun to resume).

## Check
`.venv/bin/python cloud/test_embed_granite.py` runs the cache/resume/output logic offline (no model, no network).
