# IBM data guide [SOURCE: IBM/DATA_DICTIONARY.md unless tagged otherwise]
Location: `~/Working/datathon/IBM/data.zip`; unzipped copy at `~/Working/datathon/_probe/ibm/data/`. Never modify originals. Join on `cve_id` (weakness_types joins on `cwe_ids`).

| File | Rows | Use |
|---|---|---|
| vulnerabilities.csv | 401,082 | One row per CVE since 1988: description, severity (CVSS 2/3/4), attack fields, cwe_ids, n_references, n_affected_cpes, nvd_status, assigner |
| affected_products.csv | 3,155,934 | Vendor/product/version ranges per CVE. Read version columns as text |
| references.csv | 1,360,487 | Links per CVE with NIST tags (Patch, Exploit, Vendor Advisory, ...). KEV links removed |
| known_exploited.csv | 1,484 | CISA KEV through 2025-12-31: date_added, vendor, product, known_ransomware_use |
| exploit_signals_2024.csv / _2025.csv | 6,463,734 total | Per month: epss, in_kev, exploitdb, metasploit, nuclei, poc_github at about month end. Rows with no EPSS and no flags are omitted |
| weakness_types.csv | 1,374 | CWE names |
| scoreboard_2026.csv | 72,670 | Benchmark rows: cve_id, published, snapshot_month, epss, 4 exploit flags at snapshot. June 2026 signals are missing, so June CVEs use snapshot July |

## Time rules
- Use `published` (not the year inside the CVE id) for dates. `last_modified` is mid-2026 or later for every row: NIST files are TODAY's versions.
- Only EPSS, exploit flags and `in_kev` from the signals files are true as-of-month values.

## Fields that leak for 2026 (do NOT use as model features; list in the write-up)
`nvd_status`, `n_affected_cpes`, `n_references`, blank severity-score patterns, links to news/threat reports in references.csv. NIST reviews attacked CVEs first and fills details in afterwards. 37,853 references link to IBM X-Force Exchange: treat as leak-prone too. Whether `cvss3_score`, `cwe_ids`, `attack_*` and other NVD-analysis fields are safe is a judgement call: our first-pass preferred model avoids them (see 02, 04).

## Quirks [SOURCE]
- NVD statuses `Received`, `Awaiting Analysis`, `Undergoing Analysis` = not analysed yet (scores, weaknesses, products may be blank); `Deferred` = will not be analysed.
- EPSS changed model in March 2025; scores before and after are not directly comparable.
- Feb 2025 in exploit_signals_2025.csv is missing about 14,500 CVEs. About 11,800 ids in the signals files are rejected IDs absent from vulnerabilities.csv.
- KEV `date_added` is before `published` for 62 CVEs.
- NIST has not reviewed 51,046 of the 92,205 CVEs published in 2026, so most lack product lists; every CVE has a description.
