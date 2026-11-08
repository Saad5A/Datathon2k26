"""IBM Before the Breach — Streamlit triage dashboard for judges."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent

# Baselines from IBM track brief (Recall@500 on KEV additions).
BASELINE_CVSS = 7
BASELINE_EPSS = 6
BASELINE_EXPLOIT_EPSS = 8
TOTAL_MONITORED = 72_670
FOCUS_POOL = 500


st.set_page_config(
    page_title="Before the Breach | Triage SOC",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def inject_soc_styles() -> None:
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');

:root {
  --bg-0: #070b10;
  --bg-1: #0d141c;
  --bg-2: #121c27;
  --line: #1e2d3d;
  --text: #d7e2ec;
  --muted: #7f93a8;
  --accent: #2dd4bf;
  --accent-dim: rgba(45, 212, 191, 0.12);
  --warn: #f59e0b;
  --danger: #f43f5e;
  --ok: #34d399;
}

html, body, [class*="css"] {
  font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
  color: var(--text);
}

.stApp {
  background:
    radial-gradient(1200px 600px at 10% -10%, rgba(45, 212, 191, 0.08), transparent 55%),
    radial-gradient(900px 500px at 100% 0%, rgba(244, 63, 94, 0.06), transparent 50%),
    linear-gradient(180deg, var(--bg-0), #0a1118 40%, var(--bg-0));
  color: var(--text);
}

[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #0a1017, #0d1520);
  border-right: 1px solid var(--line);
}

[data-testid="stSidebar"] * { color: var(--text) !important; }

h1, h2, h3, h4 {
  font-family: "IBM Plex Sans", sans-serif !important;
  letter-spacing: -0.02em;
  color: var(--text) !important;
}

.hero-brand {
  font-family: "IBM Plex Mono", monospace;
  font-size: 0.78rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 0.35rem;
}

.hero-title {
  font-size: 2.1rem;
  font-weight: 700;
  line-height: 1.15;
  margin: 0 0 0.4rem 0;
}

.hero-sub {
  color: var(--muted);
  max-width: 52rem;
  font-size: 0.98rem;
  margin-bottom: 1.2rem;
}

.metric-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.85rem;
  margin: 0.4rem 0 1.4rem 0;
}

.metric {
  background: linear-gradient(160deg, var(--bg-2), var(--bg-1));
  border: 1px solid var(--line);
  border-left: 3px solid var(--accent);
  padding: 0.95rem 1rem;
  min-height: 5.4rem;
}

.metric .label {
  font-family: "IBM Plex Mono", monospace;
  font-size: 0.68rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 0.45rem;
}

.metric .value {
  font-size: 1.55rem;
  font-weight: 700;
  color: var(--text);
  line-height: 1.1;
}

.metric .hint {
  margin-top: 0.35rem;
  font-size: 0.78rem;
  color: var(--muted);
}

.badge {
  display: inline-block;
  font-family: "IBM Plex Mono", monospace;
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.18rem 0.55rem;
  border: 1px solid;
  letter-spacing: 0.04em;
}

.badge-p0 { color: #fecdd3; border-color: #fb7185; background: rgba(244, 63, 94, 0.15); }
.badge-p1 { color: #fde68a; border-color: #fbbf24; background: rgba(245, 158, 11, 0.14); }
.badge-p2 { color: #a7f3d0; border-color: #34d399; background: rgba(52, 211, 153, 0.12); }

.ai-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  font-family: "IBM Plex Mono", monospace;
  font-size: 0.74rem;
  letter-spacing: 0.06em;
  color: var(--accent);
  border: 1px solid rgba(45, 212, 191, 0.45);
  background: var(--accent-dim);
  padding: 0.35rem 0.7rem;
  margin-bottom: 0.9rem;
}

.panel {
  background: linear-gradient(165deg, rgba(18, 28, 39, 0.95), rgba(10, 16, 24, 0.98));
  border: 1px solid var(--line);
  padding: 1rem 1.1rem 1.15rem;
  margin-bottom: 0.85rem;
}

.panel h4 {
  font-family: "IBM Plex Mono", monospace !important;
  font-size: 0.72rem !important;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--accent) !important;
  margin: 0 0 0.55rem 0 !important;
}

.panel p, .panel div.body {
  color: var(--text);
  font-size: 0.95rem;
  line-height: 1.55;
  margin: 0;
  white-space: pre-wrap;
}

div[data-testid="stDataFrame"] {
  border: 1px solid var(--line);
}

.stSelectbox label, .stTextInput label, .stRadio label {
  color: var(--muted) !important;
}

@media (max-width: 1100px) {
  .metric-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
        """,
        unsafe_allow_html=True,
    )


