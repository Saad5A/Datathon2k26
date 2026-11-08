# The pancake lab — UI notes

The dashboard is an upload-first “kitchen” experience:

1. **Kitchen** — empty skillet, batter jug and plate. Drag to orbit; the jug opens the file picker; “Try a sample batch” loads `public/sample_judge_input.csv`.
2. **Cook** — parsing and scoring drive a short presentation sequence (pour, cook, flip, plate). Presentation is independent of processing time; fast uploads still show the sequence, slow requests wait at “cooking.”
3. **Served** — the review queue, source label, warnings, CSV export and, for the selected CVE, the supplied signal rationale plus an optional IBM Granite technical note when the backend has one.

## Upload engines

- **Model API** — default when `POST /api/predict` is available. Known scoreboard CVEs reuse the audited G2 score; unknown CVEs use the transparent `api-heuristic-v1` fallback. Files are sent to the configured API.
- **Local demo** — in-browser logistic stand-in; no file leaves the machine. Pre-scored files keep their scores unless *Re-score* is checked.
- Accepted input: CSV or JSON (array or `{ "rows": [...] }`), up to 50 MB / 50,000 rows, with `cve_id` required.

## Robustness

- A batch identity prevents stale uploads from overwriting newer results.
- Cancel/error keeps the previous dataset; API failures offer an explicit local fallback.
- Built-in sample provenance is explicit, never inferred from a filename.
- WebGL failure has a static fallback with upload/results access.
- Reduced-motion preferences skip decorative transitions.
- The results rail labels scores as ranking/review urgency, not exploit probability; IBM Granite notes are labelled with provider/model metadata.

## Verification

`npm run build`, `npm test` and the FastAPI `/api/predict` smoke path are the release checks. Upload/API/results were also exercised in a headless browser. `npm run build` warns about the lazy Three.js scene bundle size; it is non-blocking.
