# Primer (plain English)

## Security terms
- **CVE**: a public ID for one vulnerability, e.g. CVE-2024-3400. **NVD**: US NIST database of CVEs with scores and details. **CNA/assigner**: the organization that issues a CVE ID (often the vendor, or a firm like GitHub/VulnCheck/MITRE).
- **CVSS**: severity score 0-10 (how bad if attacked), not likelihood of attack. **EPSS**: model estimating the chance a CVE is attacked in the next 30 days (FIRST.org).
- **KEV**: CISA's Known Exploited Vulnerabilities list = confirmed attacks. Our answer key. A CVE not on it may still be attacked.
- **CWE**: type of weakness (e.g. CWE-79 cross-site scripting). **CPE**: NIST naming for affected products. **Exploit code flags**: public code exists on Exploit-DB, Metasploit, a Nuclei scanner template, or a GitHub proof of concept.
- **Remote / unauthenticated / no user interaction**: the attacker needs no login or click: classic attack targets.

## ML terms
- **Row, feature, label**: one example (a CVE at a snapshot month), what we know about it, and the outcome (later added to KEV or not).
- **Class imbalance**: only about 0.15% of rows are positive.
- **Train/validation/test and time split**: learn on earlier data, judge on later data; a random split would leak the future.
- **Overfitting**: memorizing training data; shows as great training and poor held-out results.
- **Logistic regression**: weighted checklist turned into a probability. **Gradient-boosted trees**: many small decision trees, each fixing the previous ones' errors. **TF-IDF**: turns text into word-importance numbers. **Embedding**: a list of numbers capturing a text's meaning (Granite embedding model).
- **Metrics**: top-500 hits = positives among our 500 highest-ranked; AUC = chance a random positive outranks a random negative (0.5 is chance); average precision = quality of the ranking at the top; median rank of positives = how far down the list the typical attacked CVE sits; bootstrap interval = uncertainty range from resampling.
- **Leakage**: using information that would not exist at prediction time (e.g. NVD fields filled in after an attack). Makes results look great and fail in reality.
- **Permutation test**: shuffle the training labels; performance should collapse to chance.
- **Ablation**: remove one feature group at a time to see what it contributes.
