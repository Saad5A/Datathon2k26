"""Embed CVE descriptions with IBM Granite (watsonx.ai or local Hugging Face). Standalone: needs only pandas, numpy,
pyarrow, plus ibm-watsonx-ai (WATSONX) or sentence-transformers (LOCAL). Model IDs and doc URLs: docs/ibm.md.

  python cloud/embed_granite.py --provider LOCAL --estimate     # counts and token estimate, no model, no calls
  python cloud/embed_granite.py --provider WATSONX --limit 20   # dry run on 20 rows
  python cloud/embed_granite.py --provider LOCAL                # full run

Input  data_cache/descriptions_to_embed.parquet (cve_id, text), built by cloud/make_embed_input.py.
Output data_cache/granite_embeddings.parquet (cve_id, vector: fixed-size list of float32, L2-normalised)
       + granite_embeddings.meta.json next to it (no secrets). --limit/--ids write *_subset files instead.
Cache  <out dir>/embed_cache/cache.sqlite, keyed by sha256(model_id + text), committed after every batch, so a crash,
       Ctrl-C or quota stop loses at most one batch; rerun the same command to resume.
Credentials (WATSONX only): env vars WATSONX_APIKEY, WATSONX_URL, WATSONX_PROJECT_ID, or a .env file in the repo
root or the current directory. They are never printed or written anywhere.
"""
import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
MODELS = {  # verified 2026-11-07, see docs/ibm.md
    "WATSONX": "ibm/granite-embedding-278m-multilingual",
    "LOCAL": "ibm-granite/granite-embedding-278m-multilingual",
}
HF_REVISION = "a9cb5338491faf32b73dd17b714a31821c021bbf"  # HF commit pinned for reproducibility
DIM = 768
MAX_TOKENS = 512           # model input limit (both providers)
LITE_TOKENS = 300_000      # watsonx.ai Runtime Lite plan: foundation-model tokens per month (docs/ibm.md)
RETRIES = 6


def load_dotenv():
    """Minimal .env reader (KEY=VALUE lines). Values are never printed.

    Existing non-empty env vars win. Empty placeholders are overwritten from .env
    so a blank WATSONX_APIKEY in the shell cannot block a real key in .env.
    """
    for p in (ROOT / ".env", Path.cwd() / ".env"):
        if p.is_file():
            # utf-8-sig strips a leading BOM so WATSONX_APIKEY is not mis-named on Windows.
            for line in p.read_text(encoding="utf-8-sig").splitlines():
                k, sep, v = line.strip().partition("=")
                if sep and not k.startswith("#"):
                    key = k.strip()
                    val = v.strip().strip('"').strip("'")
                    if not key:
                        continue
                    if not os.environ.get(key):
                        os.environ[key] = val


def est_tokens(texts):
    """ESTIMATE: chars/4, capped at the model limit (inputs beyond it are truncated)."""
    return int(sum(min(len(t) / 4, MAX_TOKENS) for t in texts))