def _safe_str(value, fallback: str) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return fallback
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return fallback
    return text


def _extract_epss(row: pd.Series) -> float | None:
    for col in ("epss", "epss_hist"):
        if col in row.index and pd.notna(row[col]):
            try:
                return float(row[col])
            except (TypeError, ValueError):
                pass
    reasons = row.get("reasons")
    if isinstance(reasons, dict):
        if "epss" in reasons:
            try:
                return float(reasons["epss"])
            except (TypeError, ValueError):
                return None
    text = _safe_str(reasons, "")
    if not text:
        return None
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and "epss" in parsed:
            return float(parsed["epss"])
    except (json.JSONDecodeError, TypeError, ValueError):
        match = re.search(r'"epss"\s*:\s*([0-9.]+)', text)
        if match:
            return float(match.group(1))
    return None


def _load_our_recall() -> str:
    metrics_path = ROOT / "results" / "benchmark_summary.json"
    if metrics_path.exists():
        try:
            data = json.loads(metrics_path.read_text(encoding="utf-8"))
            hits = data.get("recall_at_500") or data.get("our_hits")
            if hits is not None:
                return str(hits)
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    return "Pending"


@st.cache_data(show_spinner=False)
def load_dashboard_frame() -> pd.DataFrame:
    enriched = ROOT / "results" / "top500_enriched.csv"
    if enriched.exists():
        df = pd.read_csv(enriched)
    else:
        scores = pd.read_csv(ROOT / "docs" / "sample_scores_2026.csv")
        display = pd.read_csv(ROOT / "docs" / "sample_cve_display.csv")
        if "in_top500" in scores.columns:
            mask = scores["in_top500"].astype(str).str.lower().isin({"true", "1", "yes"})
            scores = scores.loc[mask]
        df = scores.merge(display, on="cve_id", how="left")

    if "rank" in df.columns:
        df = df.sort_values("rank", ascending=True)
    elif "priority_score" in df.columns:
        df = df.sort_values("priority_score", ascending=False)

    df = df.reset_index(drop=True)
    df["priority"] = df.get("priority", "P2").fillna("P2").astype(str).str.upper()
    df["vendor"] = df.get("vendor", pd.Series(["Unknown"] * len(df))).map(
        lambda v: _safe_str(v, "Unknown")
    )
    df["affected_products"] = df.get("affected_products", pd.Series(["Unknown"] * len(df))).map(
        lambda v: _safe_str(v, "Unknown")
    )
    df["weakness"] = df.get("weakness", df.get("cwe_name", pd.Series(["Unassigned"] * len(df)))).map(
        lambda v: _safe_str(v, "Unassigned")
    )
    df["cvss_score"] = df.get("cvss_score", pd.Series(["Pending Review"] * len(df))).map(
        lambda v: _safe_str(v, "Pending Review")
    )
    df["priority_score"] = pd.to_numeric(df.get("priority_score"), errors="coerce")
    df["epss"] = df.apply(_extract_epss, axis=1)
    df["vendor_product"] = df.apply(
        lambda r: f"{r['vendor']} / {r['affected_products']}"
        if r["affected_products"] not in {"", "Unknown"} and r["affected_products"] != r["vendor"]
        else r["vendor"],
        axis=1,
    )
    return df


def priority_badge(tier: str) -> str:
    tier = str(tier).upper()
    cls = {"P0": "badge-p0", "P1": "badge-p1", "P2": "badge-p2"}.get(tier, "badge-p2")
    return f'<span class="badge {cls}">{tier}</span>'


