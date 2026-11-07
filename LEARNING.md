# Learning guide: how our vulnerability ranking works

This is for teammates who are new to machine learning (ML). Read it top to bottom once, then use it as a lookup. The shorter glossary is in `docs/kb/03_primer.md`.

**How to read the numbers here**
- Anything labelled "Toy example" uses numbers we made up to explain an idea. Never quote them.
- A real project figure is always marked "(first pass, not yet verified)". It comes from `docs/kb/`, and no audit has checked it. Do not publish it.
- This guide states no model results. Those live in the claims ledger (`results/claims*.json`) once the auditor verifies them.

## The project in one paragraph

A **CVE** is a public ID for one software vulnerability. New CVEs appear far faster than anyone can fix them, so teams need to know what to fix first. We rank CVEs by how likely attackers are to exploit them. The judges count how many of our top 500 later appear on **KEV**, the Known Exploited Vulnerabilities list from CISA (a US government security agency).

Three more terms come up a lot:
- **CVSS**: a 0-10 score for how bad an attack would be. It does not say how likely an attack is.
- **EPSS**: a public model's estimate of the chance a CVE is attacked in the next 30 days.
- **Assigner**: the organization that issued the CVE ID, often the software vendor.

## Row, feature and label

- **Row**: one example. For us, one CVE as it looked at the end of one month, called its **snapshot month**.
- **Feature**: something we knew about that row at that time, such as its EPSS score.
- **Label**: the outcome we want to predict. For us: was this CVE added to KEV after the snapshot month? Yes is 1 (a **positive**), no is 0 (a **negative**).

**Toy example (invented numbers):**

| cve_id | snapshot month | epss | public exploit code? | assigner's past KEV entries | label |
|---|---|---|---|---|---|
| CVE-TOY-0001 | March | 0.02 | yes | 12 | 1 |
| CVE-TOY-0002 | March | 0.001 | no | 0 | 0 |

The model sees everything except the label and learns how the columns relate to it.

**One honest limit:** KEV lists confirmed attacks only. A CVE that is not on KEV may still have been attacked, so our label stands in for "exploited" without matching it exactly. The word for this is a **proxy**.

## Why so few rows are positive

Most vulnerabilities are never seen being attacked. Attackers concentrate on a small number that are useful to them, and KEV only records the attacks that were confirmed. In our backtest (a replay of the method on past data), only about 0.15% of rows are positive (first pass, not yet verified). This situation is called **class imbalance**.

**Toy example (invented numbers):** take 10,000 rows with 15 positives.
- A "model" that always answers "no" is right 9,985 times out of 10,000. That is 99.85% accuracy, and it catches nothing. So we do not use accuracy.
- Picking 500 rows at random catches 0.75 positives on average (500 x 15 / 10,000).

What this means for us:
- We judge the order of the list, using the metrics further down.
- With so few positives, big models memorize instead of learning, so we keep ours small.
- One lucky or unlucky CVE moves the results a lot, so we always report a range.
- Our scores put CVEs in order. They are not probabilities, so never say "this CVE has an X% chance of attack".

## Train vs validation, and why we split by time

- **Training set**: the rows the model learns from.
- **Validation set** (also called a held-out set): rows kept away from the model and used only to score it. You will also see "test" used for this. In our docs, the 2025 "test" pool and the "validation" set mean the same rows.

Our main split is to train on CVEs from 2024 and validate on CVEs from January to September 2025. A second split trains on July 2024 to March 2025 and validates on April to September 2025. We report both.

**Why not split at random?** A random split lets the model learn from the future. In real use we only ever have the past.

**Toy example (invented numbers):** attackers hit a product called ToyVPN in June. Three ToyVPN CVEs from around that time reach KEV.
- With a random split, two land in training and one in validation. The model learns "ToyVPN means attack" and then "predicts" the third. Suppose this scores 20 hits.
- With a time split, the model trains only on rows before June and has never seen this campaign. Suppose this scores 9 hits.

The 9 is the honest number, because it matches the position we are in when predicting new CVEs.

## Overfitting

**Overfitting** means memorizing the training rows instead of learning patterns that carry over to new rows. The sign is a great score on training data and a poor score on held-out data.

