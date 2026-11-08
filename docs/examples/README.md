# Examples and drafts (NOT results; do not display as findings)
- `explanations_top30_OFFLINE_TEMPLATE_not_granite.json`: produced by `cloud/explain_granite_top100.py --offline`: a fill-in template for 30 CVEs, not output of any language model (every entry has `"provider": "offline_template"`). The script's online model is set to `meta-llama/llama-3-3-70b-instruct`, not IBM Granite. Do not call these "Granite explanations" or "AI-generated".
- `sample_playbooks_DUMMY.json`: dummy example with fake vendors and `.example` URLs. Never show as real data.
