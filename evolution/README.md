# pancakess — Evolution Braid

A standalone evolution diagram for the pancakess search. The light, high-contrast field makes the gold champion lineage, alternatives, and C1 baseline easy to follow.

## Open it

The dashboard is already being served locally at:

```text
http://localhost:5174/evolve
```

The default is **focus mode**: the diagram alone, with no surrounding UI or text. Add `?ui=1` for the full dashboard (rail, dossier, timeline, controls).

```text
http://localhost:5174/evolve?ui=1
```

Restart it with:

```bash
bash evolution/serve.sh
```

Deep links:

- `?view=blind` (default), `?view=c1opt`, `?view=arena`
- `?mode=curated` (default) or `?mode=full`
- `?ui=1` for the full dashboard chrome

## What you are looking at

- **Gold trunk** — the champion lineage: CatBoost seed → first GAM → top-243 record → champion.
- **Rings / side branches** — real alternative branches (top siblings at each step).
- **Gold crown** — the champion's actual descendants, curated to the strongest branches.
- **Dust** — the full population of genomes, position by generation and ancestry order.
- **C1 baseline** — the audited baseline, shown at the end as a dashed comparison branch.

## Interactions

- Drag to pan, scroll/pinch to zoom.
- In `?ui=1`, click a ring or the champion to open its dossier.
- Switch **Curated / Full** to move between the story and the entire field.
- **Isolate champion** dims the alternatives and keeps the lineage.
- **Run 80 generations** animates the reveal; drag the generation ruler to scrub.
- Tabs switch between the blind search, the C1-seeded search, and the arena.
- Search highlights matching genomes; family rows hide/show families.
- Dossier can be closed and reopened; `?mode=full` shows the complete population.
- Keyboard: `/` search, `0` reset, `Space` play/pause, `L` isolate, `Esc` clear.

## Data

Built from the archived search artifacts:

- `audit/evidence_2026-11-08-gate/archive_final/blind/evolution_tree.json`
- `audit/evidence_2026-11-08-gate/archive_final/c1opt/evolution_tree.json`
- `evolution/assets/arena_raw.json` (a dump of `results/autorank/arena.sqlite`)

Rebuild the JSON payloads with:

```bash
python evolution/build_data.py
```

## Honest framing

All metrics are 2025 backtest results under time-safe folds. There are **no 2026 labels**, so no 2026 accuracy is claimed.

- Champion: GAM, `assigner24 + signals + temporal`, cap 75.
- Backtest mean: **18.0 top-243 / 20.0 top-500 / 0.1323 AP**.
- C1 baseline: **13.5 / 16.0 / 0.0770**.
- Five-seed gains vs C1: **+7.5 top-243 / +4.0 top-500 / +0.0542 AP**.

After pulling `origin/feat/model-ranking` on 2026-11-08, the repo’s audited submission is **G2** (C1 + Granite text), adopted by the pre-registered IBM tie-break with no measurable gain. This dashboard is an explanatory artifact; it does not change `results/top500.csv`.
