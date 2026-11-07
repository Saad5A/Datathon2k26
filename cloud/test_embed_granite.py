"""Offline check of cloud/embed_granite.py: caching, crash-resume, dedup, output format. No model, no network.
Run: .venv/bin/python cloud/test_embed_granite.py
"""
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

import embed_granite as E


def fake(texts):  # deterministic vector per text
    return [np.random.default_rng(abs(hash(t)) % 2**32).normal(size=E.DIM) for t in texts]


def main():
    E.time.sleep = lambda s: None
    with tempfile.TemporaryDirectory() as d:
        inp, out = Path(d) / "in.parquet", Path(d) / "emb.parquet"
        pd.DataFrame({"cve_id": [f"CVE-X-{i}" for i in range(10)],
                      "text": [f"text {i % 7}" for i in range(10)]}).to_parquet(inp)  # 7 unique texts
        args = E.parse(["--provider", "LOCAL", "--in", str(inp), "--out", str(out), "--batch", "3"])
        calls = []

        def crashing(texts):
            calls.append(len(texts))
            if len(calls) > 1:
                raise RuntimeError("quota")
            return fake(texts)
        try:
            E.run(args, fn=crashing)
            raise AssertionError("expected a stop")
        except SystemExit:
            pass
        assert not out.exists()
        seen = []
        E.run(args, fn=lambda t: seen.append(len(t)) or fake(t))
        assert sum(seen) == 4, seen  # 3 cached by the first run, 4 new
        df = pd.read_parquet(out)
        M = np.stack(df.vector.to_numpy())
        assert len(df) == 10 and M.shape == (10, E.DIM) and M.dtype == np.float32
        assert np.allclose(np.linalg.norm(M, axis=1), 1, atol=1e-5)
        assert np.allclose(M[0], M[7])  # same text, same vector
        assert Path(str(out.with_suffix(".meta.json"))).exists()
        seen.clear()
        E.run(args, fn=lambda t: seen.append(len(t)) or fake(t))
        assert seen == []  # fully cached: no calls
    print("ok")


if __name__ == "__main__":
    main()