**Toy example (invented numbers):** a model scores 0.99 on training rows and 0.60 on validation rows. It may have learned "a description containing this one odd phrase means positive", which was true for one CVE and means nothing elsewhere.

We fight overfitting by keeping models small, adding **regularization** (a penalty on complicated models), and always scoring on held-out rows. We have only about 65 training positives (first pass, not yet verified), so this matters a lot.

## Logistic regression

Think of a weighted checklist. Each feature adds or subtracts points, and a formula squeezes the total into a number between 0 and 1. Training finds the weights.

**Toy example (invented weights):** start at -3, add 2 if public exploit code exists, add 1 if no login is needed.

| CVE | total points | squeezed to 0-1 |
|---|---|---|
| Neither | -3 | about 0.05 |
| No login needed | -2 | about 0.12 |
| Exploit code and no login needed | 0 | 0.50 |

It is simple, hard to overfit, and you can read the weights to see why a CVE scored high. The weakness is that it cannot easily capture "this feature matters only when that other one is true" unless you build that in by hand.

## Gradient-boosted trees

A **decision tree** is a small flowchart of yes/no questions. **Gradient boosting** builds many small trees in a row, and each new tree tries to fix the errors the earlier ones still make. The final score adds up all the trees. We use scikit-learn's HistGradientBoosting and keep the trees shallow.

**Toy example (invented points):**
- Tree 1 asks "public exploit code?" Yes gets +3, no gets 0.
- Looking at the remaining errors, tree 2 asks "exploit code, but an assigner with no KEV history?" Yes gets -1, no gets 0.

| CVE | tree 1 | tree 2 | total |
|---|---|---|---|
| Exploit code, assigner with KEV history | +3 | 0 | 3 |
| Exploit code, assigner with no history | +3 | -1 | 2 |
| No exploit code | 0 | 0 | 0 |

Trees capture feature combinations by themselves, which logistic regression cannot. The price is that they overfit more easily, which is why we keep them shallow.

## TF-IDF

Models need numbers, so text has to be converted. **TF-IDF** gives each word a score: how often it appears in this description (term frequency, TF) times how rare it is across all descriptions (inverse document frequency, IDF). Common words score near zero and distinctive words score high.

**Toy example (invented numbers):** we have 1,000 descriptions, using a base-10 logarithm for rarity. Real libraries adjust this formula slightly, but the idea is the same.

| word | times in this description | descriptions containing it | rarity | TF-IDF |
|---|---|---|---|---|
| the | 3 | 1,000 | log10(1,000 / 1,000) = 0 | 3 x 0 = 0 |
| unauthenticated | 1 | 10 | log10(1,000 / 10) = 2 | 1 x 2 = 2 |

We feed these word scores into logistic regression to get one "text score" per CVE. The gradient-boosted trees can then use that score as a feature.

Two traps:
- **Out-of-fold scores.** If the text model scores rows it trained on, those scores look better than they should and the trees trust them too much. So we split the training rows into parts and score each part with a text model trained on the other parts.
- **Hidden vendor names.** Words like a product name mean the text model partly re-learns which vendor is involved, which overlaps with the assigner feature (first pass, not yet verified).

## Embeddings

An **embedding** turns a whole text into a list of numbers that captures its meaning, so texts with similar meanings get similar lists. We plan to get ours from an IBM Granite embedding model.

**Toy example (invented numbers, and real lists are much longer):**

| description | embedding |
|---|---|
| Attacker can run code without logging in | [0.9, 0.1, 0.2] |
| Remote code execution, no authentication needed | [0.8, 0.2, 0.2] |
| Wrong button colour on the settings page | [0.1, 0.9, 0.1] |

The first two lists are close even though the sentences share few words. TF-IDF treats "without logging in" and "no authentication" as unrelated words. That is the appeal of embeddings. Whether they beat TF-IDF on our held-out data is still an open question, and we will only know after testing.

## How we score a ranking

All the toy examples in this section use this invented list of six CVEs, best-ranked first (P is a positive, N is a negative):

`rank 1: P | rank 2: N | rank 3: P | rank 4: N | rank 5: N | rank 6: N`

### AUC

**AUC** is the chance that a randomly chosen positive is ranked above a randomly chosen negative. 0.5 is coin-flip quality and 1.0 is perfect.

