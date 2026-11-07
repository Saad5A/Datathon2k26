# Before the Breach — triage dashboard

React + TypeScript + Tailwind dashboard for the 2026 CVE ranking. Data contract: [`../docs/INTERFACES.md`](../docs/INTERFACES.md).

```bash
cd dashboard
npm install
npm run dev        # http://localhost:5173
npm run build      # type-check + production bundle in dist/
```

## Judge flow

**Evaluate dataset** (top right) opens a drag-and-drop modal for CSV/JSON uploads.

- **In-browser**: a transparent logistic stand-in (`src/lib/scoring.ts › dummyScore`) scores rows in chunks, and the leaderboard updates live while it runs.
- **Model API**: rows are POSTed to `/predict` (see INTERFACES §4). In dev, Vite proxies `/predict` to `http://127.0.0.1:8000`, or to whatever `PREDICT_PROXY_TARGET` is set to. In production, set `VITE_PREDICT_URL`.
- Pre-scored files (every row has `score`) are shown as-is. That includes `outputs/scores_2026.csv`, and its global ranks are preserved.
- **Try sample input** loads `public/sample_judge_input.csv` (400 unscored CVEs).

**Load into dashboard** replaces the active dataset across every widget. **Export CSV** writes it back out in INTERFACES format.

## Layout

| Path | Purpose |
|---|---|
| `src/theme/tokens.ts` | Severity colours, surfaces, 4px spacing, 12-col layout. Feeds `tailwind.config.ts` and charts. |
| `src/components/dashboard/` | `DashboardGrid`, `WidgetCard`, `KpiTile`, `DonutWidget`, `BarWidget`, `TrendWidget`, `RankedTable`, `JudgeUploadModal` |
| `src/components/ui/` | shadcn-style primitives on Radix (button, badge, dialog, tooltip, dropdown) |
| `src/lib/server.ts` | Server-style paged/sorted/filtered query. Swap for `fetch()` when a real API exists. |
| `src/lib/parse.ts` | CSV/JSON ingest, normalisation, streaming scoring, CSV export |
| `src/data/mock.ts` | Deterministic synthetic 72,670-row snapshot (seeded) |
