# IBM technology

## Allowed / suggested by the README [SOURCE: IBM/README.md]
Granite language and embedding models (https://huggingface.co/ibm-granite), Granite TimeSeries (https://huggingface.co/ibm-granite/granite-timeseries-ttm-r2), watsonx.ai and watsonx Orchestrate (need an IBM account; https://www.ibm.com/watsonx), Red Hat AI Inference Server and vLLM (https://docs.vllm.ai). IBM products named in the brief: IBM Concert Protect (vulnerability prioritization), IBM X-Force (threat intelligence).

## Organizer recommendation [SOURCE: screenshot from mentor channel]
Sign up for the free watsonx.ai trial (no code needed): https://ca-tor.dai.cloud.ibm.com/registration/stepone?context=wx&preselect_region=true . Setup can take a few minutes: do it early. No account: run Granite locally or in Colab using https://github.com/ibm-granite-community/granite-agent-cookbook (tutorial notebooks on function calling, ReAct, ToolRAG, Plan-and-Solve, agent testing, AI agent security, small-model techniques; Apache 2.0 code; IBM says it is not an IBM product and will not maintain it).

## Our plan (model branch owns all IBM integration)
1. Granite embedding model of CVE descriptions via watsonx.ai API (cloud step; fallback LOCAL/Colab). Compare to TF-IDF honestly.
2. Optional: Granite-generated grounded explanations (alongside the Gemini playbooks), optional watsonx Studio notebook run of the final training, optional AutoAI cross-check.
3. Document exactly what ran where in `docs/ibm.md` for the write-up and Devpost.

## Must be looked up, not guessed [UNKNOWN]
Current Granite model IDs (embedding and instruct), ibm-watsonx-ai SDK call signatures, trial limits (tokens, compute units, whether Studio notebooks and AutoAI are included), watsonx region/endpoint URL.
Credentials only in a gitignored `.env`: WATSONX_APIKEY, WATSONX_URL, WATSONX_PROJECT_ID.
