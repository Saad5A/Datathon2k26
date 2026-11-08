# Gemini model analysis (dual-provider with IBM Granite)

Standalone evaluation notes for the Gemini triage / remediation path from
`feat/triage-playbook-gemini`, integrated additively beside the watsonx Granite
embedding + narrative stack. **Does not modify** audited baselines
(`JUDGE_QA.md`, `docs/writeup_model.md`, `results/top500.csv`, `results/scores_2026.csv`).

## Methodology

1. **Ranking stays ML-owned.** Priority tiers (P0/P1/P2) and ranks come from the
   audited scoring pipeline. Gemini never re-ranks CVEs.
2. **Enrichment.** `src/enrich_top500.py` joins ranking outputs with vulnerability
   text / references into `results/top500_enriched.csv` (separate from audited
   `top500.csv`).
3. **Generation.** `src/remediation_agent.py` calls **Gemini 2.5 Flash**
   (`google-genai`) with a strict JSON schema: executive summary, triage
   explanation, immediate mitigation, patch guidance, `is_ai_generated`.
4. **Grounding guards.** Patch URLs must appear in source references; otherwise
   the agent emits the fixed “no verified vendor patch URL” message. Eval
   (`src/eval_playbooks.py`) measures schema conformance, priority preservation,
   vendor grounding, and patch-URL hallucination.
5. **Artifacts (Gemini-only).**
   - `results/cached_playbooks.json` — generated playbooks
   - `results/agent_eval_report.json` — smoke-suite metrics
   - `results/gemini_explanations_top100.json` — normalized dual-API payload
   - `results/gemini_subset_comparison.json` — Granite ↔ Gemini head-to-head note

## Architectural contrast

| Dimension | IBM Granite (watsonx) | Gemini 2.5 Flash |
|-----------|----------------------|------------------|
| Primary role | Dense **768-d** multilingual embeddings + optional instruct narrative | Long-context **generative** remediation playbooks |
| Representation | Truncated at 512 tokens / text; L2-normalised vectors | Free-form grounded prose under JSON schema |
| Token economics | Lite plan metered FM tokens (~233k on the embedding subset run) | Small smoke suite (5 playbooks); latency null in report |
| Cold-start / new CVE | Embedding similarity over known corpus; ranking features still required | Can draft mitigations from description + references once enriched |
| Failure mode on Lite | Instruct IDs often unavailable → offline template narratives | Missing API key → cached playbooks / eval-only path |
| Hallucination control | Grounding check rejects invented patch versions/URLs in narratives | Measured **0%** patch-URL hallucination on smoke suite |

Granite’s strength is a **stable embedding geometry** for similarity and
leakage-aware text features. Gemini’s strength is **operational depth**:
executive framing, immediate mitigation, and patch guidance in one structured
object judges can read in the dashboard toggle.

## Smoke-suite metrics (from `agent_eval_report.json`)

| Metric | Value |
|--------|------:|
| Playbooks evaluated | 5 |
| Schema conformance | 100% |
| Patch URL hallucination | 0% |
| Vendor grounding pass | 100% |
| Priority preservation | 100% |
| Overall pass | 100% |
| Avg latency (s) | null (not recorded in this run) |

These IDs (`CVE-2026-10001`…`10005`) are the Gemini judge-sample set. Production
ranked CVEs (e.g. `CVE-2026-10523`) currently have Granite narratives; the UI
toggle shows whichever provider has text for the selected CVE.

## Cold-start & defense notes (judging)

- **Cold-start CVE** (no prior KEV / sparse history): Granite embeddings still
  place the description in a multilingual space for nearest-neighbour context;
  Gemini can verbalise mitigations from the enriched description without waiting
  for a large labelled remediation corpus.
- **Defense-in-depth presentation:** keep ML rank authoritative; treat both LLMs
  as *explain / act* layers. Prefer Gemini when operators need a playbook; prefer
  Granite when comparing semantic neighbours or embedding-augmented models.
- **Do not claim** Gemini improved AUC over TF-IDF — that delta is Granite’s
  embedding experiment only (`mean_delta_auc_granite_minus_tfidf` in
  `granite_subset_comparison.json`).

## API surface (additive)

- `GET /api/explanations/{cve_id}?model=granite|gemini|both` — dual payload
- `GET /api/models/comparison` — head-to-head telemetry
- Existing Granite routes (`/api/stats/summary`, `/api/ranking/cves`, default
  explanations) remain unchanged in behaviour for Granite fields.
