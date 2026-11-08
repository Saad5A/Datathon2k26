# The pancake lab

A focused kitchen-to-results experience. Initial load shows an empty skillet, open batter jug and serving plate, with no synthetic metrics. The jug's projected HTML upload button follows its position as the camera moves; clicking the jug also opens the native file chooser. Keyboard users can use the same labelled button.

## Run and checks

Set `VITE_API_URL=demo` for local demo scoring. The read-only FastAPI backend can be started from the repository root with `pip install -r server/requirements.txt` and `uvicorn server.app:app --reload --port 8000`; configure the dashboard as `VITE_API_URL=http://localhost:8000/api` to load backend ranking summaries and provider-backed Gemini briefs. This backend does not score arbitrary uploaded files; the kitchen's default local processing remains available. The optional upload API engine stays disabled unless `/health` explicitly advertises `capabilities.upload_scoring: true` and the configured server provides `/predict`. In dashboard, run `npm install`, `npm run dev`, and `npm run build` as needed.

## The story

A new batch begins a continuous pour, cook, flip and plate presentation. The jug lifts and tips, its batter level lowers, and a curved stream joins the spout to the pan. Batter spreads monotonically, browns and bubbles; the spatula slides underneath before the flip and transfer. The jug remains part of the station throughout.

Presentation time is separate from processing time. Fast uploads still play the full short sequence; slow requests hold at cooking. Completed results are accessible immediately via View now. Plating automatically opens the results screen after successful processing. Pause only freezes decorative motion. Reduced motion makes state transitions immediate. Cooking is illustrative and implies neither model accuracy nor confirmed future exploitation.

Results are intentionally compact: source and dataset identity, backend-provided ranking/risk totals when connected, the searchable queue and a Gemini brief fetched for the selected CVE. No client-calculated chart wall is shown. Gemini text stays labelled AI-generated and is fetched from the backend artifact; a missing brief is shown as unavailable, never synthesized in the browser. CSV export remains available. Back to kitchen preserves the plated batch. Cook another batch resets presentation and cancels pending work without deleting previous results. File errors and cancellation retain the previous dataset. Retries, explicit API-to-local fallback and return-to-results are inline.

A batch identity protects the controller and presentation against stale work. Built-in sample provenance is explicit, never guessed from a filename. Failed WebGL displays a static alternative with upload and result access. Context loss cancels the render loop. Unmounting disposes geometry, materials, texture, controls, shadow resources and renderer.

## Verification

Automated tests cover controller cancellation, stale results, sample provenance, API states, presentation timing and results navigation. Production build passes with a nonblocking scene bundle size warning. Independent source review covers callback guards, source labels, focus transfer and resource cleanup. Browser appearance, mobile framing, WebGL fallback interaction, live API behavior and motion continuity remain unchecked here; validate with screenshots and a recording before considering the visual finish complete.

No audited result artifacts were edited. The separate evolution research directory is preserved. Shared KB publication is blocked by pre-existing changes in the model-ranking team file.
