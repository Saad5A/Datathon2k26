# Event, rules, judging

## Event [SOURCE: Sheridan Datathon -Opening.pdf, IBM/README.md]
- Sheridan Datathon 2026, Nov 7-8, Sheridan College, Hazel McCallion Campus. MLH (Major League Hacking) is the hackathon organizer; coaches Sara and Brian. MLH resources: mlh.link/sheridan, hack.mlh.com. Code of conduct: mlh.com/code-of-conduct (incidents@mlh.io).
- Sat workshops (from the opening deck): TechTogether meetup 4:30-5:00 pm room C208; Intro to Google AI Studio 7:30-8:00 pm room C506; Hacking with GitHub Copilot 8:00-8:30 pm room C506. Sunday: demo to earn the MLH "I Demoed" sticker.
- Our track: IBM, "Before the Breach". Other sponsor tracks (not ours): ElevenLabs, NASA, Tangerine. A team picks ONE sponsor track; MLH prize tracks can be combined freely.
- Submission deadline: [UNKNOWN] (not in the deck or READMEs; check Devpost).

## Judging (general datathon rubric, image from the organizers) [SOURCE]
Discovery 35% (non-obvious, meaningful, evidence-backed), Data Use 25% (sound analysis, cleaned and questioned the data, honest about limits), Communication 25% (story clear in the first minute; charts and demo support the finding), Impact 15% (matters to a real user/decision/community; realistic next step). IBM/README.md restates these four for the IBM track.

## IBM track rules [SOURCE: IBM/README.md]
- Task: using real vulnerability data, predict which vulnerabilities attackers will exploit and show engineers what to fix first and why. Ground truth = CISA Known Exploited Vulnerabilities (KEV) list.
- MUST use at least one IBM technology (Granite models, Granite TimeSeries, watsonx.ai / Orchestrate, Red Hat AI Inference Server / vLLM).
- Benchmark: `scoreboard_2026.csv` = 72,670 CVEs published Jan-Sep 2026 not on KEV at the end of their `snapshot_month`. Rank them using only what was known at the end of that month. Judges count how many of our top 500 were added to KEV through Nov 4, 2026. Submit `top500.csv` with ONE column `cve_id`.
- Judges' reference baselines (found in top 500): highest CVSS3 first = 7; EPSS first = 6; public exploit code first then EPSS = 8.
- Fairness: for 2026 CVEs, `nvd_status`, `n_affected_cpes`, `n_references`, blank severity scores and news/threat-report links in `references.csv` can give away the answer. The write-up must say which columns we used.
- Submit on Devpost: 2-3 minute demo video, code repo, short write-up, links to any outside data, and the top 500.

## MLH prize tracks (optional extras) [SOURCE: opening deck]
Best Use of Gemini API (MLH+DEV swag), Solana (hardware wallets), Tiger Data (Stream Deck Mini), Vultr (M5Stack Tab5; promo code MAJORLEAGUEHACKING), Snowflake API (Arduino kits), GoDaddy Registry domain (gift card; code MLHSD91), Entire (mini projector), DEV Writing Challenge ($100). Details/rules are behind the links on the slides (mlh.link/...): [UNKNOWN] until read.
