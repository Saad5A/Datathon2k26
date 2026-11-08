"""Gemini-powered CVE triage / remediation playbook generator.

Uses google-genai with gemini-2.5-flash. Priority tiers come from ML only;
Gemini explains them and proposes grounded mitigations/patches.
"""

from __future__ import annotations

import json
import os
import re
import sys
import warnings
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load .env before any API-key reads (project root + cwd).
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
load_dotenv()

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.enrich_top500 import ENRICHED_OUT, enrich_top500, save_enriched

MODEL_ID = "gemini-2.5-flash"
CACHED_PLAYBOOKS_PATH = ROOT / "results" / "cached_playbooks.json"
NO_PATCH_MSG = (
    "No verified vendor patch URL identified in advisory references — "
    "rely on interim mitigations."
)
PLACEHOLDER_KEY_FRAGMENTS = (
    "your_google",
    "your_api",
    "changeme",
    "replace_me",
    "xxx",
    "todo",
    "placeholder",
    "example",
)

PLAYBOOK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "cve_id": {"type": "string"},
        "priority_tier": {"type": "string", "enum": ["P0", "P1", "P2"]},
        "executive_summary": {"type": "string"},
        "triage_explanation": {"type": "string"},
        "immediate_mitigation": {"type": "string"},
        "patch_guidance": {"type": "string"},
        "is_ai_generated": {"type": "boolean"},
    },
    "required": [
        "cve_id",
        "priority_tier",
        "executive_summary",
        "triage_explanation",
        "immediate_mitigation",
        "patch_guidance",
        "is_ai_generated",
    ],
}

UI_KEYS = (
    "cve_id",
    "priority_tier",
    "executive_summary",
    "triage_explanation",
    "immediate_mitigation",
    "patch_guidance",
    "is_ai_generated",
)

VERSION_PATTERN = re.compile(
    r"(?:\bversion\s+|\bv)(\d+(?:\.\d+){1,3}(?:[-_][A-Za-z0-9]+)?)"
    r"|\bupgrade to\s+(?:v)?(\d+(?:\.\d+){1,3}(?:[-_][A-Za-z0-9]+)?)",
    re.IGNORECASE,
)
PRODUCTISH = re.compile(r"\b([A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+)+)\b")
URL_PATTERN = re.compile(r"https?://[^\s\]\"']+")

_GENAI_CLIENT = None
_GENAI_TYPES = None
_GENAI_IMPORT_ERROR: str | None = None


def _is_placeholder_key(value: str) -> bool:
    lowered = value.strip().lower()
    if not lowered:
        return True
    return any(frag in lowered for frag in PLACEHOLDER_KEY_FRAGMENTS)


def get_gemini_api_key() -> str | None:
    """Return a usable Gemini API key, or None if missing/placeholder."""
    load_dotenv(ROOT / ".env")
    key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    if not key or _is_placeholder_key(key):
        return None
    return key


def _warn(msg: str) -> None:
    print(f"[remediation_agent] WARNING: {msg}")


def _init_genai_client():
    """Lazy-init Google GenAI client. Returns (client, types) or (None, None)."""
    global _GENAI_CLIENT, _GENAI_TYPES, _GENAI_IMPORT_ERROR

    if _GENAI_CLIENT is not None and _GENAI_TYPES is not None:
        return _GENAI_CLIENT, _GENAI_TYPES
    if _GENAI_IMPORT_ERROR:
        return None, None

    api_key = get_gemini_api_key()
    if not api_key:
        _warn(
            "GEMINI_API_KEY is missing or still a placeholder in the environment/.env. "
            "Falling back to the deterministic offline playbook template."
        )
        return None, None

    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        _GENAI_IMPORT_ERROR = str(exc)
        _warn(
            "Could not import google-genai (`from google import genai`). "
            "Install with: pip install google-genai python-dotenv\n"
            f"  Details: {exc}\n"
            "Falling back to the deterministic offline playbook template."
        )
        return None, None

    try:
        _GENAI_CLIENT = genai.Client(api_key=api_key)
        _GENAI_TYPES = types
        return _GENAI_CLIENT, _GENAI_TYPES
    except Exception as exc:  # noqa: BLE001 — never crash triage UI
        _warn(
            f"Failed to initialize Gemini client ({exc}). "
            "Falling back to the deterministic offline playbook template."
        )
        return None, None


