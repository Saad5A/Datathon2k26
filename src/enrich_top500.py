"""Join ML ranking scores with display metadata for triage UI / Gemini agent.

Per docs/INTERFACES.md: ranking scores stay free of descriptions/references;
this module produces results/top500_enriched.csv for grounded playbooks.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import (
    DATA_DIR,
    PROJECT_ROOT,
    REFERENCES_CSV,
    VULNERABILITIES_CSV,
    WEAKNESS_TYPES_CSV,
)

RESULTS_DIR = PROJECT_ROOT / "results"
DOCS_DIR = PROJECT_ROOT / "docs"
DATA_CACHE_DIR = PROJECT_ROOT / "data_cache"

SCORES_PRIMARY = RESULTS_DIR / "scores_2026.csv"
SCORES_FALLBACK = DOCS_DIR / "sample_scores_2026.csv"
DISPLAY_CACHE = DATA_CACHE_DIR / "cve_display.parquet"
DISPLAY_FALLBACK = DOCS_DIR / "sample_cve_display.csv"
AFFECTED_PRODUCTS_CSV = DATA_DIR / "affected_products.csv"
ENRICHED_OUT = RESULTS_DIR / "top500_enriched.csv"

PATCH_ADVISORY_EXPLOIT = re.compile(
    r"(patch|advisory|exploit|mitigation)",
    re.IGNORECASE,
)


def load_scores() -> pd.DataFrame:
    if SCORES_PRIMARY.exists():
        path = SCORES_PRIMARY
        print(f"Loading scores from {path}")
    elif SCORES_FALLBACK.exists():
        path = SCORES_FALLBACK
        print(f"scores_2026.csv not found; falling back to {path}")
    else:
        raise FileNotFoundError(
            f"No scores file found at {SCORES_PRIMARY} or {SCORES_FALLBACK}"
        )

    df = pd.read_csv(path)
    required = {"cve_id", "rank"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Scores file missing columns: {sorted(missing)}")

    if "in_top500" in df.columns:
        mask = df["in_top500"].astype(str).str.lower().isin({"true", "1", "yes"})
        top = df.loc[mask].copy()
        if top.empty:
            top = df.nsmallest(500, "rank").copy()
    else:
        top = df.nsmallest(500, "rank").copy()

    return top.sort_values("rank").reset_index(drop=True)


def _cvss_display(row: pd.Series) -> str:
    for col in ("cvss_score", "cvss3_score", "cvss4_score", "cvss2_score"):
        if col in row.index and pd.notna(row[col]) and str(row[col]).strip() != "":
            return str(row[col])
    return "Pending Review"


def _weakness_display(row: pd.Series) -> str:
    for col in ("weakness", "cwe_name", "cwe_names"):
        if col in row.index and pd.notna(row[col]) and str(row[col]).strip() != "":
            return str(row[col])
    return "Unassigned"


def _vendor_products(row: pd.Series) -> tuple[str, str]:
    vendor = ""
    products = ""
    if "vendor" in row.index and pd.notna(row["vendor"]) and str(row["vendor"]).strip():
        vendor = str(row["vendor"]).strip()
    if "affected_products" in row.index and pd.notna(row["affected_products"]):
        products = str(row["affected_products"]).strip()

    assigner = ""
    if "assigner" in row.index and pd.notna(row["assigner"]):
        assigner = str(row["assigner"]).strip()

    # Team agreement: fall back to assigner when vendor/products missing.
    if not vendor:
        vendor = assigner or "Unknown"
    if not products:
        products = vendor if vendor != "Unknown" else (assigner or "Unknown")

    return vendor, products


def _normalize_reference_urls(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "[]"
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none"}:
        return "[]"
    if text.startswith("["):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return json.dumps(parsed, ensure_ascii=False)
        except json.JSONDecodeError:
            pass
    # semicolon / pipe separated
    parts = [p.strip() for p in re.split(r"[;|]", text) if p.strip()]
    return json.dumps(parts, ensure_ascii=False)


def load_display_from_sample() -> pd.DataFrame:
    print(f"Loading display metadata from {DISPLAY_FALLBACK}")
    df = pd.read_csv(DISPLAY_FALLBACK)
    df["cvss_score"] = df.apply(_cvss_display, axis=1)
    df["weakness"] = df.apply(_weakness_display, axis=1)
    df["cwe_name"] = df["weakness"]
    vendors, products = zip(*[_vendor_products(row) for _, row in df.iterrows()])
    df["vendor"] = list(vendors)
    df["affected_products"] = list(products)
    df["reference_urls"] = df.get("reference_urls", "[]").map(_normalize_reference_urls)
    keep = [
        "cve_id",
        "description",
        "cvss_score",
        "cwe_name",
        "weakness",
        "vendor",
        "affected_products",
        "reference_urls",
    ]
    return df[keep]


def load_display_from_cache() -> pd.DataFrame:
    print(f"Loading display metadata from {DISPLAY_CACHE}")
    df = pd.read_parquet(DISPLAY_CACHE)
    if "cvss_score" not in df.columns:
        df["cvss_score"] = df.apply(_cvss_display, axis=1)
    else:
        df["cvss_score"] = df.apply(
            lambda r: r["cvss_score"] if pd.notna(r["cvss_score"]) and str(r["cvss_score"]).strip() else "Pending Review",
            axis=1,
        )
    df["weakness"] = df.apply(_weakness_display, axis=1)
    df["cwe_name"] = df.get("cwe_name", df["weakness"])
    df["cwe_name"] = df["cwe_name"].fillna("Unassigned").replace("", "Unassigned")
    vendors, products = zip(*[_vendor_products(row) for _, row in df.iterrows()])
    df["vendor"] = list(vendors)
    df["affected_products"] = list(products)
    if "reference_urls" in df.columns:
        df["reference_urls"] = df["reference_urls"].map(_normalize_reference_urls)
    else:
        df["reference_urls"] = "[]"
    if "description" not in df.columns:
        df["description"] = ""
    keep = [
        "cve_id",
        "description",
        "cvss_score",
        "cwe_name",
        "weakness",
        "vendor",
        "affected_products",
        "reference_urls",
    ]
    return df[keep]


def _aggregate_reference_urls(cve_ids: set[str]) -> pd.DataFrame:
    if not REFERENCES_CSV.exists():
        return pd.DataFrame({"cve_id": [], "reference_urls": []})

    urls_by_cve: dict[str, list[str]] = {c: [] for c in cve_ids}
    usecols = ["cve_id", "url", "tags"]
    for chunk in pd.read_csv(
        REFERENCES_CSV,
        usecols=usecols,
        quotechar='"',
        escapechar='"',
        low_memory=False,
        chunksize=400_000,
    ):
        chunk = chunk[chunk["cve_id"].isin(cve_ids)]
        if chunk.empty:
            continue
        tags = chunk["tags"].fillna("")
        keep = chunk[tags.str.contains(PATCH_ADVISORY_EXPLOIT, regex=True)].copy()
        for cve_id, url in zip(keep["cve_id"], keep["url"].fillna("")):
            url = str(url).strip()
            if url and url not in urls_by_cve[cve_id]:
                urls_by_cve[cve_id].append(url)

    rows = [
        {"cve_id": cve, "reference_urls": json.dumps(urls, ensure_ascii=False)}
        for cve, urls in urls_by_cve.items()
    ]
    return pd.DataFrame(rows)


def _product_vendor_agg(cve_ids: set[str]) -> pd.DataFrame:
    if not AFFECTED_PRODUCTS_CSV.exists():
        return pd.DataFrame({"cve_id": [], "vendor": [], "affected_products": []})

    parts = []
    usecols = ["cve_id", "vendor", "product", "vulnerable"]
    for chunk in pd.read_csv(
        AFFECTED_PRODUCTS_CSV,
        usecols=usecols,
        quotechar='"',
        escapechar='"',
        low_memory=False,
        chunksize=400_000,
    ):
        chunk = chunk[chunk["cve_id"].isin(cve_ids)]
        if "vulnerable" in chunk.columns:
            chunk = chunk[chunk["vulnerable"] == "Y"]
        if chunk.empty:
            continue
        parts.append(chunk)

    if not parts:
        return pd.DataFrame({"cve_id": [], "vendor": [], "affected_products": []})

    prod = pd.concat(parts, ignore_index=True)
    grouped = (
        prod.groupby("cve_id")
        .agg(
            vendor=("vendor", lambda s: ";".join(sorted({str(x) for x in s.dropna() if str(x).strip()}))),
            affected_products=(
                "product",
                lambda s: ";".join(sorted({str(x) for x in s.dropna() if str(x).strip()})),
            ),
        )
        .reset_index()
    )
    return grouped


def load_display_from_nvd(cve_ids: set[str]) -> pd.DataFrame:
    print(f"Loading display metadata from {VULNERABILITIES_CSV}")
    usecols = [
        "cve_id",
        "description",
        "cvss3_score",
        "cvss4_score",
        "cvss2_score",
        "cwe_ids",
        "assigner",
    ]
    vulns = pd.read_csv(
        VULNERABILITIES_CSV,
        usecols=lambda c: c in usecols,
        quotechar='"',
        escapechar='"',
        low_memory=False,
    )
    vulns = vulns[vulns["cve_id"].isin(cve_ids)].copy()

    cwe_map = {}
    if WEAKNESS_TYPES_CSV.exists():
        weaknesses = pd.read_csv(WEAKNESS_TYPES_CSV, quotechar='"', escapechar='"')
        if {"cwe_id", "name"}.issubset(weaknesses.columns):
            cwe_map = dict(zip(weaknesses["cwe_id"], weaknesses["name"]))

    def map_cwe(value) -> str:
        if pd.isna(value) or not str(value).strip():
            return "Unassigned"
        names = []
        for token in str(value).split(";"):
            token = token.strip()
            if not token:
                continue
            names.append(cwe_map.get(token, token))
        return "; ".join(names) if names else "Unassigned"

    vulns["weakness"] = vulns.get("cwe_ids", pd.Series(dtype=str)).map(map_cwe)
    vulns["cwe_name"] = vulns["weakness"]
    vulns["cvss_score"] = vulns.apply(_cvss_display, axis=1)

    products = _product_vendor_agg(cve_ids)
    refs = _aggregate_reference_urls(cve_ids)
    out = vulns.merge(products, on="cve_id", how="left").merge(refs, on="cve_id", how="left")

    vendors, product_vals = zip(*[_vendor_products(row) for _, row in out.iterrows()])
    out["vendor"] = list(vendors)
    out["affected_products"] = list(product_vals)
    out["reference_urls"] = out.get("reference_urls", pd.Series(["[]"] * len(out))).fillna("[]")
    out["reference_urls"] = out["reference_urls"].map(_normalize_reference_urls)
    out["description"] = out.get("description", "").fillna("")

    keep = [
        "cve_id",
        "description",
        "cvss_score",
        "cwe_name",
        "weakness",
        "vendor",
        "affected_products",
        "reference_urls",
    ]
    return out[keep]


def load_display_metadata(cve_ids: set[str]) -> pd.DataFrame:
    if DISPLAY_CACHE.exists():
        return load_display_from_cache()
    if VULNERABILITIES_CSV.exists():
        return load_display_from_nvd(cve_ids)
    if DISPLAY_FALLBACK.exists():
        return load_display_from_sample()
    raise FileNotFoundError(
        "No display metadata found. Expected one of: "
        f"{DISPLAY_CACHE}, {VULNERABILITIES_CSV}, {DISPLAY_FALLBACK}"
    )


def enrich_top500(scores: pd.DataFrame | None = None) -> pd.DataFrame:
    scores = load_scores() if scores is None else scores.copy()
    cve_ids = set(scores["cve_id"].astype(str))
    display = load_display_metadata(cve_ids)

    merged = scores.merge(display, on="cve_id", how="left")
    merged["description"] = merged.get("description", "").fillna("")
    merged["cvss_score"] = merged.get("cvss_score", "Pending Review").fillna("Pending Review")
    merged["cvss_score"] = merged["cvss_score"].replace("", "Pending Review")
    merged["weakness"] = merged.get("weakness", "Unassigned").fillna("Unassigned").replace("", "Unassigned")
    merged["cwe_name"] = merged.get("cwe_name", merged["weakness"]).fillna("Unassigned").replace("", "Unassigned")
    merged["vendor"] = merged.get("vendor", "Unknown").fillna("Unknown").replace("", "Unknown")
    merged["affected_products"] = (
        merged.get("affected_products", "Unknown").fillna("Unknown").replace("", "Unknown")
    )
    merged["reference_urls"] = merged.get("reference_urls", "[]").fillna("[]").map(_normalize_reference_urls)

    score_cols = [c for c in ("cve_id", "rank", "priority_score", "priority", "reasons", "in_top500") if c in merged.columns]
    display_cols = [
        "description",
        "cvss_score",
        "cwe_name",
        "weakness",
        "vendor",
        "affected_products",
        "reference_urls",
    ]
    return merged[score_cols + display_cols].sort_values("rank").reset_index(drop=True)


def save_enriched(df: pd.DataFrame, path: Path = ENRICHED_OUT) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    print(f"Wrote {path} ({len(df)} rows)")
    return path


def main() -> None:
    enriched = enrich_top500()
    save_enriched(enriched)
    print(enriched.head().to_string(index=False))


if __name__ == "__main__":
    main()
