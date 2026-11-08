"""Provenance sidecar and claims-ledger merge shared by leakage.py and drift.py."""
import hashlib
import json
import math
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
CLAIMS = RESULTS / "claims_model_drift.json"


def _git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def write_meta(output_file, script, extra=None):
    """results/<name>.meta.json next to `output_file`: script, commit, dirty flag, UTC date, code hash."""
    out = ROOT / output_file
    # git_dirty: any tracked or untracked change under src/model/ (the code), as in candidates.write_meta. Untracked
    # audit scratch files and the outputs themselves do not count.
    changed = _git("status", "--porcelain", "--", "src/model").splitlines()
    meta = {"script": script, "output_file": output_file, "git_commit": _git("rev-parse", "HEAD"),
            "git_dirty": bool(changed), "git_dirty_files": changed,
            "date_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "code_sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
                            for p in (script, "src/model/sidecar.py", "src/model/pool.py", "src/model/metrics.py")},
            "python": platform.python_version()}
    meta.update(extra or {})
    out.with_name(out.name.rsplit(".", 1)[0] + ".meta.json").write_text(json.dumps(meta, indent=2) + "\n")


def claim(text, value, unit, script, output_file):
    return {"text": text, "value": float(value) if unit != "count" else int(value), "unit": unit,
            "source_script": script, "output_file": output_file, "status": "unverified", "verified_by": None}


def merge_claims(new):
    """Update this script's keys in the ledger. Only an unchanged value AND text keeps an auditor's verdict."""
    old = json.loads(CLAIMS.read_text()) if CLAIMS.exists() else {}
    for key, c in new.items():
        prev = old.get(key)
        if (prev and prev["text"] == c["text"]
                and math.isclose(prev["value"], c["value"], rel_tol=1e-9, abs_tol=1e-12)):
            c["status"], c["verified_by"] = prev["status"], prev["verified_by"]
    old.update(new)
    CLAIMS.write_text(json.dumps(dict(sorted(old.items())), indent=2) + "\n")
    return len(new)
