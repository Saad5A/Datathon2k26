# Pitfalls

## Data
- NVD files are today's versions; fields can be filled in after attacks (leakage). See 01.
- Use `published`, not the year in the CVE id. June 2026 has no signals (use snapshot July). Feb 2025 signals missing about 14.5k CVEs. EPSS model changed March 2025.
- KEV `date_added` before `published` for 62 CVEs: exclude carefully when building labels.
- About 11.8k ids in the signals files are rejected IDs: inner-join to vulnerabilities.csv.
- Right-censoring: later snapshot months have less time to be exploited; we cap the label window and the judges' window varies (about 1.5 months for Sep to about 10 months for Jan).
- Memory: files up to 238 MB; read with usecols/chunks (linked machine has about 3 GB RAM).

## Modelling
- Only about 65 training positives: keep models small, regularized; do not tune endlessly.
- Comparing many variants on one test set inflates the best score.
- Vendor/assigner priors must be computed only from KEV rows added BEFORE the snapshot month, ideally over a recent window (24 months) because 2026's mix shifted.
- Assigner and text features overlap (the text model partly learns vendor names).
- Risk of one assigner flooding the top 500 (Chrome, Microsoft): cap and test.
- AUC above about 0.93 or a sudden jump in hits: suspect leakage.
- We have NO 2026 labels: no 2026 accuracy claims.

## Process / LLM
- Gemini/Granite text must not invent patch versions, URLs, product names or CVE facts; grounding check required; label AI-generated.
- Scores are rankings, not probabilities.
- Never commit or print API keys; `.env` is gitignored.
- Do not rely on memory for model IDs, SDK calls or statistics.