def _parse_reference_urls(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(u).strip() for u in value if str(u).strip()]
    text = str(value).strip()
    if not text or text in {"[]", "nan", "None"}:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(u).strip() for u in parsed if str(u).strip()]
    except json.JSONDecodeError:
        pass
    return [p.strip() for p in re.split(r"[;|]", text) if p.strip()]


def _parse_reasons(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value is None or (isinstance(value, float) and str(value) == "nan"):
        return {}
    text = str(value).strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {"signals": parsed}
    except json.JSONDecodeError:
        return {"raw": text}


def build_prompt(row: dict[str, Any]) -> str:
    refs = _parse_reference_urls(row.get("reference_urls"))
    reasons = _parse_reasons(row.get("reasons"))
    priority = str(row.get("priority", "P2"))
    score = row.get("priority_score", "n/a")
    rank = row.get("rank", "n/a")
    ref_block = "\n".join(f"- {u}" for u in refs) if refs else "- (none provided)"

    return f"""You are a security triage assistant generating a remediation playbook.

STRICT RULES:
1. Ground impact ONLY on the DESCRIPTION and WEAKNESS below. Do not invent products, vendors, or behaviors.
2. Priority tier is FIXED at {priority}. Do NOT change, upgrade, or downgrade it. Only explain it using REASONS.
3. Explain why this CVE ranked highly using REASONS (model signals). Label the ML value as "Priority Score" or "Rank" only. NEVER say "X% chance of exploit" or similar probability language.
4. Immediate mitigation: only standard safe stopgaps (perimeter firewall rules, disable unneeded services, network isolation, least privilege). No speculative product-specific hacks.
5. Patch guidance: ONLY cite URLs from REFERENCE URLS below. NEVER invent software versions (e.g. "upgrade to v1.2.3") or URLs. If no patch/advisory URL is listed, set patch_guidance exactly to:
   "{NO_PATCH_MSG}"
6. Return JSON matching the schema. Set is_ai_generated to true. Set priority_tier to {priority}. Set cve_id to {row.get("cve_id")}.

CVE_ID: {row.get("cve_id")}
PRIORITY_TIER (immutable): {priority}
PRIORITY_SCORE: {score}
RANK: {rank}
DESCRIPTION: {row.get("description", "")}
WEAKNESS: {row.get("weakness") or row.get("cwe_name") or "Unassigned"}
VENDOR: {row.get("vendor", "")}
AFFECTED_PRODUCTS: {row.get("affected_products", "")}
CVSS_SCORE: {row.get("cvss_score", "Pending Review")}
REASONS_JSON: {json.dumps(reasons, ensure_ascii=False)}
REFERENCE_URLS:
{ref_block}
"""


def grounding_validation(playbook: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    """Flag/sanitize invented product names and version patterns not present in input."""
    grounded_text = " ".join(
        str(row.get(k, "") or "")
        for k in (
            "description",
            "weakness",
            "cwe_name",
            "vendor",
            "affected_products",
            "reference_urls",
            "reasons",
            "cve_id",
        )
    ).lower()

    allowed_urls = set(_parse_reference_urls(row.get("reference_urls")))
    out = dict(playbook)
    flags: list[str] = []

    out["cve_id"] = str(row.get("cve_id"))
    out["priority_tier"] = str(row.get("priority", out.get("priority_tier", "P2")))
    out["is_ai_generated"] = True

    combined = " ".join(
        str(out.get(k, ""))
        for k in (
            "executive_summary",
            "triage_explanation",
            "immediate_mitigation",
            "patch_guidance",
        )
    )

    if re.search(r"\b\d{1,3}\s*%\s*chance of exploit", combined, re.IGNORECASE):
        flags.append("probability_language")
        out["triage_explanation"] = re.sub(
            r"\b\d{1,3}\s*%\s*chance of exploit\b",
            "elevated Priority Score",
            out.get("triage_explanation", ""),
            flags=re.IGNORECASE,
        )

    for match in VERSION_PATTERN.finditer(combined):
        token = next((g for g in match.groups() if g), match.group(0))
        if token.lower() not in grounded_text and not any(token in u for u in allowed_urls):
            flags.append(f"invented_version:{token}")
            out["patch_guidance"] = re.sub(
                rf"(?i)upgrade to\s+(?:v)?{re.escape(token)}",
                "apply the vendor fix linked below (if any)",
                out.get("patch_guidance", ""),
            )

    for url in URL_PATTERN.findall(out.get("patch_guidance", "")):
        cleaned = url.rstrip(").,];")
        if cleaned not in allowed_urls:
            flags.append(f"invented_url:{cleaned}")
            out["patch_guidance"] = (
                NO_PATCH_MSG
                if not allowed_urls
                else "Apply vendor guidance using only these verified references: "
                + "; ".join(sorted(allowed_urls))
            )
            break

    if not allowed_urls:
        if "verified vendor patch url" not in out.get("patch_guidance", "").lower():
            out["patch_guidance"] = NO_PATCH_MSG

    allowlist = {
        "Priority Score",
        "Known Exploited",
        "Remote Code",
        "Code Injection",
        "Untrusted Data",
        "Improper Authentication",
        "Improper Access",
        "Cross Site",
        "Identity Proxy",
        "Message Broker",
    }
    for match in PRODUCTISH.finditer(combined):
        name = match.group(1).strip()
        if name in allowlist or name.upper().startswith("CVE-"):
            continue
        if name.lower() not in grounded_text:
            flags.append(f"ungrounded_product:{name}")

    out["_validation_flags"] = flags
    out["_validation_ok"] = len(flags) == 0
    return out


def clean_playbook_for_ui(playbook: dict[str, Any]) -> dict[str, Any]:
    """Strip internal validation keys for Streamlit rendering."""
    return {k: playbook.get(k) for k in UI_KEYS}


def _offline_playbook(row: dict[str, Any]) -> dict[str, Any]:
    """Deterministic schema-valid playbook when Gemini is unavailable."""
    refs = _parse_reference_urls(row.get("reference_urls"))
    reasons = _parse_reasons(row.get("reasons"))
    reason_bits = ", ".join(f"{k}={v}" for k, v in list(reasons.items())[:4]) or "model signals"
    weakness = row.get("weakness") or row.get("cwe_name") or "Unassigned"
    summary = (
        f"{row.get('cve_id')}: based on the provided description, an attacker may exploit "
        f"{weakness} against {row.get('affected_products') or row.get('vendor') or 'the affected component'}."
    )
    patch = (
        "Follow vendor remediation using only these verified references: " + "; ".join(refs)
        if refs
        else NO_PATCH_MSG
    )
    draft = {
        "cve_id": str(row.get("cve_id")),
        "priority_tier": str(row.get("priority", "P2")),
        "executive_summary": summary,
        "triage_explanation": (
            f"Rank {row.get('rank')} with Priority Score {row.get('priority_score')} "
            f"due to signals: {reason_bits}. Priority tier remains {row.get('priority')}."
        ),
        "immediate_mitigation": (
            "Restrict external access with perimeter firewall rules, isolate the affected "
            "service segment, and disable unused management/diagnostic interfaces until patched."
        ),
        "patch_guidance": patch,
        "is_ai_generated": True,
    }
    return grounding_validation(draft, row)


def generate_playbook(row: dict[str, Any], *, force_offline: bool = False) -> dict[str, Any]:
    """Generate one playbook. Never raises for missing SDK/key — falls back offline."""
    if force_offline:
        return _offline_playbook(row)

    client, types = _init_genai_client()
    if client is None or types is None:
        return _offline_playbook(row)

    prompt = build_prompt(row)
    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=PLAYBOOK_SCHEMA,
                temperature=0.2,
            ),
        )
        raw = json.loads(response.text)
    except Exception as exc:  # noqa: BLE001 — keep judging UI alive
        _warn(
            f"Gemini call failed for {row.get('cve_id')} ({exc}). "
            "Falling back to offline template."
        )
        return _offline_playbook(row)

    return grounding_validation(raw, row)


