"""Granite instruct explanations for the top-100 ranked CVEs (optional IBM path).

Grounded on description + model reasons only. Never invents patch versions/URLs.
Provider: watsonx.ai (default) or a dry offline template with --offline.

  python cloud/explain_granite_top100.py --limit 5
  python cloud/explain_granite_top100.py --limit 100

Writes docs/examples/explanations_top100_draft.json keyed by cve_id (not results/ until audited).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "model"))
from pool import data_dir  # noqa: E402

# Not written to results/ until an audit verifies it and the output really comes from an IBM Granite model (see AGENTS.md "Protected files").
OUT = ROOT / "docs" / "examples" / "explanations_top100_draft.json"
SCORES = ROOT / "results" / "scores_2026.csv"
# ca-tor Lite (2026-11-07) does not list ibm/granite-3-8b-instruct; use an available instruct model.
INSTRUCT_MODEL = "meta-llama/llama-3-3-70b-instruct"


def load_dotenv() -> None:
    for p in (ROOT / ".env", Path.cwd() / ".env"):
        if not p.is_file():
            continue
        for line in p.read_text(encoding="utf-8-sig").splitlines():
            k, sep, v = line.strip().partition("=")
            if sep and not k.startswith("#"):
                key = k.strip()
                val = v.strip().strip('"').strip("'")
                if key and not os.environ.get(key):
                    os.environ[key] = val


def grounding_ok(text: str, allowed: str) -> bool:
    allowed_l = allowed.lower()
    for m in re.finditer(r"(?i)upgrade to\s+v?\d+(?:\.\d+){1,3}", text):
        if m.group(0).lower() not in allowed_l:
            return False
    for url in re.findall(r"https?://\S+", text):
        if url.rstrip(").,]") not in allowed:
            return False
    return True


def offline_explanation(row: dict) -> dict:
    reasons = row.get("reasons") or "[]"
    summary = (
        f"{row['cve_id']} is Priority {row['priority']} (rank {row['rank']}). "
        f"Based only on the provided description, defenders should treat the described weakness "
        f"as higher priority because the ranking model cited: {reasons}."
    )
    return {
        "cve_id": row["cve_id"],
        "priority": row["priority"],
        "rank": int(row["rank"]),
        "explanation": summary,
        "is_ai_generated": True,
        "provider": "offline_template",
        "grounding_ok": True,
    }


def watsonx_explain(row: dict) -> dict:
    load_dotenv()
    from ibm_watsonx_ai import Credentials
    from ibm_watsonx_ai.foundation_models import ModelInference

    desc = row.get("description") or ""
    reasons = row.get("reasons") or "[]"
    prompt = f"""You explain why a vulnerability was ranked highly for a security team.
Rules:
- Use ONLY the DESCRIPTION and REASONS below. Do not invent products, versions, patches, or URLs.
- Priority tier {row['priority']} and rank {row['rank']} are fixed; do not change them.
- Call the model value a Priority Score or Rank, never a percent chance of exploit.
- Keep to 4-6 sentences. Label that this is AI-generated.

CVE_ID: {row['cve_id']}
PRIORITY: {row['priority']}
RANK: {row['rank']}
PRIORITY_SCORE: {row.get('score')}
DESCRIPTION: {desc}
REASONS_JSON: {reasons}
"""
    model = ModelInference(
        model_id=INSTRUCT_MODEL,
        credentials=Credentials(
            url=os.environ["WATSONX_URL"],
            api_key=os.environ["WATSONX_APIKEY"],
        ),
        project_id=os.environ["WATSONX_PROJECT_ID"],
    )
    text = model.generate_text(prompt=prompt, params={"max_new_tokens": 220, "temperature": 0.2})
    allowed = f"{desc}\n{reasons}\n{row['cve_id']}"
    ok = grounding_ok(text, allowed)
    return {
        "cve_id": row["cve_id"],
        "priority": row["priority"],
        "rank": int(row["rank"]),
        "explanation": text.strip(),
        "is_ai_generated": True,
        "provider": "WATSONX",
        "model_id": INSTRUCT_MODEL,
        "grounding_ok": ok,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--resume", action="store_true", help="Skip CVE ids already in the output file")
    args = parser.parse_args()

    scores = pd.read_csv(SCORES).sort_values("rank").head(args.limit)
    vulns = pd.read_csv(
        data_dir() / "vulnerabilities.csv",
        usecols=["cve_id", "description"],
        low_memory=False,
    )
    scores = scores.merge(vulns, on="cve_id", how="left")

    out: dict[str, dict] = {}
    if args.resume and OUT.exists():
        out = json.loads(OUT.read_text(encoding="utf-8"))

    for _, row in scores.iterrows():
        d = row.to_dict()
        cve = str(d["cve_id"])
        if cve in out and args.resume:
            continue
        print(f"explain {cve} rank={d['rank']}")
        if args.offline:
            pb = offline_explanation(d)
        else:
            try:
                pb = watsonx_explain(d)
            except Exception as exc:  # noqa: BLE001
                print(f"  watsonx failed ({exc}); using offline template")
                pb = offline_explanation(d)
            time.sleep(0.6)
        out[cve] = pb
        # Checkpoint every 10
        if len(out) % 10 == 0:
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    n_ok = sum(1 for v in out.values() if v.get("grounding_ok"))
    n_wx = sum(1 for v in out.values() if v.get("provider") == "WATSONX")
    print(f"wrote {OUT} ({len(out)} explanations, watsonx={n_wx}, grounding_ok={n_ok})")


if __name__ == "__main__":
    main()
