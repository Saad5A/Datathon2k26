"""Paths and constants for the IBM vulnerability ranking baseline."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DATA_CACHE_DIR = PROJECT_ROOT / "data_cache"
DOCS_DIR = PROJECT_ROOT / "docs"
RESULTS_DIR = PROJECT_ROOT / "results"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

VULNERABILITIES_CSV = DATA_DIR / "vulnerabilities.csv"
AFFECTED_PRODUCTS_CSV = DATA_DIR / "affected_products.csv"
REFERENCES_CSV = DATA_DIR / "references.csv"
KNOWN_EXPLOITED_CSV = DATA_DIR / "known_exploited.csv"
WEAKNESS_TYPES_CSV = DATA_DIR / "weakness_types.csv"
SCOREBOARD_2026_CSV = DATA_DIR / "scoreboard_2026.csv"
EXPLOIT_SIGNALS_2024_CSV = DATA_DIR / "exploit_signals_2024.csv"
EXPLOIT_SIGNALS_2025_CSV = DATA_DIR / "exploit_signals_2025.csv"

FEATURES_PARQUET = OUTPUT_DIR / "features.parquet"
SCOREBOARD_FEATURES_PARQUET = OUTPUT_DIR / "scoreboard_features.parquet"

# Columns that can leak post-exploit NIST updates for 2026 CVEs.
LEAKY_COLUMNS = (
    "nvd_status",
    "n_affected_cpes",
    "n_references",
    "last_modified",
)
