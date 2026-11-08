"""Read-only in-memory cache for ranking, Granite, and playbook artifacts.

Loads once at startup. Never writes back to results/ or data_cache/.
Missing optional files are recorded in ``load_errors`` and left as empty defaults
so the API still boots.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

log = logging.getLogger("server.data_service")

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
CACHE = ROOT / "data_cache"

PRIORITY_BAND = {"P0": "critical", "P1": "high", "P2": "med", "P3": "low"}


class DataService:
    def __init__(self) -> None:
        self.load_errors: list[str] = []
        self.scores: pd.DataFrame = pd.DataFrame()
        self.ranking: pd.DataFrame = pd.DataFrame()
        self.comparison: dict[str, Any] = {}
        self.embed_meta: dict[str, Any] = {}
        self.explanations: dict[str, Any] = {}
        self.playbooks: dict[str, Any] = {}
        self.gemini_explanations: dict[str, Any] = {}
        self.gemini_playbooks: dict[str, Any] = {}
        self.gemini_comparison: dict[str, Any] = {}
        self.gemini_eval: dict[str, Any] = {}
        self.embed_ids: np.ndarray = np.array([], dtype=object)
        self.embed_matrix: np.ndarray | None = None  # (n, 768) float32, L2-normalised when present

    def load(self) -> None:
        self.load_errors.clear()
        self._load_scores()
        self._load_ranking()
        self._load_json(RESULTS / "granite_subset_comparison.json", "comparison")
        self._load_json(CACHE / "granite_embeddings_watsonx_subset.meta.json", "embed_meta")
        self._load_explanations()
        self._load_playbooks()
        self._load_gemini_explanations()
        self._load_gemini_playbooks()
        self._load_json(RESULTS / "gemini_subset_comparison.json", "gemini_comparison")
        self._load_json(RESULTS / "agent_eval_report.json", "gemini_eval")
        self._load_embeddings()
        log.info(
            "DataService ready: ranking=%s scores=%s granite_expl=%s gemini_expl=%s playbooks=%s embeds=%s errors=%s",
            len(self.ranking),
            len(self.scores),
            len(self.explanations),
            len(self.gemini_explanations),
            len(self.playbooks),
            0 if self.embed_matrix is None else len(self.embed_ids),
            len(self.load_errors),
        )

    def _note(self, path: Path, err: Exception | str) -> None:
        msg = f"{path.relative_to(ROOT)}: {err}"
        self.load_errors.append(msg)
        log.warning("optional load skipped: %s", msg)

    def _load_json(self, path: Path, attr: str) -> None:
        if not path.is_file():
            self._note(path, "missing")
            setattr(self, attr, {})
            return
        try:
            setattr(self, attr, json.loads(path.read_text(encoding="utf-8")))
        except Exception as exc:  # noqa: BLE001
            self._note(path, exc)
            setattr(self, attr, {})

    def _load_scores(self) -> None:
        path = RESULTS / "scores_2026.csv"
        if not path.is_file():
            self._note(path, "missing")
            self.scores = pd.DataFrame()
            return
        try:
            df = pd.read_csv(path)
            self.scores = df.copy()  # defensive copy; never mutate source file
        except Exception as exc:  # noqa: BLE001
            self._note(path, exc)
            self.scores = pd.DataFrame()

    def _load_ranking(self) -> None:
        """Prefer top500 order joined to scores metadata; else full scores by rank."""
        top_path = RESULTS / "top500.csv"
        if top_path.is_file() and not self.scores.empty:
            try:
                top = pd.read_csv(top_path)
                if "cve_id" not in top.columns:
                    raise ValueError("top500.csv missing cve_id column")
                # Preserve top500 order; enrich from scores (read-only join on copies).
                ordered = top[["cve_id"]].copy()
                ordered["_ord"] = np.arange(len(ordered))
                merged = ordered.merge(self.scores, on="cve_id", how="left")
                merged = merged.sort_values("_ord").drop(columns=["_ord"])
                if "rank" not in merged.columns or merged["rank"].isna().all():
                    merged["rank"] = np.arange(1, len(merged) + 1)
                self.ranking = merged.reset_index(drop=True)
                return
            except Exception as exc:  # noqa: BLE001
                self._note(top_path, exc)

        if not self.scores.empty:
            df = self.scores.copy()
            if "rank" in df.columns:
                df = df.sort_values("rank")
            self.ranking = df.reset_index(drop=True)
            return

        if top_path.is_file():
            try:
                self.ranking = pd.read_csv(top_path)
            except Exception as exc:  # noqa: BLE001
                self._note(top_path, exc)
                self.ranking = pd.DataFrame()
        else:
            self._note(top_path, "missing (and scores unavailable)")
            self.ranking = pd.DataFrame()

    def _load_explanations(self) -> None:
        path = RESULTS / "granite_explanations_top100.json"
        if not path.is_file():
            self._note(path, "missing")
            self.explanations = {}
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                self.explanations = raw
            elif isinstance(raw, list):
                self.explanations = {
                    str(item.get("cve_id")): item for item in raw if isinstance(item, dict) and item.get("cve_id")
                }
            else:
                self.explanations = {}
        except Exception as exc:  # noqa: BLE001
            self._note(path, exc)
            self.explanations = {}

    def _load_playbooks(self) -> None:
        path = RESULTS / "sample_playbooks.json"
        if not path.is_file():
            self._note(path, "missing")
            self.playbooks = {}
            return
        try:
            self.playbooks = self._as_cve_map(json.loads(path.read_text(encoding="utf-8")))
        except Exception as exc:  # noqa: BLE001
            self._note(path, exc)
            self.playbooks = {}

    def _load_gemini_explanations(self) -> None:
        path = RESULTS / "gemini_explanations_top100.json"
        if not path.is_file():
            self._note(path, "missing")
            self.gemini_explanations = {}
            return
        try:
            self.gemini_explanations = self._as_cve_map(json.loads(path.read_text(encoding="utf-8")))
        except Exception as exc:  # noqa: BLE001
            self._note(path, exc)
            self.gemini_explanations = {}

    def _load_gemini_playbooks(self) -> None:
        path = RESULTS / "cached_playbooks.json"
        if not path.is_file():
            self._note(path, "missing")
            self.gemini_playbooks = {}
            return
        try:
            self.gemini_playbooks = self._as_cve_map(json.loads(path.read_text(encoding="utf-8")))
        except Exception as exc:  # noqa: BLE001
            self._note(path, exc)
            self.gemini_playbooks = {}

    @staticmethod
    def _as_cve_map(raw: Any) -> dict[str, Any]:
        if isinstance(raw, dict):
            if all(isinstance(v, dict) for v in raw.values()):
                return {str(k): v for k, v in raw.items()}
            cid = raw.get("cve_id")
            return {str(cid): raw} if cid else {}
        if isinstance(raw, list):
            return {
                str(item["cve_id"]): item for item in raw if isinstance(item, dict) and item.get("cve_id")
            }
        return {}

    def _load_embeddings(self) -> None:
        path = CACHE / "granite_embeddings_watsonx_subset.parquet"
        if not path.is_file():
            self._note(path, "missing")
            self.embed_ids = np.array([], dtype=object)
            self.embed_matrix = None
            return
        try:
            df = pd.read_parquet(path, columns=["cve_id", "vector"])
            ids = df["cve_id"].astype(str).to_numpy()
            mat = np.stack([np.asarray(v, dtype=np.float32) for v in df["vector"]])
            # Re-normalise defensively for cosine via dot product (does not mutate parquet).
            norms = np.linalg.norm(mat, axis=1, keepdims=True).clip(1e-12)
            mat = mat / norms
            self.embed_ids = ids
            self.embed_matrix = mat
        except Exception as exc:  # noqa: BLE001
            self._note(path, exc)
            self.embed_ids = np.array([], dtype=object)
            self.embed_matrix = None

    def risk_band_counts(self) -> dict[str, int]:
        bands = {"critical": 0, "high": 0, "med": 0, "low": 0}
        src = self.ranking if not self.ranking.empty else self.scores
        if src.empty or "priority" not in src.columns:
            return bands
        for p, n in src["priority"].fillna("").astype(str).value_counts().items():
            band = PRIORITY_BAND.get(p)
            if band:
                bands[band] = int(n)
        return bands

    def cve_record(self, row: pd.Series) -> dict[str, Any]:
        reasons = row.get("reasons")
        if isinstance(reasons, str):
            try:
                reasons = json.loads(reasons)
            except json.JSONDecodeError:
                pass
        return {
            "cve_id": str(row.get("cve_id", "")),
            "rank": _num(row.get("rank")),
            "score": _num(row.get("score")),
            "priority": _str_or_none(row.get("priority")),
            "risk_band": PRIORITY_BAND.get(str(row.get("priority") or ""), None),
            "published": _str_or_none(row.get("published")),
            "snapshot_month": _str_or_none(row.get("snapshot_month")),
            "assigner": _str_or_none(row.get("assigner")),
            "epss": _num(row.get("epss")),
            "any_public_exploit": _num(row.get("any_public_exploit")),
            "in_top500": _num(row.get("in_top500")),
            "reasons": reasons,
        }

    def similar_cves(self, cve_id: str, top_k: int = 5) -> list[dict[str, Any]] | None:
        """Return top_k similar CVEs, or None if embeddings unavailable / id missing."""
        if self.embed_matrix is None or len(self.embed_ids) == 0:
            return None
        matches = np.where(self.embed_ids == cve_id)[0]
        if len(matches) == 0:
            return None
        idx = int(matches[0])
        q = self.embed_matrix[idx]
        sims = self.embed_matrix @ q
        sims[idx] = -1.0  # exclude self
        k = min(top_k, len(sims) - 1)
        if k <= 0:
            return []
        top = np.argpartition(-sims, k)[:k]
        top = top[np.argsort(-sims[top])]
        score_lookup = {}
        if not self.scores.empty and "cve_id" in self.scores.columns:
            score_lookup = self.scores.set_index("cve_id")["score"].to_dict() if "score" in self.scores.columns else {}
        rank_lookup = {}
        if not self.scores.empty and "rank" in self.scores.columns:
            rank_lookup = self.scores.set_index("cve_id")["rank"].to_dict()
        out = []
        for i in top:
            cid = str(self.embed_ids[i])
            out.append(
                {
                    "cve_id": cid,
                    "similarity": float(sims[i]),
                    "score": _num(score_lookup.get(cid)),
                    "rank": _num(rank_lookup.get(cid)),
                }
            )
        return out


def _num(v: Any) -> float | int | None:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    try:
        if isinstance(v, (int, np.integer)):
            return int(v)
        f = float(v)
        if f.is_integer() and abs(f) < 1e15:
            # keep ranks/flags as int when clean
            if isinstance(v, (bool, np.bool_)):
                return int(v)
        return f
    except (TypeError, ValueError):
        return None


def _str_or_none(v: Any) -> str | None:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    s = str(v)
    return s if s and s.lower() != "nan" else None


store = DataService()
