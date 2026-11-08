# pancakess dashboard

The upload-first dashboard for **Before the Breach**. It turns a CVE dataset into a ranked review queue, with an optional API path through the FastAPI backend.

## Run

```bash
cd dashboard
npm install
printf 'VITE_API_URL=http://localhost:8000/api\n' > .env.local
npm run dev -- --host 0.0.0.0 --port 5173
```

Open <http://localhost:5173/>.

No backend? Run `VITE_API_URL=demo npm run dev -- --host 0.0.0.0 --port 5173`; uploads are scored in the browser and nothing leaves the machine.

## Upload behavior

- Accepts **CSV or JSON** (array, or `{ "rows": [...] }`), up to **50 MB / 50,000 rows**.
- Requires `cve_id`; optional fields: `published`, `assigner`, `epss`, `exploitdb`, `metasploit`, `nuclei`, `poc_github`, `score`, `rank`, `priority`, `reasons`.
- **Model API** sends rows to `POST /api/predict`:
  - known scoreboard CVEs reuse the audited G2 score/reasons;
  - unknown CVEs use a transparent API fallback labelled `api-heuristic-v1`.
- **Local demo** uses the in-browser logistic stand-in; pre-scored files keep their scores unless you tick *Re-score*.
- The built-in **Try a sample batch** uses `public/sample_judge_input.csv`.
- Results include search/filter, priority bands, public-exploit filter, expandable signal reasons, CSV export, and a clickable **Signal rationale** panel.

## API contract

`VITE_API_URL` includes `/api`; the client appends `/health`, `/stats/summary`, `/explanations/...`, `/predict`. See [`server/README.md`](../server/README.md).

## Build and test

```bash
npm run build   # tsc -b + vite build
npm test        # vitest
npm run lint
```

`npm run build` writes `dist/`. Deploy `dist/` with the host rewriting all routes to `index.html` (see `vercel.json` / `public/_redirects`).

## Environment

| Variable | Use |
|---|---|
| `VITE_API_URL` | API origin including `/api`, or `demo` |
| `VITE_API_URL=demo` | pure browser demo, no backend |

No API keys are needed by this frontend. IBM Granite/Gemini keys are only for regenerating backend artifacts; see [`docs/IBM_USAGE.md`](../docs/IBM_USAGE.md).
