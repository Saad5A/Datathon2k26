"""Google Colab LOCAL embedding runner for the full CVE description set.

Designed for Runtime > T4 or A100 GPU. Reads the 147,818-row parquet and calls
cloud/embed_granite.py --provider LOCAL with token-safe batching
(ibm-granite/granite-embedding-278m-multilingual, max 512 tokens/text).

Colab cells (paste into a notebook after uploading this file + embed_granite.py
+ descriptions_to_embed.parquet to /content):

  !pip install -q -U "sentence-transformers>=3.0" pyarrow pandas numpy
  !python /content/colab_embed_local.py --smoke
  !python /content/colab_embed_local.py

Or from a cloned repo on a GPU VM:

  python cloud/colab_embed_local.py --in data_cache/descriptions_to_embed.parquet
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent if (HERE / "embed_granite.py").is_file() else Path("/content")
EMBED_SCRIPT = HERE / "embed_granite.py"
DEFAULT_IN = Path("/content/descriptions_to_embed.parquet")
DEFAULT_OUT = Path("/content/granite_embeddings.parquet")
# Cache-commit batch: larger than encode micro-batch inside embed_granite.py.
# 256 texts × 512 tokens is safe on T4; bump to 512 on A100 if VRAM allows.
T4_BATCH = 256
A100_BATCH = 512
EXPECTED_ROWS = 147_818


def detect_batch() -> int:
    try:
        import torch

        if not torch.cuda.is_available():
            return 64
        name = (torch.cuda.get_device_name(0) or "").lower()
        if "a100" in name or "h100" in name:
            return A100_BATCH
        return T4_BATCH
    except Exception:  # noqa: BLE001
        return T4_BATCH


def resolve_input(path: Path) -> Path:
    candidates = [
        path,
        ROOT / "data_cache" / "descriptions_to_embed.parquet",
        Path("/content/descriptions_to_embed.parquet"),
        HERE.parent / "data_cache" / "descriptions_to_embed.parquet",
    ]
    for c in candidates:
        if c.is_file():
            return c
    raise SystemExit(
        f"missing descriptions parquet (expected ~{EXPECTED_ROWS} rows). "
        f"Tried: {[str(c) for c in candidates]}"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="inp", default=str(DEFAULT_IN))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--batch", type=int, default=0, help="0 = auto (T4=256, A100=512)")
    ap.add_argument("--smoke", action="store_true", help="embed first 200 rows only")
    ap.add_argument("--estimate", action="store_true")
    args = ap.parse_args()

    if not EMBED_SCRIPT.is_file():
        # Colab flat upload layout: both scripts in /content
        alt = Path("/content/embed_granite.py")
        if alt.is_file():
            script = alt
        else:
            raise SystemExit(f"missing embed_granite.py next to {HERE} or at /content")
    else:
        script = EMBED_SCRIPT

    inp = resolve_input(Path(args.inp))
    try:
        import pandas as pd

        n = len(pd.read_parquet(inp, columns=["cve_id"]))
        print(f"input {inp}: {n:,} rows (expected {EXPECTED_ROWS:,} for full set)")
        if not args.smoke and n != EXPECTED_ROWS:
            print(f"WARNING: row count {n} != {EXPECTED_ROWS}; continuing anyway")
    except Exception as exc:  # noqa: BLE001
        print(f"could not preview parquet ({exc}); continuing")

    batch = args.batch or detect_batch()
    out = Path(args.out)
    if args.smoke:
        out = out.with_name(out.stem + "_smoke.parquet")

    cmd = [
        sys.executable,
        str(script),
        "--provider",
        "LOCAL",
        "--in",
        str(inp),
        "--out",
        str(out),
        "--batch",
        str(batch),
    ]
    if args.smoke:
        cmd.extend(["--limit", "200"])
    if args.estimate:
        cmd.append("--estimate")

    print("running:", " ".join(cmd))
    print("model: ibm-granite/granite-embedding-278m-multilingual | max_seq_length=512 | provider=LOCAL")
    rc = subprocess.call(cmd)
    if rc != 0:
        raise SystemExit(rc)

    meta = out.with_suffix(".meta.json")
    if meta.is_file() and out.parent != Path.cwd():
        # Convenience copy when running under /content
        for artifact in (out, meta):
            if artifact.parent == Path("/content"):
                continue
            dest = Path("/content") / artifact.name
            if artifact.resolve() != dest.resolve() and artifact.is_file():
                shutil.copy2(artifact, dest)
                print(f"copied {artifact.name} -> {dest}")
    print("done. Download the parquet + .meta.json; do NOT commit the ~450 MB full embedding file.")


if __name__ == "__main__":
    main()
