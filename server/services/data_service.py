"""Read-only in-memory cache for ranking, Granite, and playbook artifacts.

Loads once at startup. Never writes back to results/ or data_cache/.
Missing optional files are recorded in ``load_errors`` and left as empty defaults
so the API still boots.
"""
from __future__ import annotations

import json
import logging
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

log = logging.getLogger("server.data_service")

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
CACHE = ROOT / "data_cache"

_RANK_WORDS = re.compile(r"\b(rank|priority|P[0-3])\b", re.IGNORECASE)

PRIORITY_BAND = {"P0": "critical", "P1": "high", "P2": "med", "P3": "low"}


def is_live_gemini_record(record: Any) -> bool:
    """Accept only records carrying explicit live-provider provenance.

    Records with ``source_granite`` come from scripts/build_gemini_from_granite.py,
    a Python string template fed by the offline template file (no Gemini call), so
    they are rejected even though they carry ``generation_mode: "live"``.
    """
    if not isinstance(record, dict) or record.get("source_granite"):
        return False
    return (
        str(record.get("provider") or "").strip().lower() == "gemini"
        and bool(record.get("model_id"))
        and record.get("is_ai_generated") is True
        and record.get("generation_mode") == "live"
    )


class DataService:
    def __init__(self) -> None:
        self.load_errors: list[str] = []
        self.scores: pd.DataFrame = pd.DataFrame()
        self.ranking: pd.DataFrame = pd.DataFrame()
        self.comparison: dict[str, Any] = {}
        self.embed_meta: dict[str, Any] = {}
        self.ranking_embed_meta: dict[str, Any] = {}  # full-corpus embeddings behind the G2 text score
        self.explanations_meta: dict[str, Any] = {}
        self.explanations_coverage: dict[str, Any] = {}
        self.explanations: dict[str, Any] = {}
        self.gemini_explanations: dict[str, Any] = {}
        self.gemini_playbooks: dict[str, Any] = {}
        self.gemini_comparison: dict[str, Any] = {}
        self.gemini_eval: dict[str, Any] = {}
        self.embed_ids: np.ndarray = np.array([], dtype=object)
        self.embed_matrix: np.ndarray | None = None  # (n, 768) float32, L2-normalised when present
        self.similar_ids: np.ndarray = np.array([], dtype=object)
        self.similar_matrix: np.ndarray | None = None  # retrieval index (never used for scoring)
        self.similar_meta: dict[str, Any] = {}
        self.scores_by_id: dict[str, dict[str, Any]] = {}
        self.assigner_prior: dict[str, float] = {}
        self.global_prior: float = 0.005

    def load(self) -> None:
        self.load_errors.clear()
        self._load_scores()
        self._build_scoring_index()
        self._load_ranking()
        self._load_json(RESULTS / "granite_subset_comparison.json", "comparison")
        self._load_json(CACHE / "granite_embeddings_watsonx_subset.meta.json", "embed_meta")
        self._load_json(CACHE / "granite_embeddings.meta.json", "ranking_embed_meta")
        self._load_explanations()
        self._load_gemini_explanations()
        self._load_gemini_playbooks()
        self._load_json(RESULTS / "gemini_subset_comparison.json", "gemini_comparison")
        self._load_json(RESULTS / "agent_eval_report.json", "gemini_eval")
        self._load_embeddings()
        self._load_similarity_index()
        log.info(
            "DataService ready: ranking=%s scores=%s granite_expl=%s gemini_expl=%s playbooks=%s embeds=%s similar=%s errors=%s",
            len(self.ranking),
            len(self.scores),
            len(self.explanations),
            len(self.gemini_explanations),
            len(self.gemini_playbooks),
            0 if self.embed_matrix is None else len(self.embed_ids),
            0 if self.similar_matrix is None else len(self.similar_ids),
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
        """Granite instruct summaries (results/granite_summaries_top100.json).

        That file was built on an earlier (pre-G2) ranking, so only the text is served:
        ``summary`` and a ``suggested_action`` that names no rank/priority. Rank, priority
        and reasons always come from scores_2026.csv. Rows whose ``summary_source`` is not
        "granite" are template fallbacks (``is_ai_generated: False``).
        """
        path = RESULTS / "granite_summaries_top100.json"
        self.explanations = {}
        self.explanations_meta = {}
        self.explanations_coverage = {}
        if not path.is_file():
            self._note(path, "missing")
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            meta = raw.get("meta") or {}
            self.explanations_meta = meta
            for row in raw.get("results") or []:
                if not isinstance(row, dict) or not row.get("cve_id"):
                    continue
                is_granite = row.get("summary_source") == "granite"
                action = row.get("suggested_action")
                if action and _RANK_WORDS.search(str(action)):
                    action = None
                self.explanations[str(row["cve_id"])] = {
                    "cve_id": row["cve_id"],
                    "explanation": row.get("summary"),
                    "suggested_action": action,
                    "source": "granite" if is_granite else "template",
                    "provider": "granite" if is_granite else "template",
                    "model_id": (row.get("model_id") or meta.get("model_id")) if is_granite else None,
                    "is_ai_generated": is_granite,
                    "audited": False,
                    "label": ("AI-generated (IBM Granite instruct, run locally), unaudited"
                              if is_granite else "Template (no AI): Granite output failed validation")
                    + "; written for an earlier version of the ranking",
                    "generated_at": row.get("generated_at"),
                }
            top100: set[str] = set()
            if not self.ranking.empty and "cve_id" in self.ranking.columns:
                r = self.ranking.sort_values("rank") if "rank" in self.ranking.columns else self.ranking
                top100 = set(r["cve_id"].astype(str).head(100))
            covered = len(top100 & set(self.explanations))
            self.explanations_coverage = {
                "current_top100_with_summary": covered,
                "current_top100": len(top100),
                "summaries_total": len(self.explanations),
                "note": "Summaries were written for an earlier version of the ranking.",
            }
        except Exception as exc:  # noqa: BLE001
            self._note(path, exc)
            self.explanations = {}

    def _load_gemini_explanations(self) -> None:
        path = RESULTS / "gemini_explanations_top100.json"
        if not path.is_file():
            self._note(path, "missing")
            self.gemini_explanations = {}
            return
        try:
            records = self._as_cve_map(json.loads(path.read_text(encoding="utf-8")))
            self.gemini_explanations = {
                cve_id: record for cve_id, record in records.items() if is_live_gemini_record(record)
            }
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
            records = self._as_cve_map(json.loads(path.read_text(encoding="utf-8")))
            self.gemini_playbooks = {
                cve_id: record for cve_id, record in records.items() if is_live_gemini_record(record)
            }
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

    def _load_similarity_index(self) -> None:
        """Retrieval-only neighbours for the CVE drawer.

        Prefers the local Granite small index (historical pool + 2026 top 500).
        Falls back to the watsonx subset so the endpoint keeps working if the
        new file is not deployed. Never contributes to the ranking score.
        """
        path = CACHE / "granite_embeddings_retrieval.parquet"
        meta_path = CACHE / "granite_embeddings_retrieval.meta.json"
        self.similar_meta = {}
        if not path.is_file():
            self.similar_ids = self.embed_ids
            self.similar_matrix = self.embed_matrix
            if self.embed_matrix is not None:
                self.similar_meta = {"model_id": "ibm/granite-embedding-278m-multilingual", "fallback": True}
            return
        try:
            df = pd.read_parquet(path, columns=["cve_id", "vector"])
            ids = df["cve_id"].astype(str).to_numpy()
            mat = np.stack([np.asarray(v, dtype=np.float32) for v in df["vector"]])
            norms = np.linalg.norm(mat, axis=1, keepdims=True).clip(1e-12)
            self.similar_ids = ids
            self.similar_matrix = mat / norms
            if meta_path.is_file():
                self.similar_meta = json.loads(meta_path.read_text(encoding="utf-8"))
            else:
                self.similar_meta = {"model_id": "ibm-granite/granite-embedding-small-english-r2"}
        except Exception as exc:  # noqa: BLE001
            self._note(path, exc)
            self.similar_ids = self.embed_ids
            self.similar_matrix = self.embed_matrix
            self.similar_meta = {}

    def _build_scoring_index(self) -> None:
        """Index known scoreboard rows and assigner priors for uploaded rows."""
        self.scores_by_id = {}
        self.assigner_prior = {}
        self.global_prior = 0.005
        if self.scores.empty or "cve_id" not in self.scores.columns:
            return
        try:
            df = self.scores.copy()
            df["_cid"] = df["cve_id"].astype(str).str.upper()
            self.scores_by_id = {str(r["_cid"]): r for r in df.to_dict("records")}
            if "assigner" in df.columns and "score" in df.columns:
                priors = df.groupby("assigner")["score"].mean()
                self.assigner_prior = {str(k): float(v) for k, v in priors.items() if pd.notna(v)}
                self.global_prior = float(df["score"].mean()) if len(df) else 0.005
        except Exception as exc:  # noqa: BLE001
            self._note(RESULTS / "scores_2026.csv", exc)
            self.scores_by_id = {}
            self.assigner_prior = {}
            self.global_prior = 0.005

    @staticmethod
    def _as_float(value: Any, default: float | None = None) -> float | None:
        if value is None or value == "":
            return default
        try:
            f = float(value)
            return f if math.isfinite(f) else default
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _as_flag(value: Any) -> int:
        if isinstance(value, bool):
            return 1 if value else 0
        text = str(value or "").strip().lower()
        return 1 if text in {"1", "true", "yes", "y"} else 0

    @staticmethod
    def _parse_reasons(value: Any) -> list[dict[str, Any]]:
        if isinstance(value, list):
            return value
        if isinstance(value, str) and value.strip():
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, list) else []
            except json.JSONDecodeError:
                return []
        return []

    def score_upload(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        """Score an uploaded CVE list without writing to any artifact.

        Known scoreboard CVEs use the audited G2 score and reasons from
        results/scores_2026.csv. Unknown CVEs use a transparent API fallback
        (EPSS, exploit flags, assigner prior, age) and are labelled
        ``api-heuristic-v1``. The frontend ranks the returned rows within the
        upload, exactly as it does for local demo scoring.
        """
        out: list[dict[str, Any]] = []
        known = 0
        heuristic = 0
        now = datetime.now(timezone.utc)
        base = self.global_prior or 0.005
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            cid = str(raw.get("cve_id") or raw.get("cve") or raw.get("id") or "").strip().upper()
            if not cid:
                continue
            existing = self.scores_by_id.get(cid)
            if existing:
                known += 1
                item = {
                    "cve_id": cid,
                    "published": _str_or_none(existing.get("published")),
                    "snapshot_month": _str_or_none(existing.get("snapshot_month")),
                    "assigner": _str_or_none(existing.get("assigner")),
                    "score": _num(existing.get("score")) or 0.0,
                    "epss": _num(existing.get("epss")),
                    "exploitdb": int(_num(existing.get("exploitdb")) or 0),
                    "metasploit": int(_num(existing.get("metasploit")) or 0),
                    "nuclei": int(_num(existing.get("nuclei")) or 0),
                    "poc_github": int(_num(existing.get("poc_github")) or 0),
                    "any_public_exploit": int(_num(existing.get("any_public_exploit")) or 0),
                    "reasons": self._parse_reasons(existing.get("reasons")),
                    "model_version": str(existing.get("model_version") or "G2"),
                }
                out.append(item)
                continue

            heuristic += 1
            assigner = str(raw.get("assigner") or "unknown").strip()
            published = str(raw.get("published") or raw.get("published_date") or "").strip()
            snapshot = str(raw.get("snapshot_month") or (published[:7] if len(published) >= 7 else ""))
            epss = self._as_float(raw.get("epss"))
            if epss is not None:
                epss = min(1.0, max(0.0, epss))
            edb = self._as_flag(raw.get("exploitdb"))
            msf = self._as_flag(raw.get("metasploit"))
            nuc = self._as_flag(raw.get("nuclei"))
            poc = self._as_flag(raw.get("poc_github"))
            any_exploit = self._as_flag(raw.get("any_public_exploit")) if raw.get("any_public_exploit") not in (None, "") else int(bool(edb or msf or nuc or poc))
            age_days = 180.0
            if published:
                try:
                    parsed = datetime.fromisoformat(published.replace("Z", "+00:00"))
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=timezone.utc)
                    age_days = max(0.0, (now - parsed).total_seconds() / 86400.0)
                except ValueError:
                    pass
            prior = float(self.assigner_prior.get(assigner, base))
            terms = [
                ("public_exploit_code", any_exploit, 1.6 * any_exploit),
                ("metasploit_module", msf, 1.3 * msf),
                ("nuclei_template", nuc, 0.9 * nuc),
                ("exploitdb_entry", edb, 0.6 * edb),
                ("poc_github_repos", poc, 0.7 * poc),
                ("epss_score", epss, 0.0 if epss is None else 4.2 * math.sqrt(epss) - 0.4),
                ("assigner_kev_rate", prior, 18.0 * (prior - base)),
                ("days_since_published", round(age_days), 0.35 if age_days < 30 else (-0.4 if age_days > 365 else 0.0)),
            ]
            logit = -5.2 + sum(w for _, _, w in terms)
            score = 1.0 / (1.0 + math.exp(-max(-40.0, min(40.0, logit))))
            total = sum(abs(w) for _, _, w in terms) or 1.0
            reasons = [
                {"signal": signal, "value": round(float(value), 5) if value is not None else None,
                 "impact": round(abs(w) / total, 3), "direction": "up" if w >= 0 else "down"}
                for signal, value, w in sorted(terms, key=lambda t: abs(t[2]), reverse=True)
                if abs(w) > 0.05
            ][:3]
            out.append({
                "cve_id": cid, "published": published or None, "snapshot_month": snapshot or None,
                "assigner": assigner, "score": round(float(score), 6), "epss": epss,
                "exploitdb": edb, "metasploit": msf, "nuclei": nuc, "poc_github": poc,
                "any_public_exploit": any_exploit, "reasons": reasons, "model_version": "api-heuristic-v1",
            })
        return {"rows": out, "known": known, "heuristic": heuristic, "total": len(out)}

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
        """Return top_k similar CVEs, or None if the retrieval index misses the id."""
        if self.similar_matrix is None or len(self.similar_ids) == 0:
            return None
        matches = np.where(self.similar_ids == cve_id)[0]
        if len(matches) == 0:
            return None
        idx = int(matches[0])
        q = self.similar_matrix[idx]
        sims = self.similar_matrix @ q
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
        published_lookup = {}
        if not self.scores.empty and "published" in self.scores.columns:
            published_lookup = self.scores.set_index("cve_id")["published"].to_dict()
        out = []
        for i in top:
            cid = str(self.similar_ids[i])
            out.append(
                {
                    "cve_id": cid,
                    "similarity": float(sims[i]),
                    "score": _num(score_lookup.get(cid)),
                    "rank": _num(rank_lookup.get(cid)),
                    "published": _str_or_none(published_lookup.get(cid)),
                    # A retrieved historical CVE has no 2026 score; say so explicitly.
                    "scope": "2026 queue" if cid in score_lookup else "historical pool",
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
