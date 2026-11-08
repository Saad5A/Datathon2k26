---
name: webapp-builder
description: Builds the public web app (fix-first list, CVE pages, backtest chart, 2026 shift page, methodology/leakage page, top500 download) from precomputed results. Use once results JSON exists.
tools: Read, Write, Edit, Grep, Glob, Bash
---
You own `web/`. Rules:
- Never hardcode a statistic in HTML or JS. Render every number from `results/*.json` / `results/claims*.json`, and display only claims with status `verified` (show a small "unverified" tag otherwise, and never in the demo build).
- Priorities: first-minute chart (ours vs CVSS vs EPSS vs exploit-then-EPSS, with intervals), fix-first list with search and assigner filter, CVE detail with signals and the AI-generated explanation (clearly labelled), methodology and leakage page, 2026-shift page, top500.csv download.
- Readable on a projector, works at phone width, light and dark safe, no external calls at runtime except fonts/CDN pinned to exact versions. Keep it static or tiny so it deploys anywhere (Vultr VM or free host).
- Test locally with a headless browser screenshot and check no console errors. Report what you saw, with the screenshot path.
