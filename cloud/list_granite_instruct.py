"""List ibm/granite-*-instruct IDs from SDK enums + authenticated ca-tor catalog.

Writes cloud/granite_instruct_model_id.txt with the preferred Granite instruct ID
(ibm/granite-3-8b-instruct when available; otherwise the best live/enum match).
Never prints secrets.

  python cloud/list_granite_instruct.py
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import load_dotenv
from ibm_watsonx_ai import APIClient, Credentials
from ibm_watsonx_ai.foundation_models.utils.enums import ModelTypes

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "cloud" / "granite_instruct_model_id.txt"
PREFERRED = "ibm/granite-3-8b-instruct"
FALLBACKS = [
    "ibm/granite-3-8b-instruct",
    "ibm/granite-3-2-8b-instruct",
    "ibm/granite-3-3-8b-instruct",
    "ibm/granite-13b-instruct-v2",
    "ibm/granite-13b-instruct-v1",
    "ibm/granite-8b-code-instruct",
]


def enum_ids() -> list[str]:
    return sorted(
        m.value
        for m in ModelTypes
        if "granite" in m.value.lower() and "instruct" in m.value.lower()
    )


def iam_token(apikey: str) -> str:
    data = urllib.parse.urlencode(
        {"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": apikey}
    ).encode()
    req = urllib.request.Request(
        "https://iam.cloud.ibm.com/identity/token",
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))["access_token"]


def live_ids(token: str | None = None) -> tuple[list[str], list[str]]:
    """Return (granite_instruct_ids, all_model_ids) from ca-tor foundation_model_specs."""
    url = (
        "https://ca-tor.ml.cloud.ibm.com/ml/v1/foundation_model_specs"
        "?version=2024-07-25&limit=200"
    )
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    resources = payload.get("resources") or []
    all_ids: list[str] = []
    gi: list[str] = []
    for item in resources:
        mid = item.get("model_id") or item.get("id") or ""
        if not mid:
            continue
        all_ids.append(mid)
        if mid.startswith("ibm/granite") and "instruct" in mid.lower():
            gi.append(mid)
    return sorted(set(gi)), sorted(set(all_ids))


def pick(available: list[str]) -> str:
    for cand in FALLBACKS:
        if cand in available:
            return cand
    return available[0] if available else PREFERRED


def main() -> None:
    load_dotenv(ROOT / ".env", encoding="utf-8-sig")
    enums = enum_ids()
    print("ModelTypes granite-instruct:", enums)

    need = ["WATSONX_APIKEY", "WATSONX_URL", "WATSONX_PROJECT_ID"]
    missing = [k for k in need if not os.getenv(k)]
    token = None
    live: list[str] = []
    all_live: list[str] = []
    if missing:
        print("missing env:", missing)
    else:
        try:
            token = iam_token(os.environ["WATSONX_APIKEY"].strip())
            live, all_live = live_ids(token)
            print("ca-tor live granite-instruct:", live)
            print("ca-tor live model count:", len(all_live))
        except Exception as exc:  # noqa: BLE001
            print("ca-tor live list failed:", type(exc).__name__, str(exc)[:200])
        creds = Credentials(url=os.environ["WATSONX_URL"].strip(), api_key=os.environ["WATSONX_APIKEY"].strip())
        client = APIClient(creds, project_id=os.environ["WATSONX_PROJECT_ID"].strip())
        print("APIClient ok; project_id set:", bool(client.default_project_id))

    # Prefer a model that is actually on the live catalog when any exist.
    # If the project has zero granite-*-instruct IDs, keep PREFERRED
    # (ibm/granite-3-8b-instruct) as the configured target — do not write an
    # enum-only ID that is also unavailable on this Runtime/plan.
    if live:
        chosen = pick(live)
        source = "live"
    else:
        chosen = PREFERRED
        source = "preferred_default"
    print("ModelTypes ∩ preferred available:", [e for e in enums if e == PREFERRED or e in live])
    print("selected_instruct_model:", chosen, f"(source={source})")
    if not live:
        print(
            "NOTE: no ibm/granite-*-instruct IDs on this ca-tor project catalog; "
            f"configured target remains {chosen}. Text generation will fail until "
            "a Granite instruct model is enabled for the Runtime / plan."
        )
    OUT.write_text(chosen + "\n", encoding="utf-8")
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
