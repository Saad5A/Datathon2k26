"""Build baseline feature tables for IBM CVE exploitability ranking.

Reads CSVs from ./data (gitignored) and writes parquet outputs to ./outputs.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import DATA_DIR, FEATURES_PARQUET, OUTPUT_DIR, SCOREBOARD_FEATURES_PARQUET
from src.features import build_feature_matrix


def main() -> None:
    if not DATA_DIR.exists():
        raise SystemExit(
            f"Missing data directory: {DATA_DIR}\n"
            "Unzip IBM data.zip into ./data before running feature extraction."
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Building feature matrix...")
    features, scoreboard_features = build_feature_matrix()

    features.to_parquet(FEATURES_PARQUET, index=False)
    scoreboard_features.to_parquet(SCOREBOARD_FEATURES_PARQUET, index=False)

    print(f"Wrote {FEATURES_PARQUET} ({len(features):,} rows, {features.shape[1]} cols)")
    print(
        f"Wrote {SCOREBOARD_FEATURES_PARQUET} "
        f"({len(scoreboard_features):,} rows, {scoreboard_features.shape[1]} cols)"
    )


if __name__ == "__main__":
    main()
