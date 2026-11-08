# PancakeSec — 3-minute demo script

**Target:** 3:00 (hard limit 3:00). Calm pace.
**Record:** full HD or better, 16:9, cursor visible, clean browser window.
**Live app:** <https://pancakess.work/> · **Evidence page:** <https://pancakess.work/results>

> Every number in the narration is a verified claim. Do not ad-lib a new number, average, or percentage.
> The score is a **ranking score**, never a probability or an accuracy.

## Before you record

- Open these tabs in order: **Home**, **/results**, **/evolve/**, **GitHub repo**.
- On Home: keep **3D Stack** for the opening; switch to **Table (500)** for the demo.
- Pre-select the CVE you will click. **CVE-2026-10523** is the safe demo row.
- Test the Judge Q&A with **“What does KEV stand for?”** before recording. Do not ask it for metrics; live answers are not audited claims.
- Check that the side panel shows the Granite brief and **Nearest neighbours**. The Gemini card may be empty in this build; do not promise it on camera.
- Record two takes. Keep the cursor still while narrating.

## Shot list

| Time | Visual | Purpose |
|---|---|---|
| 0:00–0:10 | 3D stack, slow rotate; overlay “72,670 CVEs” | Hook |
| 0:10–0:32 | Slide: NIST fields crossed out; quick cut to /results limits | The hidden leak |
| 0:32–1:00 | Animated stack diagram over Home | Technical model |
| 1:00–1:25 | /results hero, AUC chart, top-500 tile | Honest result |
| 1:25–2:05 | Home → Table (500) → P0 → CVE → neighbours → Judge Q&A | Live product |
| 2:05–2:30 | /results checks + /api/docs + /evolve + GitHub | Engineering and audit |
| 2:30–2:50 | /results “What we refuse to claim” | Limits |
| 2:50–3:00 | End card with URLs | Close |

---

## 0:00–0:10 · Hook

**Visual:** Home, 3D pancake stack rotating. Overlay, large:

> **72,670 CVEs. Which ones will attackers actually use?**

**Narration:**
“There are 72,670 vulnerabilities on the 2026 scoreboard. A scanner tells you what is missing a patch. It cannot tell you what attackers will actually use. We built PancakeSec to rank that queue — then tried to prove ourselves wrong.”

---

## 0:10–0:32 · The trap we found

**Visual:** Slide, then a quick cut to the limits cards on `/results`.

On-screen text:

> **The leak:** `nvd_status` · product count · reference count · CVSS/CWE blank patterns  
> **All 52 KEV positives were “Analyzed.” About half of the negatives were.**

**Narration:**
“Our first backtest looked too good. Every KEV-positive CVE in the test had NIST status ‘Analyzed’; only about half of the negatives did. NIST reviews attacked CVEs first, so that column was recording the answer. We excluded it, plus product counts, reference counts, and the CVSS/CWE blank-score fields.”

---

## 0:32–1:00 · Inside the model

**Visual:** Animated stack diagram over a dimmed Home screen. Four boxes light up in sequence:

> **1. Exploit signals** — EPSS + 4 public-exploit flags, at the snapshot month  
> **2. Assigner history** — prior KEV rate and count, strictly before the month  
> **3. Two text scores** — TF-IDF words + IBM Granite meaning, out-of-fold  
> **4. Gradient-boosted trees** — depth 3, 150 trees, 5 seeds

**Narration:**
“What remains is time-safe. At each snapshot month: EPSS and four exploit flags; the assigner’s prior KEV rate; and the masked description. Two text models read it: TF-IDF for words, and IBM Granite for meaning. Each becomes an out-of-fold score, so the trees never see a row’s own label. Gradient-boosted trees — depth three, 150 trees, five seeds — combine them into one ranking score.”

**Technical overlay (optional, 3 s):**
> “Granite vectors → logistic score → trees. No raw embedding vectors fed to the trees.”

---

## 1:00–1:25 · The honest result

**Visual:** `/results` hero. Then section 01 “Head-to-head”, hold on the AUC chart and the Top-500 tile.

**Narration:**
“On the 2025 backtest, G2 has a mean AUC of 0.871, against 0.732 for CVSS and 0.707 for EPSS. The typical exploited CVE sits around rank 1,288 instead of 7,960. But top-500 is noisy: 20 of 52, then 11 of 32. And G2 is not an improvement over its base model: 0.871 versus 0.870. Granite was adopted by a tie-break declared in advance — with no measurable gain.”

**On-screen:** “AUC = chance a random exploited CVE ranks above a random non-exploited one.”

---

## 1:25–2:05 · Live product demo

**Visual:** Home. Hold the 3D stack, then click **Table (500)**.

**Narration:**
“This is the live queue. The 3D stack samples the tiers; the table shows all 500. Filter to P0 — the top 100. Each row carries its strongest reasons.”

**Visual:** Click a P0 row (**CVE-2026-10523**). The side panel opens.

**Narration:**
“Select one: the Granite brief, and nearest neighbours from a separate Granite index. Retrieval only — it never changes the score.”

**Visual:** Scroll to **Nearest neighbours · IBM Granite**, then click **Judge Q&A**.

**Narration:**
“The Judge Q&A is live Gemini, with the active CVE in context.”

**Visual:** Ask **“What does KEV stand for?”** Hold on the answer for two seconds.

**Narration:**
“Upload your own CSV: known rows reuse the audited score; unknown rows get a transparent fallback. Export downloads the top 500.”

---

## 2:05–2:30 · Engineering and audit

**Visual:** `/results` section 03 “The checks that could have killed it”, then quick cuts to `/api/docs`, `/evolve/`, GitHub.

**Narration:**
“FastAPI serves the audited files; React and Three.js render the queue. The rules were pre-registered; an independent auditor re-derived the numbers, and a claims ledger marks what is verified. The evolution search found no variant that passed the gate, so the model stayed.”

**On-screen:** “Claims ledger · independent audit · pre-registered rules.”

---

## 2:30–2:50 · Limits

**Visual:** `/results` section 04 “What we refuse to claim”. Hold on the cards **No 2026 accuracy**, **Top-500 is noisy**, **KEV is a proxy**.

**Narration:**
“No 2026 accuracy — there are no labels. KEV is a proxy; one hit is about 2% of the 52-positive test. Top-500 is noisy. Descriptions are today’s text, and the test period was used for model selection.”

---

## 2:50–3:00 · Close

**Visual:** End card with logo and URLs:

> **pancakess.work**  
> **github.com/Saad5A/Datathon2k26**  
> “A measured ranking. An honest audit.”

**Narration:**
“PancakeSec: a measured ranking, an honest audit, and a queue your team can work. Code and evidence at pancakess.work.”

---

## Do not say on camera

- “The score is a probability of attack.” → Say **ranking score**.
- “Granite improves accuracy.” → Say **adopted by the pre-registered tie-break, no measurable gain**.
- “We catch 20 out of 52, so we are 38% accurate.” → Say **20 of 52 exploited CVEs reached the top 500**.
- “We beat the baselines on top-500.” → Say **the top-500 count is noisy; AUC and median rank are the steadier result**.
- “This is RAG.” → The neighbour panel is **retrieval-only**; the Judge Q&A is a separate live Gemini chat.
- “We know the 2026 accuracy.” → **No 2026 labels; no 2026 accuracy claim.**
- Any live Gemini answer as a metric or fact. Label it **AI-generated**.

## If you need to cut 15 seconds

Drop the upload/export sentence in 1:25–2:05 and shorten the engineering section to:

> “FastAPI serves the audited files; React and Three.js render the queue. The rules were pre-registered, and an independent auditor re-derived the numbers.”
