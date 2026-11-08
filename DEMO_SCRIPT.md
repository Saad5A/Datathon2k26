# Demo video script (2:30)

Target length 2:30 (limit 2 to 3 minutes), read at a calm pace. Record the live app at https://pancakess.work/ (home) and https://pancakess.work/results (evidence page). Screen names below match `dashboard/src` at the time of writing; another teammate is still editing the dashboard, so re-check every label right before recording.

Recording rules:
- The score column is labelled "Priority score". Call it a ranking score, never a chance or percentage of attack.
- Do not show or mention Gemini. No Gemini output exists in this build. Keep the "Google Gemini" pill in the home banner and the "Google Gemini · Executive Brief" card in the side panel out of frame (crop or scroll past them).
- Do not click "Explain this rank" on camera; it returns a template answer.
- Do not film section 03 of /results. Its "Paired bootstrap · AUC vs exploit→EPSS" card shows a seed-median interval, which is not a verified claim; the narration uses the verified seed-set-0 interval instead.
- Every number spoken below is a verified claim. Do not add or round any.

Slides marked [SLIDE] are not in the app; make them as plain title cards with exactly the text given.

---

## 0:00-0:10 · Hook
**On screen:** [SLIDE] "Which of the 72,670 vulnerabilities on the 2026 scoreboard will attackers use? PancakeSec · IBM Before the Breach"

**Narration:**
"Which of the 72,670 vulnerabilities on the 2026 scoreboard will attackers actually use? First, a trap that standard backtests can fall into."

## 0:10-0:40 · The hidden leak
**On screen:** [SLIDE] Two lines of text:
- "2025 test: CVEs later added to KEV with NIST status 'Analyzed': 52 of 52"
- "All other test CVEs with status 'Analyzed': 50.1%"

Then add one line: "Product count alone, AUC 0.767 · EPSS, AUC 0.707 (intervals overlap)"

**Narration:**
"In our 2025 backtest, all 52 vulnerabilities later added to CISA's Known Exploited Vulnerabilities list, KEV, had NIST status 'Analyzed'. Of the rest, only 50.1% did. The organisers' README notes that NIST reviews attacked vulnerabilities first, so these fields partly record that an attack was already noticed. The product count alone scores a higher AUC, a measure of how well a list puts exploited above non-exploited, than EPSS, the usual exploitation score: 0.767 against 0.707, though the intervals overlap."

## 0:40-1:00 · Why it matters
**On screen:** [SLIDE] "Excluded: nvd_status, n_affected_cpes, n_references, CVSS and CWE fields, blank-score patterns, references.csv, affected_products.csv" and below it "2026, August-September: 66-68% of CVEs have no product list"

**Narration:**
"Why it matters: such a model looks great in a backtest but reads NIST's reaction to attacks, which new vulnerabilities lack. In August and September 2026, 66 to 68% have no product list. So we left those fields out and used only what was known at each snapshot month, apart from today's description text."

## 1:00-1:30 · The honest backtest
**On screen:** https://pancakess.work/results. Start on the hero "The queue is not a guess. It is a measured ordering." and the KPI tile "Top-500 hits · fold 1". Scroll to section 01 "Head-to-head" and hold on the chart "ROC AUC by method" (do not scroll into section 03).

**Narration:**
"Then we tried to break our own result. Our first pass found 25 top-500 hits, against 18 to 19 for 'exploit code first, then EPSS'. It was inflated by training labels overlapping the test period, and by seed luck. With time-safe labels, the submitted model gets 20 against 18 in one fold, and 11 against 15 in the other. Its AUC is higher, but for our base model's first seed set, the paired interval on that gain includes zero. Borderline."

## 1:30-1:40 · Discipline
**On screen:** quick cut to https://pancakess.work/evolve/ (the evolution observatory).

**Narration:**
"An automated search over many variants found none that passed the gate we wrote down in advance, so the submitted model stayed."

## 1:40-2:05 · What we built
**On screen:** https://pancakess.work/ home. Show the "3D Stack" view, then click "Table (72,670)" to show "Audited CVE Exploitation Ranking". Set "Filter Tiers" to P0. Point at the "Priority score" and "Public exploit code" / "None recorded" columns. Click one P0 row ("Triage →"), which opens the 3D view with that CVE selected. In its side panel, the summary card is headed "IBM Granite (AI-generated summary)" or "Template (no AI)" with the model ID badge; scroll past the Gemini card to "Nearest neighbours · IBM Granite". End by pointing at the "top500.csv" button in the header.

**Narration:**
"This is the 2026 queue: the top 100 are tier P0, the next 400 P1. Each carries up to three reasons, the signals that moved its score most; the table shows the strongest. Select one to see similar vulnerabilities, found with a separate, smaller IBM Granite model that does not affect the ranking. No assigner fills more than 50 of the top 500. One click downloads our submitted file."

## 2:05-2:30 · IBM technology, limits, close
**On screen:** /results section 04 "What we refuse to claim" (cards "No 2026 accuracy", "Top-500 is noisy", "KEV is a proxy"), then an end card [SLIDE] "github.com/Saad5A/Datathon2k26 · pancakess.work".

**Narration:**
"IBM Granite embeddings of every masked description, some also run through watsonx.ai, are in the final model, adopted by a tie-break we declared in advance, with no measurable gain. Limits: KEV lists only confirmed attacks, one test hit is about 2% of 52 positives, and we have no 2026 labels. Descriptions are today's text, and our first pass had already used the 2025 period."