**Toy example:** there are 2 positives and 4 negatives, so 8 possible pairs. The positive at rank 1 beats all 4 negatives. The positive at rank 3 beats 3 of them. So AUC is 7 / 8 = 0.875.

AUC looks at the whole list, so it can be high even when the very top is mediocre. Our project rule is that an AUC above about 0.93 means we stop and hunt for leakage (explained below).

### Average precision

**Precision** at a point in the list is the share of rows so far that are positive. **Average precision** takes that value at each positive and averages them, so it rewards putting positives right at the top.

**Toy example:** at rank 1, precision is 1/1. At rank 3, it is 2/3. The average is about 0.83. If the positives had instead been at ranks 3 and 4, it would be (1/3 + 2/4) / 2, about 0.42.

Do not be alarmed by small average precision values in our work. A random list scores about the share of positives, which is tiny here, so compare against that and against the baselines.

### Top-500 hits

**Top-500 hits** is how many positives land in our 500 highest-ranked rows. This is what the judges count.

**Toy example:** a top-2 cut of our list has 1 hit, and a top-3 cut has 2.

It is easy to explain but noisy, because it ignores everything below the cut. With about 52 test positives, one hit is about 2% (first pass, not yet verified). Also, the 2026 pool is about twice as large as our test pool, so a top 500 there is a stricter cut, closer to a top 250 here (first pass, not yet verified).

### Median rank of positives

Line up the rank of every positive and take the middle one. It tells you how far down the list the typical attacked CVE sits. Lower is better.

**Toy example (a different, invented list):** positives at ranks 3, 40, 90, 700 and 5,000 have a median rank of 90. The one at 5,000 does not distort it, which an average would.

### Work saved

**Work saved** asks how many CVEs a team must fix, working down the ranking, to catch half of the ones later exploited. We compare this between rankings.

**Toy example (invented numbers):** there are 10 positives, so half is 5. Ranking A reaches its 5th positive at rank 1,200 and ranking B at rank 300. Ranking B saves 900 fixes, which is 75% less work than A (900 / 1,200). This is the most practical number for a real security team.

## Bootstrap intervals

Our test set is one sample, and a slightly different set of CVEs would give a different score. A **bootstrap** estimates how much that matters:
1. Draw rows at random from the test set, the same number as the original, allowing repeats.
2. Recompute the metric on that redraw.
3. Repeat many times, sort the results, and keep the middle 95%. That range is the **95% interval**.

**Toy example (invented numbers):** rows A B C D E might redraw as A A C D E. After 1,000 redraws of a larger test set, a ranking with 12 hits might have an interval of 7 to 17. We would then say "12 hits, plausibly anywhere from 7 to 17".

To compare two rankings, redraw the same rows for both and look at the interval on the difference between them. If it comfortably includes zero, we cannot claim that one is better.

## The leakage columns

**Leakage** means using information that would not have existed at prediction time. Results look great in testing and then fail in real use, because the model is reading the answer instead of predicting it.

Why it can happen here: NIST files are today's versions, not historic copies, and NIST (the US agency that runs the NVD vulnerability database) reviews attacked CVEs first and fills in their details afterwards. So some columns partly record "someone already noticed this was attacked". They give away the answer for 2026, and we never use them as model features:

| Column | What it is | Why it cheats |
|---|---|---|
| `nvd_status` | How far NIST's review has got | Attacked CVEs get reviewed sooner |
| `n_affected_cpes` | How many affected products NIST has listed | The list gets filled in during that review |
| `n_references` | How many web links the CVE has | Attacked CVEs collect more links over time |
| Blank severity scores | Whether a CVSS score is still missing | A blank means "not reviewed yet", so a filled score can hint at attention |
| News/threat links in `references.csv` | Links to reports about the vulnerability | A threat report can be written because of the attack. Links to IBM X-Force Exchange are treated as leak-prone too |

**Toy example:** on the same day, two toy CVEs are published. Attackers hit CVE-TOY-A in May, so NIST reviews it, lists 40 products and adds 15 links. CVE-TOY-B is ignored, with 0 products and 1 link. A model trained on these counts will rank A high, but in the snapshot month those counts did not exist yet. It is really detecting that attention came later.

A related judgement call: `cvss3_score`, `cwe_ids` and the `attack_*` columns are also filled in by NIST's analysis. Our preferred model avoids them, and we use them only to measure what they would add.

