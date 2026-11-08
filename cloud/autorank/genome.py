"""Genome definition, mutation and crossover for AutoRank Lab."""
from __future__ import annotations

import hashlib
import json
import random

from .config import FEATURE_GROUPS, MODEL_SPACE, POSTPROCESS
from .models import available_models


def random_genome(rng: random.Random, available_groups: list[str]) -> dict:
    base = ["signals"]
    optional = [g for g in available_groups if g not in base]
    # Always allow a compact model; sample 1-3 optional groups.
    k = rng.randint(0, min(3, len(optional)))
    groups = base + rng.sample(optional, k) if optional else base
    family = rng.choice(available_models())
    params = {k: rng.choice(v) for k, v in MODEL_SPACE[family].items()}
    post = {
        "cap": rng.choice(POSTPROCESS["cap"]),
        "month_allocation": rng.choice(POSTPROCESS["month_allocation"]),
        "flag_quota": rng.choice(POSTPROCESS["flag_quota"]),
        "seed_average": 1,
    }
    return {"features": groups, "model": family, "params": params, "postprocess": post}


def _mutate_params(rng: random.Random, family: str, params: dict) -> dict:
    space = MODEL_SPACE[family]
    out = dict(params)
    keys = list(space)
    for key in rng.sample(keys, k=min(len(keys), rng.randint(1, 2))):
        out[key] = rng.choice(space[key])
    return out


def mutate(genome: dict, rng: random.Random, available_groups: list[str]) -> dict:
    out = json.loads(json.dumps(genome))
    choice = rng.choice(["features", "model", "params", "postprocess"])
    if choice == "features":
        base = ["signals"]
        optional = [g for g in available_groups if g not in base]
        out["features"] = base + rng.sample(optional, rng.randint(0, min(3, len(optional))))
    elif choice == "model":
        out["model"] = rng.choice(available_models())
        out["params"] = {k: rng.choice(v) for k, v in MODEL_SPACE[out["model"]].items()}
    elif choice == "params":
        out["params"] = _mutate_params(rng, out["model"], out.get("params", {}))
    else:
        out["postprocess"]["cap"] = rng.choice(POSTPROCESS["cap"])
        out["postprocess"]["month_allocation"] = rng.choice(POSTPROCESS["month_allocation"])
        out["postprocess"]["flag_quota"] = rng.choice(POSTPROCESS["flag_quota"])
    return out


def crossover(a: dict, b: dict, rng: random.Random) -> dict:
    out = json.loads(json.dumps(a))
    # feature union/intersection mix
    fa, fb = set(a["features"]), set(b["features"])
    if rng.random() < 0.5:
        out["features"] = sorted(fa | fb)
    else:
        out["features"] = sorted(fa & fb) or sorted(fa)
    if "signals" not in out["features"]:
        out["features"].insert(0, "signals")
    if rng.random() < 0.5:
        out["model"] = b["model"]
        out["params"] = json.loads(json.dumps(b["params"]))
    if rng.random() < 0.5:
        out["postprocess"] = json.loads(json.dumps(b["postprocess"]))
    return out


def key(genome: dict) -> str:
    blob = json.dumps(genome, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(blob.encode()).hexdigest()[:16]


def describe(genome: dict) -> str:
    p = genome["postprocess"]
    return (
        f"{genome['model']}({genome['params']}) "
        f"features={','.join(genome['features'])} "
        f"cap={p['cap']} month={p['month_allocation']} flagq={p['flag_quota']} seeds={p['seed_average']}"
    )
