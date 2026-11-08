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

## For a teammate running this on their own computer (start here)
You need: git, Python 3.12, about 2 GB free disk, the IBM `data.zip` (from the datathon page or a teammate), and for
watsonx.ai your own watsonx.ai account. Commands are for Mac/Linux; on Windows use `py -3.12` instead of `python3.12`
and `.venv\Scripts\python` instead of `.venv/bin/python`.

1. Get the code:
   ```
   git clone https://github.com/Saad5A/Datathon2k26.git
   cd Datathon2k26
   git checkout feat/model-ranking
   ```
2. Make a Python environment with the exact versions we used:
   ```
   python3.12 -m venv .venv
   .venv/bin/python -m pip install -r src/model/requirements.lock
   ```
3. Put the data in place: unzip `data.zip` so that `data/known_exploited.csv` exists inside the repo folder
   (or set the env var `IBM_DATA_DIR` to the folder that holds the CSVs). The `data/` folder is gitignored.
4. Build the input file (about 1 minute). It must print 147,818 rows:
   ```
   .venv/bin/python cloud/make_embed_input.py
   ```
   This writes `data_cache/descriptions_to_embed.parquet` (about 28 MB).
5. Run ONE of the options below. Option A (Colab) for the full set, and Option B (watsonx.ai) for a small slice.
6. Hand the results back. The full output is about 450 MB (147,818 x 768 numbers), too big for git, so do NOT
   commit it. Upload `granite_embeddings.parquet` and `granite_embeddings.meta.json` (and, for watsonx.ai,
   `granite_embeddings_watsonx_subset.parquet` plus its meta file) to the team's shared drive. Then tell the
   model-ranking owner where they are. They go into `data_cache/` on the model-ranking laptop.

Rules: never commit or paste `.env` or an API key into chat, Slack or Discord. Use your own watsonx.ai API key; if
you must use someone else's, get it in person or in a password manager. Do not run the full watsonx.ai set without
asking: it is paid above the free quota.
If something fails, copy the last 20 lines of output (they contain no secrets) and send them to the model-ranking owner.

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

## Option D: local Ollama Granite summaries (CPU, no API key, no GPU)

This is the guaranteed IBM-track artifact: IBM Granite 4.2 3B writes a grounded one-sentence
summary for the top 100 ranked CVEs. It does **not** change `scores_2026.csv` or `top500.csv`.
1. Install/start Ollama and pull the model: `ollama pull granite4.2:3b`.
2. Run: `.venv/bin/python cloud/explain_granite_ollama.py --limit 100`.
3. Output: `results/granite_summaries_top100.json` + `.meta.json`. The 2026-11-08 run produced
   100 rows, 94 Granite summaries that passed grounding, 6 deterministic template fallbacks,
   and 0 unsupported versions/URLs/CVE IDs/banned claims in the final file.
4. The script validates every summary and falls back to the description's first sentence on
   failure. Template fallbacks are labelled `deterministic-template`, not AI-generated.
5. `--limit 10` is a quick pilot; the model stays local and no credentials are used.

## Check
`.venv/bin/python cloud/test_embed_granite.py` runs the cache/resume/output logic offline (no model, no network).