def load_cached_playbooks(path: Path | None = None) -> dict[str, dict[str, Any]]:
    cache_path = path or CACHED_PLAYBOOKS_PATH
    if not cache_path.exists():
        return {}
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _warn(f"Could not read playbook cache ({exc}).")
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): v for k, v in data.items() if isinstance(v, dict)}


def save_cached_playbooks(cache: dict[str, dict[str, Any]], path: Path | None = None) -> Path:
    cache_path = path or CACHED_PLAYBOOKS_PATH
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    clean = {cve: clean_playbook_for_ui(pb) for cve, pb in cache.items()}
    cache_path.write_text(json.dumps(clean, indent=2, ensure_ascii=False), encoding="utf-8")
    return cache_path


def _load_enriched_frame(enriched_df=None):
    import pandas as pd

    if enriched_df is not None:
        return enriched_df
    if ENRICHED_OUT.exists():
        return pd.read_csv(ENRICHED_OUT)
    df = enrich_top500()
    save_enriched(df)
    return df


def get_playbook_for_cve(cve_id: str, enriched_df=None) -> dict:
    """
    Streamlit UI entrypoint.

    1. Checks if cve_id is in results/cached_playbooks.json (instant return).
    2. If not cached, looks up the cve_id in results/top500_enriched.csv and generates it live using Gemini.
    3. Returns a clean dictionary ready for UI rendering.
    """
    cve_id = str(cve_id).strip()
    cache = load_cached_playbooks()
    if cve_id in cache:
        return clean_playbook_for_ui(cache[cve_id])

    df = _load_enriched_frame(enriched_df)
    matches = df[df["cve_id"].astype(str) == cve_id]
    if matches.empty:
        return {
            "cve_id": cve_id,
            "priority_tier": "P2",
            "executive_summary": f"No enriched metadata found for {cve_id}.",
            "triage_explanation": "CVE was not present in the enriched top-500 table.",
            "immediate_mitigation": (
                "Isolate the asset if exposure is suspected and re-run enrichment "
                "after ranking outputs are available."
            ),
            "patch_guidance": NO_PATCH_MSG,
            "is_ai_generated": True,
        }

    playbook = generate_playbook(matches.iloc[0].to_dict())
    clean = clean_playbook_for_ui(playbook)

    # Opportunistically extend cache for subsequent UI hits.
    cache[cve_id] = clean
    try:
        save_cached_playbooks(cache)
    except OSError as exc:
        warnings.warn(f"Could not update playbook cache: {exc}", stacklevel=2)

    return clean


