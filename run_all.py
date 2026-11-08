"""Rerun the whole model pipeline in order, stopping at the first failure.

    python run_all.py                 # everything
    python run_all.py --from final    # resume from a step (names below)

Steps: pool -> checks -> reproduce_first_pass -> candidates -> cap -> leakage -> drift -> final -> backtest_summary,
then granite (only if data_cache/granite_embeddings.parquet exists) and, only if granite's pre-registered rule adopted
a Granite text source, final again with that source. Uses the current Python (run it with the project venv).
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODEL = ROOT / "src" / "model"
STEPS = ["pool", "checks", "reproduce_first_pass", "candidates", "cap", "leakage", "drift", "final", "backtest_summary"]
EMB = ROOT / "data_cache" / "granite_embeddings.parquet"


def run(name, *args):
    t = time.time()
    print(f"== {name} {' '.join(args)}", flush=True)
    code = subprocess.run([sys.executable, str(MODEL / f"{name}.py"), *args], cwd=ROOT).returncode
    print(f"== {name}: {'OK' if code == 0 else f'FAILED (exit {code})'} in {time.time() - t:.0f}s", flush=True)
    if code:
        sys.exit(code)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", choices=STEPS + ["granite"], default=STEPS[0])
    ap.add_argument("--tfidf-only", action="store_true", help="allow rebuilding final files without Granite (not the submitted version)")
    args = ap.parse_args()
    start = args.start
    if not EMB.exists() and not args.tfidf_only and start in STEPS and STEPS.index(start) <= STEPS.index("final"):
        sys.exit(f"{EMB.relative_to(ROOT)} not found. The submitted top500.csv/scores_2026.csv use Granite (G2); without it, "
                 "'final' would overwrite them with the TF-IDF-only version. Create the embeddings first (cloud/README.md), "
                 "or pass --tfidf-only to rebuild the TF-IDF version on purpose.")
    t0 = time.time()
    for name in STEPS[STEPS.index(start):] if start in STEPS else []:
        run(name)
    if EMB.exists():
        run("granite")
        flag = json.loads((ROOT / "results" / "granite_comparison.json").read_text())["selection"]["final_py_flag"]
        if flag:
            run("final", *flag.split())
        else:
            print("== granite not adopted by the pre-registered rule: TF-IDF files stay", flush=True)
    else:
        print(f"== granite skipped: {EMB.relative_to(ROOT)} not found", flush=True)
    print(f"== all done in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
