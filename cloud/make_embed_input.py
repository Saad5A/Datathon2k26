"""Write data_cache/descriptions_to_embed.parquet (cve_id, text) for the Granite embedding step.

Run: .venv/bin/python cloud/make_embed_input.py

Rows: every CVE in the backtest pool (src/model/pool.py) plus every CVE in scoreboard_2026.csv, one row per cve_id.
text = the description with exploitation wording masked exactly as the TF-IDF text model does
(src/model/candidates.py `masked`), so embeddings and TF-IDF see the same words.
Prints a token estimate (chars/4; an estimate, not the model tokenizer), writes results/embed_input_summary.json and
registers its numbers as `unverified` in results/claims_ibm.json.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "model"))
from candidates import masked  # noqa: E402  same masking as the text model
from pool import data_dir, load_pool, load_vulns  # noqa: E402

OUT = ROOT / "data_cache" / "descriptions_to_embed.parquet"
SUMMARY = ROOT / "results" / "embed_input_summary.json"
CLAIMS = ROOT / "results" / "claims_ibm.json"
MAX_TOKENS = 512  # ibm/granite-embedding-278m-multilingual input limit (docs/ibm.md)


def main():
    pool = load_pool()[["cve_id", "description"]].assign(source="pool")
    sb = pd.read_csv(data_dir() / "scoreboard_2026.csv", usecols=["cve_id"])
    v = load_vulns(cols=["cve_id", "published", "description"])
    sb = sb.merge(v[["cve_id", "description"]], on="cve_id", how="left").assign(source="scoreboard_2026")
    missing = int(sb.description.isna().sum())
    df = masked(pd.concat([pool, sb], ignore_index=True))
    n_overlap = int(df.cve_id.duplicated().sum())
    df = df.drop_duplicates("cve_id", keep="first").rename(columns={"description": "text"})[["cve_id", "text"]]
    assert df.cve_id.is_unique and len(df) == len(pool) + len(sb) - n_overlap
    OUT.parent.mkdir(exist_ok=True)
    df.to_parquet(OUT, index=False)

    chars = df.text.str.len().to_numpy()
    est = chars / 4
    summ = {"rows": len(df), "rows_pool": len(pool), "rows_scoreboard": len(sb), "overlap": n_overlap,
            "scoreboard_missing_description": missing, "empty_texts": int((chars == 0).sum()),
            "unique_texts": int(df.text.nunique()),
            "chars_percentiles": {f"p{q}": int(np.percentile(chars, q)) for q in (50, 90, 99, 100)},
            "est_tokens_total": int(est.sum()), "est_tokens_mean": round(float(est.mean()), 1),
            "est_tokens_capped_total": int(np.minimum(est, MAX_TOKENS).sum()),
            "share_over_max_tokens": round(float((est > MAX_TOKENS).mean()), 4),
            "_note": f"Token figures are ESTIMATES (characters / 4), not the model tokenizer; max input {MAX_TOKENS}."}
    SUMMARY.write_text(json.dumps(summ, indent=2))
    print(f"wrote {OUT.relative_to(ROOT)} and {SUMMARY.relative_to(ROOT)}")
    print(json.dumps(summ, indent=2))

    claims = json.loads(CLAIMS.read_text()) if CLAIMS.exists() else {}
    for k, text, unit in [("rows", "CVE descriptions prepared for Granite embedding (pool + 2026 scoreboard)", "count"),
                          ("unique_texts", "Distinct masked description texts to embed", "count"),
                          ("est_tokens_total", "ESTIMATED tokens to embed (characters/4)", "count"),
                          ("share_over_max_tokens", f"ESTIMATED share of descriptions longer than {MAX_TOKENS} tokens",
                           "fraction")]:
        old = claims.get(f"embed_input.{k}", {})
        same = old.get("value") == summ[k] and old.get("status") == "verified"
        claims[f"embed_input.{k}"] = {"text": text, "value": summ[k], "unit": unit,
                                      "source_script": "cloud/make_embed_input.py",
                                      "output_file": "results/embed_input_summary.json",
                                      "status": "verified" if same else "unverified",
                                      "verified_by": old.get("verified_by") if same else None}
    CLAIMS.write_text(json.dumps(claims, indent=2))


if __name__ == "__main__":
    main()