def render_metrics(df: pd.DataFrame) -> None:
    p0 = int((df["priority"] == "P0").sum())
    our_hits = _load_our_recall()
    st.markdown(
        f"""
<div class="metric-strip">
  <div class="metric">
    <div class="label">Total Vulnerabilities Monitored</div>
    <div class="value">{TOTAL_MONITORED:,}</div>
    <div class="hint">2026 scoreboard universe</div>
  </div>
  <div class="metric">
    <div class="label">Top High-Risk Focus Pool</div>
    <div class="value">{FOCUS_POOL}</div>
    <div class="hint">Ranked submission window</div>
  </div>
  <div class="metric">
    <div class="label">P0 Critical Escalations</div>
    <div class="value">{p0}</div>
    <div class="hint">In current enriched view</div>
  </div>
  <div class="metric">
    <div class="label">Exploits Intercepted (Recall@500)</div>
    <div class="value">{our_hits}</div>
    <div class="hint">Ours vs CVSS {BASELINE_CVSS} · EPSS {BASELINE_EPSS} · Exploit+EPSS {BASELINE_EXPLOIT_EPSS}</div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_playbook(cve_id: str, enriched_df: pd.DataFrame) -> None:
    from src.remediation_agent import get_playbook_for_cve

    with st.spinner(f"Loading triage playbook for {cve_id}…"):
        playbook = get_playbook_for_cve(cve_id, enriched_df)

    tier = _safe_str(playbook.get("priority_tier"), "P2")
    st.markdown(
        f"""
<div class="ai-badge">AI-Generated Triage Plan (Gemini 2.5 Flash) · {priority_badge(tier)} · {cve_id}</div>
        """,
        unsafe_allow_html=True,
    )

    sections = [
        ("Executive Threat Summary", playbook.get("executive_summary")),
        ("Model Prioritization Rationale", playbook.get("triage_explanation")),
        ("Immediate Stopgap Mitigation", playbook.get("immediate_mitigation")),
        ("Patch & Remediation Guidance", playbook.get("patch_guidance")),
    ]
    for title, body in sections:
        text = _safe_str(body, "Unavailable")
        st.markdown(
            f"""
<div class="panel">
  <h4>{title}</h4>
  <div class="body">{text}</div>
</div>
            """,
            unsafe_allow_html=True,
        )


def main() -> None:
    inject_soc_styles()

    st.markdown('<div class="hero-brand">IBM · Before the Breach · Sheridan Datathon 2026</div>', unsafe_allow_html=True)
    st.markdown('<p class="hero-title">Vulnerability Triage SOC</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="hero-sub">Rank the vulnerabilities attackers are most likely to use, '
        "then open a Gemini-grounded remediation playbook — Priority Score and Rank only, "
        "never invented patch versions.</p>",
        unsafe_allow_html=True,
    )

    try:
        df = load_dashboard_frame()
    except FileNotFoundError as exc:
        st.error(f"Could not load dashboard data: {exc}")
        st.stop()

    render_metrics(df)

    with st.sidebar:
        st.markdown("### Filters")
        tier = st.radio("Priority Tier", ["All", "P0", "P1", "P2"], index=0)
        query = st.text_input("Search CVE ID or Vendor", placeholder="e.g. CVE-2026 or acme")
        sort_mode = st.selectbox(
            "Sort by",
            ["Rank (asc)", "Priority Score (desc)"],
            index=0,
        )
        st.caption("Playbooks prefer `results/cached_playbooks.json` for instant judge demos.")

    view = df.copy()
    if tier != "All":
        view = view[view["priority"] == tier]
    if query.strip():
        q = query.strip().lower()
        view = view[
            view["cve_id"].astype(str).str.lower().str.contains(q, na=False)
            | view["vendor"].astype(str).str.lower().str.contains(q, na=False)
            | view["vendor_product"].astype(str).str.lower().str.contains(q, na=False)
        ]

    if sort_mode.startswith("Rank"):
        view = view.sort_values("rank", ascending=True, na_position="last")
    else:
        view = view.sort_values("priority_score", ascending=False, na_position="last")

    table = pd.DataFrame(
        {
            "Rank": view.get("rank"),
            "CVE ID": view["cve_id"],
            "Priority Tier": view["priority"],
            "Priority Score": view["priority_score"].map(
                lambda x: f"{x:.3f}" if pd.notna(x) else "—"
            ),
            "EPSS": view["epss"].map(lambda x: f"{x:.3f}" if pd.notna(x) else "—"),
            "Vendor / Product": view["vendor_product"].map(lambda v: _safe_str(v, "Unknown")),
            "Weakness": view["weakness"].map(lambda v: _safe_str(v, "Unassigned")),
        }
    )

    left, right = st.columns([1.35, 1.0], gap="large")

    with left:
        st.subheader("Ranked focus pool")
        st.caption(f"Showing {len(table):,} of {len(df):,} enriched CVE rows")
        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True,
            height=420,
        )

    with right:
        st.subheader("Gemini triage playbook")
        cve_options = view["cve_id"].astype(str).tolist()
        if not cve_options:
            st.warning("No CVEs match the current filters.")
        else:
            selected = st.selectbox("Select CVE ID", cve_options, index=0)
            # Badge row for selected priority
            sel_row = view[view["cve_id"].astype(str) == selected].iloc[0]
            st.markdown(
                f"{priority_badge(sel_row['priority'])} "
                f"<span style='color:#7f93a8;font-family:IBM Plex Mono,monospace;font-size:0.8rem;margin-left:0.5rem'>"
                f"Priority Score {_safe_str(sel_row.get('priority_score'), '—')} · "
                f"CVSS {_safe_str(sel_row.get('cvss_score'), 'Pending Review')}</span>",
                unsafe_allow_html=True,
            )
            render_playbook(selected, df)


if __name__ == "__main__":
    main()
