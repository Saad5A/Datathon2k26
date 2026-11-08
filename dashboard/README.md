# Before the Breach · CVE triage dashboard

**Live:** https://pancakess.work

Sheridan Datathon 2026. The model ranks 72,670 CVEs by how likely they are to be exploited in the wild. This dashboard shows that ranking so a security team can see what to patch first:

- KPI tiles, a monthly trend chart, priority mix and breakdown bars (assigners, driving signals, exploit evidence).
- A sortable, searchable, paged table of every CVE. Expand a row to see why it ranks where it does (`reasons`).
- **Evaluate dataset**: judges drop in their own CSV/JSON of CVEs and see it scored and ranked live, either in the browser or by the model API.

Scores are **uncalibrated ranking scores**, not probabilities. Compare them by rank.

## Tech stack

React 19 · TypeScript · Vite 6 · Tailwind CSS 3 · Radix UI primitives (shadcn-style) · Recharts · TanStack Table · PapaParse. Node ≥ 20.

## Local setup

```bash
cd dashboard
npm ci
cp .env.example .env.local     # then set VITE_API_URL (see below)
npm run dev                    # http://localhost:5173
```

| Script | What it does |
|---|---|
| `npm run dev` | Dev server with HMR |
| `npm run build` | Type-check (`tsc -b`) + production bundle in `dist/` |
| `npm run preview` | Serve `dist/` at http://localhost:4173. Use this to test the production build. |
| `npm run lint` | ESLint |

Dev and preview call the backend **directly** (there is no dev proxy), so CORS is exercised exactly as in production.

## Environment variables

| Variable | Required | Meaning |
|---|---|---|
| `VITE_API_URL` | **yes** | Backend origin, no trailing slash, e.g. `https://api.example.com` or `http://localhost:8000`. Set to `demo` to run with sample data and no backend. |

- If it is missing or malformed, the app shows a **configuration error screen** instead of a blank page.
- Vite inlines it **at build time**. Changing it on the host requires a **redeploy**.
- All `VITE_*` values are public in the shipped JS. Never put secrets in them.

## Build and deploy

The repo root is not the app: set the host's **root directory to `dashboard`**.

**Vercel (primary):**

1. Import the repo → Root Directory `dashboard` → framework Vite (auto-detected).
2. Add `VITE_API_URL` for **Production and Preview**. Until the backend is hosted, use `demo`; afterwards use its origin (`https://<api-origin>`). Redeploy after any change.
3. Add the domain `pancakess.work` under Project → Settings → Domains and follow Vercel's DNS instructions.

[`vercel.json`](vercel.json) provides the SPA rewrite, immutable asset caching and basic security headers.

Netlify also works: base directory `dashboard`, publish directory `dashboard/dist`, and [`public/_redirects`](public/_redirects) provides the SPA fallback.

Deep links and refreshes work on both hosts. Paths other than `/` render the in-app 404 page.

## Backend contract

Full schema in [`../docs/INTERFACES.md`](../docs/INTERFACES.md). The dashboard calls two endpoints on `VITE_API_URL`:

| Endpoint | Used for | Timeout | Notes |
|---|---|---|---|
| `GET /health` | Footer "API status" dot (on load, every 60 s, on click) | 5 s | Any `2xx` = online; body ignored |
| `POST /predict` | "Model API" scoring in the upload modal | 60 s | JSON `{ "rows": [...] }` in, array or `{ "rows": [...] }` out; each row needs `score` |

If the backend is unreachable the dashboard keeps working: the headline data is the built-in **demo data** (labelled `demo data` in the header), the footer shows **API unreachable**, and a failed upload offers **Retry** and **Score in browser instead**.

### CORS: origins the backend must allow

The browser sends `Content-Type: application/json`, so `POST /predict` triggers a preflight. The backend must answer `OPTIONS` and send, for each allowed origin:

```
Access-Control-Allow-Origin: <the requesting origin, if allow-listed>
Access-Control-Allow-Methods: GET, POST, OPTIONS
Access-Control-Allow-Headers: Content-Type, Accept
Vary: Origin
```

Origins to allow:

| Origin | Why |
|---|---|
| `https://pancakess.work` | Production |
| `https://www.pancakess.work` | Only if you also serve the `www` host |
| `https://<project>-<hash>-<team>.vercel.app` (or Netlify deploy-preview URLs) | Preview deploys. Match by pattern server-side. |
| `http://localhost:5173` | `npm run dev` |
| `http://localhost:4173` | `npm run preview` |

No cookies or credentials are sent, so `Access-Control-Allow-Credentials` is not needed. Do not use `*` together with credentials.

## Data and columns used

The table, charts and CSV export use exactly the 17 columns of the scores file:

`cve_id, published, snapshot_month, assigner, score, rank, percentile, in_top500, priority, epss, exploitdb, metasploit, nuclei, poc_github, any_public_exploit, reasons, model_version`

Types, priority bands (P0/P1/P2) and the `reasons` format are defined in [`../docs/INTERFACES.md`](../docs/INTERFACES.md). Uploads need only `cve_id`; optional columns feed the in-browser scorer.

> The dashboard does not yet have an `/audit` page, so this section and `INTERFACES.md` are the reference for now. Link it here once it exists.

## Project layout

| Path | Purpose |
|---|---|
| `src/lib/apiClient.ts` | The only place that reads `VITE_API_URL` or calls `fetch` (timeouts, typed errors) |
| `src/theme/tokens.ts` | Severity colours, surfaces, spacing, layout; feeds Tailwind and the charts |
| `src/components/dashboard/` | Grid, widget card, KPI tile, donut/bar/trend widgets, ranked table, upload modal |
| `src/lib/server.ts` | Server-style page/sort/filter query layer (swap for `fetch` when a scores API exists) |
| `src/data/mock.ts` | Deterministic synthetic 72,670-row demo data |
| `public/sample_judge_input.csv` | 400 unscored CVEs for the modal's "Try sample input" |