def generate_playbooks_for_enriched(
    enriched_path: Path | None = None,
    *,
    limit: int = 3,
    force_offline: bool = False,
) -> list[dict[str, Any]]:
    import pandas as pd

    path = enriched_path or ENRICHED_OUT
    if not path.exists():
        df = enrich_top500()
        save_enriched(df, path)
    else:
        df = pd.read_csv(path)

    playbooks = []
    for _, row in df.head(limit).iterrows():
        playbooks.append(generate_playbook(row.to_dict(), force_offline=force_offline))
    return playbooks


def main() -> None:
    print("=== Smoke: enrich top500 ===")
    enriched = enrich_top500()
    out = save_enriched(enriched)
    print(enriched.to_string(index=False))
    print()
    print("=== Smoke: remediation playbooks ===")
    force_offline = "--offline" in sys.argv
    playbooks = []
    for _, row in enriched.head(2).iterrows():
        pb = generate_playbook(row.to_dict(), force_offline=force_offline)
        playbooks.append(pb)
        print(json.dumps(clean_playbook_for_ui(pb), indent=2))
        if pb.get("_validation_flags"):
            print("validation_flags:", pb["_validation_flags"])
        print("---")

    # Smoke output only, not a result: keep it out of results/.
    sample_path = ROOT / "docs" / "examples" / "sample_playbooks_DUMMY.json"
    sample_path.parent.mkdir(parents=True, exist_ok=True)
    with sample_path.open("w", encoding="utf-8") as fh:
        json.dump([clean_playbook_for_ui(pb) for pb in playbooks], fh, indent=2)
    print(f"Wrote {sample_path}")

    # Quick UI helper smoke
    sample_cve = str(enriched.iloc[0]["cve_id"])
    print("=== Smoke: get_playbook_for_cve ===")
    print(json.dumps(get_playbook_for_cve(sample_cve, enriched), indent=2))


if __name__ == "__main__":
    main()
