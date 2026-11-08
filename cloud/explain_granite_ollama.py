"""Grounded Granite summaries for the top-ranked CVEs, via local Ollama (CPU).

What it does:
- reads results/scores_2026.csv (the verified ranking), data/vulnerabilities.csv,
  and data/references.csv;
- asks IBM Granite 4.2 3B for ONE plain-English summary grounded in the description;
- validates the summary (no URLs, no foreign CVE IDs, no number/version not in the
  description, no banned exploitation/probability claims, content-word overlap);
- falls back to the description's first sentence if validation fails;
- builds rank/priority/reasons/action/evidence deterministically from the record.

It does NOT change scores_2026.csv or top500.csv. The ranking stays frozen.

Run:
    ollama pull granite4.2:3b
    .venv/bin/python cloud/explain_granite_ollama.py --limit 100
Writes results/granite_summaries_top100.json (+ .meta.json).
"""
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MODEL_ID = "granite4.2:3b"
PROMPT_VERSION = "summary-v1"
NUM_RE = re.compile(r"(?<![\w.-])\d+(?:\.\d+)*(?![\w-])")
URL_RE = re.compile(r"https?://[^\s)\]>,]+", re.I)
CVE_RE = re.compile(r"\bCVE-\d{4}-\d{4,}\b", re.I)
BANNED = [
    r"\b(?:kev|cisa)\b",
    r"\bexploited\s+in\s+the\s+wild\b",
    r"\bransomware\b",
    r"\bwill\s+be\s+exploited\b",
    r"\bprobability\b",
    r"\bchance\b",
    r"\b\d+(?:\.\d+)?\s?%",
]
STOP = set(
    "a an the and or of to in on for with by from is are was were be been being this that these those "
    "it its as at via allows allow could can may might will would should not no than then into over under "
    "about after before during while when where which who whom whose".split()
)


def load_refs(cve_ids: set[str]) -> dict[str, list[str]]:
    refs = pd.read_csv(ROOT / "data/references.csv", usecols=["cve_id", "url", "tags"], low_memory=False)
    refs = refs[refs.cve_id.isin(cve_ids)].copy()
    keep = refs.tags.fillna("").str.contains("patch|vendor advisory", case=False, regex=True)
    refs = refs[keep]
    out: dict[str, list[str]] = {}
    for cid, grp in refs.groupby("cve_id"):
        urls: list[str] = []
        for u in grp.url.tolist():
            if isinstance(u, str) and u.startswith("http") and u not in urls:
                urls.append(u)
            if len(urls) >= 3:
                break
        out[cid] = urls
    return out


def prompt_for(desc: str) -> str:
    return f"""Summarize this vulnerability description in one plain-English sentence.
Use ONLY the description. Do not add versions, product names, URLs, CVE IDs, exploitation claims, probabilities or rankings. If the description is already one sentence, restate it faithfully.
Return JSON exactly as {{"summary": "..."}}.
Description:
{desc}
"""


def call_granite(desc: str, model: str, host: str) -> str:
    req = urllib.request.Request(
        f"{host}/api/chat",
        data=json.dumps({
            "model": model,
            "stream": False,
            "think": False,
            "format": "json",
            "messages": [{"role": "user", "content": prompt_for(desc)}],
            "options": {"temperature": 0, "num_predict": 140},
        }).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=600) as r:
        out = json.load(r)
    return json.loads(out["message"].get("content") or "{}").get("summary", "")


def valid_summary(summary: str, desc: str, cve_id: str) -> tuple[bool, list[str]]:
    errors: list[str] = []
    s = summary.strip()
    if not s or len(s) < 20:
        errors.append("too short")
    if len(s) > 500:
        errors.append("too long")
    if len(re.findall(r"[.!?](?:\s|$)", s)) > 2:
        errors.append("more than two sentences")
    if URL_RE.search(s):
        errors.append("URL present")
    for cid in CVE_RE.findall(s):
        if cid.upper() != cve_id.upper():
            errors.append("foreign CVE ID")
    input_nums = set(NUM_RE.findall(desc))
    for num in NUM_RE.findall(CVE_RE.sub(" ", s)):
        if num not in input_nums:
            errors.append(f"number/version not in description: {num}")
    for pat in BANNED:
        if re.search(pat, s, re.I):
            errors.append("banned claim")
    toks = [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9_.-]+", s) if w.lower() not in STOP]
    if toks:
        supported = sum(1 for w in toks if w in desc.lower())
        if supported / len(toks) < 0.65:
            errors.append(f"low content-word overlap {supported}/{len(toks)}")
    return (not errors, errors)


def first_sentence(desc: str) -> str:
    parts = re.split(r"(?<=[.!?])\s", desc.strip())
    return parts[0][:400] if parts and parts[0] else desc[:400]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--model", default=MODEL_ID)
    ap.add_argument("--host", default="http://localhost:11434")
    ap.add_argument("--out", default=str(ROOT / "results" / "granite_summaries_top100.json"))
    args = ap.parse_args()

    scores = pd.read_csv(ROOT / "results" / "scores_2026.csv").sort_values("rank").head(args.limit)
    vulns = pd.read_csv(ROOT / "data" / "vulnerabilities.csv", usecols=["cve_id", "description"], low_memory=False)
    desc = dict(zip(vulns.cve_id, vulns.description.fillna("")))
    refs = load_refs(set(scores.cve_id))
    results = []
    t0 = time.time()
    for i, row in enumerate(scores.itertuples(index=False), 1):
        d = desc.get(row.cve_id, "")
        summary, source, errors = "", "template", []
        try:
            candidate = call_granite(d, args.model, args.host)
            ok, errors = valid_summary(candidate, d, row.cve_id)
            if ok:
                summary, source = candidate.strip(), "granite"
        except Exception as exc:  # noqa: BLE001 - keep the pipeline alive
            errors = [f"call failed: {exc}"]
        if source != "granite":
            summary = first_sentence(d)
        urls = refs.get(row.cve_id, [])
        action = (
            f"Review the vendor advisory: {urls[0]}"
            if urls
            else "No vendor patch reference in the record; apply the vendor's latest update, restrict network exposure, and monitor."
        )
        signals = ", ".join(x.get("signal", "?") for x in json.loads(row.reasons)) or "none"
        results.append({
            "cve_id": row.cve_id,
            "rank": int(row.rank),
            "priority": row.priority,
            "summary": summary,
            "summary_source": source,
            "why_this_rank": f"Rank {int(row.rank)}, priority {row.priority}; signals: {signals}.",
            "suggested_action": action,
            "evidence": [{"field": "description", "quote": first_sentence(d)}],
            "unknowns": [] if urls else ["No vendor patch reference in the record."],
            "ai_generated": source == "granite",
            "model_id": args.model if source == "granite" else "deterministic-template",
            "prompt_version": PROMPT_VERSION,
            "validation_errors": errors,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
        print(f"[{i}/{len(scores)}] {row.cve_id} source={source} errors={errors[:2]}", flush=True)

    meta = {
        "model_id": args.model,
        "prompt_version": PROMPT_VERSION,
        "rows": len(results),
        "granite_summaries": sum(1 for r in results if r["summary_source"] == "granite"),
        "template_fallbacks": sum(1 for r in results if r["summary_source"] != "granite"),
        "elapsed_seconds": round(time.time() - t0, 1),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"meta": meta, "results": results}, indent=2, ensure_ascii=False))
    out.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