def make_embedder(provider, batch):
    """Return (fn(list[str]) -> list[list[float]], info dict)."""
    if provider == "WATSONX":
        load_dotenv()
        need = ["WATSONX_APIKEY", "WATSONX_URL", "WATSONX_PROJECT_ID"]
        if [k for k in need if not os.environ.get(k)]:
            sys.exit(f"missing env vars (names only): {[k for k in need if not os.environ.get(k)]}; see cloud/README.md")
        # Verified against https://ibm.github.io/watsonx-ai-python-sdk/v1.9.1/fm_embeddings.html (Embeddings class,
        # embed_documents, EmbedTextParamsMetaNames.TRUNCATE_INPUT_TOKENS) and .../v1.9.1/setup_cloud.html
        # (Credentials(url=, api_key=)). Not executed by us: the SDK is not installed in this repo yet.
        from ibm_watsonx_ai import Credentials
        from ibm_watsonx_ai.foundation_models import Embeddings
        from ibm_watsonx_ai.metanames import EmbedTextParamsMetaNames as P
        emb = Embeddings(model_id=MODELS["WATSONX"],
                         credentials=Credentials(url=os.environ["WATSONX_URL"], api_key=os.environ["WATSONX_APIKEY"]),
                         project_id=os.environ["WATSONX_PROJECT_ID"],
                         params={P.TRUNCATE_INPUT_TOKENS: MAX_TOKENS},  # UNVERIFIED whether 512 counts special tokens
                         batch_size=batch, concurrency_limit=1)  # Lite plan: 2 requests/s

        def fn(texts):
            out = emb.embed_documents(texts=texts, concurrency_limit=1)
            time.sleep(0.5)  # stay under 2 requests/s
            return out
        return fn, {"sdk": "ibm-watsonx-ai", "concurrency": 1}

    from sentence_transformers import SentenceTransformer  # verified against sbert.net v6.2 API reference
    model = SentenceTransformer(MODELS["LOCAL"], revision=HF_REVISION)  # device=None: picks GPU if available
    # Hard-cap at the model limit so long CVE descriptions never exceed 512 tokens (GPU OOM / tokenizer overflow).
    model.max_seq_length = MAX_TOKENS
    # Encode micro-batch: smaller than the cache commit --batch so T4 (16 GB) stays under token*batch memory.
    encode_bs = min(int(batch), 64)
    device = str(model.device)
    if "cuda" in device.lower():
        encode_bs = min(int(batch), 128)  # A100/T4: still truncate to MAX_TOKENS per text

    def fn(texts):
        return model.encode(
            texts,
            batch_size=encode_bs,
            convert_to_numpy=True,
            show_progress_bar=False,
            truncate_dim=None,
        )

    return fn, {
        "sdk": "sentence-transformers",
        "hf_revision": HF_REVISION,
        "device": device,
        "encode_batch_size": encode_bs,
        "max_seq_length": MAX_TOKENS,
    }


def key(model_id, text):
    return hashlib.sha256(f"{model_id}\n{text}".encode()).hexdigest()


def open_cache(out):
    d = out.parent / "embed_cache"
    d.mkdir(parents=True, exist_ok=True)
    (d / ".gitignore").write_text("*\n")  # never commit the cache
    con = sqlite3.connect(d / "cache.sqlite")
    con.execute("CREATE TABLE IF NOT EXISTS emb (key TEXT PRIMARY KEY, model_id TEXT, vec BLOB)")
    return con


def cached_keys(con, keys):
    have = set()
    for i in range(0, len(keys), 900):  # sqlite parameter limit
        chunk = keys[i:i + 900]
        have |= {r[0] for r in con.execute(f"SELECT key FROM emb WHERE key IN ({','.join('?' * len(chunk))})", chunk)}
    return have


def redact(msg):
    for k in ("WATSONX_APIKEY", "WATSONX_PROJECT_ID"):
        if os.environ.get(k):
            msg = msg.replace(os.environ[k], "***")
    return msg


def embed_with_retry(fn, texts):
    for attempt in range(RETRIES):
        try:
            vecs = np.asarray(fn(texts), dtype=np.float32)
            if vecs.shape != (len(texts), DIM):
                raise ValueError(f"unexpected embedding shape {vecs.shape}")
            return vecs
        except KeyboardInterrupt:
            raise
        except Exception as e:  # SDK error classes not verified; message only, never the request
            if attempt == RETRIES - 1:
                raise
            wait = min(2 ** attempt * 2, 60)
            print(f"  batch failed ({type(e).__name__}: {redact(str(e))[:200]}); retry {attempt + 1}/{RETRIES - 1} in {wait}s")
            time.sleep(wait)