**Leaks can also come from our own calculations.** A feature like "how many KEV entries does this assigner have?" must only count KEV rows added before the snapshot month. Using the whole KEV file sneaks the future in. Our first pass made this mistake on two side statistics, and `docs/kb/02_findings_first_pass.md` records the correction. Everyone can slip here, which is why an independent auditor checks the work.

## Why ties matter when you rank

Many CVEs can share exactly the same score. When a ranking has more tied CVEs than slots left, the order inside the tie, and so who makes the cut, is decided by something arbitrary such as file order.

**Toy example (invented numbers):** a CVSS ranking has 200 CVEs at 10.0 and 1,000 CVEs at 9.8. The first 200 slots are clear. The other 300 slots go to 300 of the 1,000 tied CVEs. If 6 positives sit among those 1,000, a random pick catches 1.8 of them on average (6 x 300 / 1,000), and any given pick might catch 0, or 4.

So a baseline's hit count is one draw, not a fixed fact, and a small win over it may only be tie luck.

What we do about it:
- Write down the tie-break rule, and use the same one for every ranking we compare.
- For rankings with many ties, repeat the count with shuffled tie order and report the range.
- Check our own model too, since small trees can give many rows the same score.

AUC handles ties by counting a tied pair as half a win, so top-500 hits are much more exposed to this problem.

## Why comparing many models on one test set flatters the winner

Each score contains some luck. If you try many models and keep the best score, you are partly selecting for luck, so the winner's score is too high as an estimate of how it will do next time. This is called **selection optimism**.

**Toy example (invented setup):** 20 students all guess randomly on a 10-question true/false quiz. The average is 5 correct. There is about a two-in-three chance that at least one of them gets 8 or more. That student is not smart, and would likely score about 5 on the next quiz.

Our first pass compared several variants on the same test set, so this applies to it (first pass, not yet verified).

What we do about it:
- Decide a small list of candidate models **before** looking at validation results.
- Do any tuning with **cross-validation** inside the training years only. Cross-validation means repeatedly holding out part of the training data to check a choice.
- Use the second time split as a further check.
- Record the held-out numbers in `LOG.md` and freeze them.
- Say how many models we compared, and report intervals.

## Why refitting on all labelled data at the end is OK

The process has two separate jobs:
1. **Estimate quality.** Train on the earlier data, score on held-out data, and freeze those numbers.
2. **Build the final model.** Use the same recipe (same features, same settings) and train it on all labelled 2024-2025 data.

This is OK because positives are scarce and throwing some away would weaken the final model. In the combined pool we have about 117 positives, compared with about 65 for the 2024 training alone (first pass, not yet verified). Nothing is being chosen at this step: the recipe was fixed before the refit.

**The honest estimate is the frozen held-out number**, and it stays that way after the refit.

**Toy example (invented numbers):** the recipe trained on the early data scores 12 hits on the held-out data, with an interval of 7 to 17. After the refit, scoring that same 2025 data gives 30 hits. The 30 means nothing, because the model has now trained on those rows and is grading its own homework. We report 12, with its interval.

Even that is an estimate for a recipe on past data, not a promise about 2026.

## Why we can make no accuracy claim about 2026

Our KEV file stops at 2025-12-31, so we hold no labels for CVEs in 2026. Only the judges can count hits, using KEV additions through November 4, 2026. A claim about accuracy needs an answer key, and we do not have one.

2026 also differs from our test period: the number of CVEs rose and the mix of assigners shifted. CVEs from later months also have less time to reach KEV, about 1.5 months for September versus about 10 for January (first pass, not yet verified). The final count could land anywhere in a wide range, partly by luck.

**What we can say about 2026:**
- How it differs from earlier years (distributions and shift).
- What our model ranked, and which signals drove it.
- What our held-out results were on 2025, clearly labelled as past data.

**What we cannot say:**
- "Our model catches X of the attacked CVEs in 2026."
- "We expect exactly X hits."
- "This 2026 CVE will be attacked."

**Good sentence:** "On held-out 2025 data, our ranking caught X positives, with an interval of Y to Z. 2026 is different, and we have no labels to check it against." Fill in X, Y and Z only from verified claims.

## What we did, phase by phase
