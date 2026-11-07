"""Feature extraction helpers for CVE exploitability ranking."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import (
    AFFECTED_PRODUCTS_CSV,
    EXPLOIT_SIGNALS_2024_CSV,
    EXPLOIT_SIGNALS_2025_CSV,
    KNOWN_EXPLOITED_CSV,
    REFERENCES_CSV,
    SCOREBOARD_2026_CSV,
    VULNERABILITIES_CSV,
    WEAKNESS_TYPES_CSV,
)


def _read_csv(path, **kwargs) -> pd.DataFrame:
    return pd.read_csv(path, quotechar='"', escapechar='"', low_memory=False, **kwargs)


def load_vulnerabilities() -> pd.DataFrame:
    cols = [
        "cve_id",
        "published",
        "assigner",
        "description",
        "cvss3_score",
        "cvss3_severity",
        "cvss3_exploitability_score",
        "cvss3_impact_score",
        "attack_vector",
        "attack_complexity",
        "privileges_required",
        "user_interaction",
        "scope",
        "confidentiality_impact",
        "integrity_impact",
        "availability_impact",
        "cvss4_score",
        "cvss2_score",
        "cwe_ids",
    ]
    df = _read_csv(VULNERABILITIES_CSV, usecols=lambda c: c in cols)
    df["published"] = pd.to_datetime(df["published"], errors="coerce")
    return df


def load_scoreboard() -> pd.DataFrame:
    df = _read_csv(SCOREBOARD_2026_CSV)
    df["published"] = pd.to_datetime(df["published"], errors="coerce")
    return df


def load_known_exploited() -> pd.DataFrame:
    df = _read_csv(KNOWN_EXPLOITED_CSV, usecols=["cve_id", "date_added", "known_ransomware_use"])
    df["date_added"] = pd.to_datetime(df["date_added"], errors="coerce")
    df["known_ransomware_use"] = (df["known_ransomware_use"] == "Known").astype(int)
    return df.rename(
        columns={
            "date_added": "kev_date_added",
            "known_ransomware_use": "kev_ransomware",
        }
    )


def reference_tag_features(chunksize: int = 500_000) -> pd.DataFrame:
    """Aggregate reference tags that are relatively safe (vendor/patch-oriented)."""
    tag_flags = {
        "ref_has_patch": "patch",
        "ref_has_vendor_advisory": "vendor advisory",
        "ref_has_third_party_advisory": "third party advisory",
        "ref_has_mitigation": "mitigation",
        "ref_has_exploit_tag": "exploit",
    }
    parts = []
    usecols = ["cve_id", "tags", "domain"]
    for chunk in pd.read_csv(
        REFERENCES_CSV,
        usecols=usecols,
        quotechar='"',
        escapechar='"',
        low_memory=False,
        chunksize=chunksize,
    ):
        tags = chunk["tags"].fillna("").str.lower()
        out = pd.DataFrame({"cve_id": chunk["cve_id"]})
        for col, needle in tag_flags.items():
            out[col] = tags.str.contains(needle, regex=False).astype(int)
        out["ref_count_safe"] = 1
        out["ref_ibm_xforce"] = chunk["domain"].fillna("").str.contains("exchange.xforce", regex=False).astype(int)
        parts.append(out.groupby("cve_id", as_index=False).sum())

    if not parts:
        return pd.DataFrame(columns=["cve_id", *tag_flags, "ref_count_safe", "ref_ibm_xforce"])

    agg = pd.concat(parts, ignore_index=True)
    return agg.groupby("cve_id", as_index=False).sum()


def product_breadth_features(chunksize: int = 500_000) -> pd.DataFrame:
    parts = []
    usecols = ["cve_id", "type", "vendor", "vulnerable"]
    for chunk in pd.read_csv(
        AFFECTED_PRODUCTS_CSV,
        usecols=usecols,
        quotechar='"',
        escapechar='"',
        low_memory=False,
        chunksize=chunksize,
    ):
        vuln = chunk[chunk["vulnerable"] == "Y"].copy()
        if vuln.empty:
            continue
        g = vuln.groupby("cve_id").agg(
            n_vendors=("vendor", "nunique"),
            n_products=("cve_id", "size"),
            n_os=("type", lambda s: int((s == "operating_system").sum())),
            n_app=("type", lambda s: int((s == "application").sum())),
        )
        parts.append(g.reset_index())

    if not parts:
        return pd.DataFrame(columns=["cve_id", "n_vendors", "n_products", "n_os", "n_app"])

    agg = pd.concat(parts, ignore_index=True)
    return agg.groupby("cve_id", as_index=False).sum()


def latest_exploit_signals() -> pd.DataFrame:
    """Latest monthly exploit signals per CVE from 2024–2025 history."""
    frames = []
    for path in (EXPLOIT_SIGNALS_2024_CSV, EXPLOIT_SIGNALS_2025_CSV):
        if path.exists():
            frames.append(_read_csv(path))
    if not frames:
        return pd.DataFrame(
            columns=["cve_id", "epss_hist", "exploitdb", "metasploit", "nuclei", "poc_github"]
        )

    sig = pd.concat(frames, ignore_index=True)
    sig = sig.sort_values(["cve_id", "month"])
    latest = sig.groupby("cve_id", as_index=False).tail(1)
    return latest.rename(columns={"epss": "epss_hist"})[
        ["cve_id", "epss_hist", "exploitdb", "metasploit", "nuclei", "poc_github"]
    ]


def encode_categoricals(df: pd.DataFrame) -> pd.DataFrame:
    cat_cols = [
        "attack_vector",
        "attack_complexity",
        "privileges_required",
        "user_interaction",
        "scope",
        "confidentiality_impact",
        "integrity_impact",
        "availability_impact",
        "cvss3_severity",
    ]
    out = df.copy()
    for col in cat_cols:
        if col in out.columns:
            out[col] = out[col].astype("category").cat.codes.replace(-1, np.nan)
    return out


def description_features(df: pd.DataFrame) -> pd.DataFrame:
    desc = df["description"].fillna("")
    out = df.drop(columns=["description"], errors="ignore").copy()
    out["desc_len"] = desc.str.len()
    out["desc_has_rce"] = desc.str.contains(
        r"remote code execution|arbitrary code", case=False, regex=True
    ).astype(int)
    out["desc_has_auth_bypass"] = desc.str.contains(
        r"authentication bypass|auth bypass", case=False, regex=True
    ).astype(int)
    out["desc_has_sqli"] = desc.str.contains("sql injection", case=False, regex=False).astype(int)
    out["desc_has_xss"] = desc.str.contains("cross-site scripting|xss", case=False, regex=True).astype(int)
    return out


def cwe_count_feature(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    cwe = out.get("cwe_ids", pd.Series("", index=out.index)).fillna("")
    out["n_cwe"] = np.where(cwe.eq(""), 0, cwe.str.count(";") + 1)
    return out.drop(columns=["cwe_ids"], errors="ignore")


def build_feature_matrix() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build training-style and scoreboard feature tables.

    Avoids leaky NIST update columns for 2026 scoring fairness.
    """
    vulns = load_vulnerabilities()
    scoreboard = load_scoreboard()
    kev = load_known_exploited()
    refs = reference_tag_features()
    products = product_breadth_features()
    signals = latest_exploit_signals()

    base = vulns.merge(kev, on="cve_id", how="left")
    base = base.merge(refs, on="cve_id", how="left")
    base = base.merge(products, on="cve_id", how="left")
    base = base.merge(signals, on="cve_id", how="left")

    base["in_kev_hist"] = base["kev_date_added"].notna().astype(int)
    base["kev_ransomware"] = base["kev_ransomware"].fillna(0).astype(int)
    base = base.drop(columns=["kev_date_added", "assigner"], errors="ignore")

    base = description_features(base)
    base = cwe_count_feature(base)
    base = encode_categoricals(base)

    fill_zero = [
        "ref_has_patch",
        "ref_has_vendor_advisory",
        "ref_has_third_party_advisory",
        "ref_has_mitigation",
        "ref_has_exploit_tag",
        "ref_count_safe",
        "ref_ibm_xforce",
        "n_vendors",
        "n_products",
        "n_os",
        "n_app",
        "exploitdb",
        "metasploit",
        "nuclei",
        "poc_github",
    ]
    for col in fill_zero:
        if col in base.columns:
            base[col] = base[col].fillna(0)

    # Scoreboard rows: use snapshot EPSS / exploit flags from the benchmark file.
    sb = scoreboard.merge(base.drop(columns=["published"], errors="ignore"), on="cve_id", how="left")
    for col in ("epss", "exploitdb", "metasploit", "nuclei", "poc_github"):
        if col in sb.columns:
            sb[col] = sb[col].fillna(0)

    return base, sb


def ensure_weakness_types_available() -> bool:
    return WEAKNESS_TYPES_CSV.exists()