def run(args, fn=None):
    provider, model_id = args.provider, MODELS[args.provider]
    df = pd.read_parquet(args.inp, columns=["cve_id", "text"])
    subset = bool(args.limit or args.ids)
    if args.ids:
        ids = set(pd.read_csv(args.ids, usecols=["cve_id"]).cve_id)
        df = df[df.cve_id.isin(ids)]
    if args.limit:
        df = df.head(args.limit)
    out = Path(args.out or ROOT / "data_cache" / (f"granite_embeddings_{provider.lower()}_subset.parquet" if subset
                                                  else "granite_embeddings.parquet"))
    df = df.assign(key=[key(model_id, t) for t in df.text])
    con = open_cache(out)
    uniq = df.drop_duplicates("key")
    have = cached_keys(con, list(uniq.key))
    todo = uniq[~uniq.key.isin(have)]
    todo = todo.iloc[np.argsort(todo.text.str.len().to_numpy(), kind="stable")]  # similar lengths batch together
    tokens = est_tokens(todo.text)
    print(f"provider {provider} model {model_id}: rows {len(df)}, unique texts {len(uniq)}, cached {len(have)}, "
          f"to embed {len(todo)}, ESTIMATED tokens {tokens:,} (chars/4, capped at {MAX_TOKENS}/text)")
    if args.estimate:
        return
    if provider == "WATSONX" and tokens > args.max_tokens:
        sys.exit(f"STOP: estimated {tokens:,} tokens > --max-tokens {args.max_tokens:,} (Lite plan allows {LITE_TOKENS:,}"
                 f"/month). Use --limit/--ids, or raise --max-tokens only if your plan allows it.")

    info = {}
    if len(todo):
        if fn is None:
            fn, info = make_embedder(provider, args.batch)
        t0, done = time.time(), 0
        for i in range(0, len(todo), args.batch):
            b = todo.iloc[i:i + args.batch]
            try:
                vecs = embed_with_retry(fn, list(b.text))
            except Exception as e:
                sys.exit(f"STOPPED after {done}/{len(todo)} new texts ({type(e).__name__}). Progress is cached; "
                         f"rerun the same command to resume.")
            con.executemany("INSERT OR REPLACE INTO emb VALUES (?, ?, ?)",
                            [(k, model_id, v.tobytes()) for k, v in zip(b.key, vecs)])
            con.commit()
            done += len(b)
            rate = done / max(time.time() - t0, 1e-9)
            if done == len(todo) or (i // args.batch) % 20 == 0:
                    print(f"  {done}/{len(todo)} embedded, {rate:.1f} texts/s, ~{(len(todo) - done) / rate / 60:.1f} min left")

    vec = {}
    keys = list(uniq.key)
    for i in range(0, len(keys), 900):
        chunk = keys[i:i + 900]
        for k, blob in con.execute(f"SELECT key, vec FROM emb WHERE key IN ({','.join('?' * len(chunk))})", chunk):
            vec[k] = np.frombuffer(blob, dtype=np.float32)
    M = np.stack([vec[k] for k in df.key])
    M /= np.linalg.norm(M, axis=1, keepdims=True).clip(1e-12)  # L2-normalise (HF model already does; watsonx: unknown)
    out.parent.mkdir(parents=True, exist_ok=True)
    table = pa.table({"cve_id": pa.array(df.cve_id.astype(str)),
                      "vector": pa.FixedSizeListArray.from_arrays(pa.array(M.astype(np.float32).ravel()), DIM)})
    pq.write_table(table, out)
    meta = {"model_id": model_id, "provider": provider, "dimension": DIM, "n_rows": len(df), "n_unique_texts": len(uniq),
            "n_embedded_this_run": len(todo), "estimated_tokens_this_run": tokens, "truncate_tokens": MAX_TOKENS,
            "l2_normalised": True, "subset": subset, "limit": args.limit, "ids_file": args.ids,
            "input_file": str(args.inp), "input_sha256": hashlib.sha256(Path(args.inp).read_bytes()).hexdigest(),
            "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), **info}
    out.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2))
    print(f"wrote {out} ({len(df)} x {DIM}) and {out.with_suffix('.meta.json').name}")
    return out


def parse(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provider", type=str.upper, choices=list(MODELS), default=os.environ.get("PROVIDER", "LOCAL").upper())
    ap.add_argument("--in", dest="inp", default=str(ROOT / "data_cache" / "descriptions_to_embed.parquet"))
    ap.add_argument("--out", help="output parquet; the cache lives in <out dir>/embed_cache/")
    ap.add_argument("--limit", type=int, help="dry run: only the first N rows")
    ap.add_argument("--ids", help="CSV with a cve_id column: embed only these CVEs")
    ap.add_argument("--batch", type=int, default=256, help="texts per request / per cache commit")
    ap.add_argument("--max-tokens", type=int, default=250_000, help="WATSONX: refuse to start above this estimate")
    ap.add_argument("--estimate", action="store_true", help="print counts and token estimate, then exit")
    return ap.parse_args(argv)


if __name__ == "__main__":
    run(parse())
