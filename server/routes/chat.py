"""Live Gemini 2.5 Flash Q&A — no keyword mocks or canned templates.

POST /api/gemini/chat
POST /api/chat  (compat)
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_ROOT / ".env")
load_dotenv()

router = APIRouter(tags=["chat"])

SYSTEM_INSTRUCTION = """You are the technical AI assistant for the PancakeSec cybersecurity platform.
Answer the user's questions directly, accurately, and naturally.

GUIDELINES:
- For general cybersecurity terms or operational questions (e.g. "full form of WAF?", "what if we can't patch on tuesday?"), answer directly (e.g. "WAF stands for Web Application Firewall...").
- For CVE questions, you are given only the active CVE ID. Do not invent products, versions, patch URLs or statistics; say what you do not know.
- You cannot see this project's data, results or metrics. If asked for the project's numbers (AUC, hits, counts), say you do not have them and point to the Evidence page (/results). Never guess a statistic.
- Keep responses concise, helpful, and professional (under 60 words for quick definitions, under 100 words for risk guidance).
- Do NOT repeat the user's question, do NOT echo keywords in parentheses like '(asked about: ...)', and do NOT output static canned templates.
"""


class ChatMessage(BaseModel):
    role: str
    content: str = ""
    text: Optional[str] = None


class ChatRequest(BaseModel):
    question: Optional[str] = Field(default=None, max_length=4000)
    message: Optional[str] = Field(default=None, max_length=4000)
    active_cve: Optional[str] = "CVE-2026-10523"
    cve_id: Optional[str] = None
    history: Optional[list[ChatMessage]] = None


def _question(req: ChatRequest) -> str:
    return (req.question or req.message or "").strip()


def _active_cve(req: ChatRequest) -> str:
    return (req.active_cve or req.cve_id or "CVE-2026-10523").strip() or "CVE-2026-10523"


def _history_rows(req: ChatRequest) -> list[ChatMessage]:
    rows: list[ChatMessage] = []
    for msg in req.history or []:
        content = (msg.content or msg.text or "").strip()
        if not content:
            continue
        low = content.lower()
        if low.startswith("analyzing project data"):
            continue
        if "project assistant initialized" in low:
            continue
        rows.append(ChatMessage(role=msg.role, content=content))
    return rows


@router.post("/api/gemini/chat")
async def chat_endpoint(req: ChatRequest) -> dict[str, Any]:
    question = _question(req)
    if not question:
        raise HTTPException(status_code=400, detail="question is required")

    api_key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    if not api_key or any(p in api_key.lower() for p in ("placeholder", "changeme", "your_", "xxx", "todo")):
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY is not set in the server environment.",
        )

    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"google-genai is not installed ({exc}). Run: pip install google-genai",
        ) from exc

    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(api_version="v1beta"),
    )

    contents: list[dict[str, Any]] = []
    for msg in _history_rows(req)[-4:]:
        role = "user" if msg.role.lower() in ("user", "judge", "human") else "model"
        contents.append({"role": role, "parts": [{"text": msg.content}]})

    prompt = (
        f"{SYSTEM_INSTRUCTION}\n\n"
        f"[Active Context: {_active_cve(req)}]\n"
        f"User question: {question}"
    )
    contents.append({"role": "user", "parts": [{"text": prompt}]})

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=160,
            ),
        )
        answer = (getattr(response, "text", None) or "").strip()
        if not answer:
            raise HTTPException(status_code=500, detail="Gemini returned an empty response.")
        return {
            "answer": answer,
            "reply": answer,
            "provider": "GEMINI",
            "model_id": "gemini-2.5-flash",
            "source": "live",
            "cached": False,
            "is_ai_generated": True,
            "label": "AI-generated (Google Gemini), unaudited",
        }
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Gemini API error: {e}") from e


@router.post("/api/chat")
async def chat_alias(req: ChatRequest) -> dict[str, Any]:
    return await chat_endpoint(req)
