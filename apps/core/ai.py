"""Local DeepSeek integration (on-prem, OpenAI-compatible endpoint).

For data privacy, all AI runs against a **locally hosted** DeepSeek 7B model —
nothing leaves the platform. The endpoint is any OpenAI-compatible server
(Ollama by default: ``http://localhost:11434/v1``; also vLLM, LM Studio, etc.),
configured via ``DEEPSEEK_*`` settings.

Public interface (``is_enabled``, ``summarize_document``, ``draft_client_email``,
``answer_tender_question``, ``draft_tender_description``, ``AIUnavailable``) is
unchanged, so views/tasks/templates need no edits. Every feature degrades
gracefully: with no ``DEEPSEEK_BASE_URL`` configured, ``is_enabled()`` is False.
"""

from __future__ import annotations

import logging
import re

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

# Keep prompts/outputs bounded — this is drafting assistance, not long-form.
_MAX_OUTPUT_TOKENS = 800
_MAX_INPUT_CHARS = 12000
# Reasoning models (deepseek-r1) emit <think>…</think>; strip it from replies.
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


class AIUnavailable(RuntimeError):
    """Raised when the local model is not configured or the call fails."""


def is_enabled() -> bool:
    return bool(getattr(settings, "DEEPSEEK_BASE_URL", ""))


def _chat(prompt: str) -> str:
    if not is_enabled():
        raise AIUnavailable("The local DeepSeek endpoint is not configured.")

    base_url = settings.DEEPSEEK_BASE_URL.rstrip("/")
    headers = {"Content-Type": "application/json"}
    api_key = getattr(settings, "DEEPSEEK_API_KEY", "")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": getattr(settings, "DEEPSEEK_MODEL", "deepseek-r1:7b"),
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant for a UK construction consultancy.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.6,
        "max_tokens": _MAX_OUTPUT_TOKENS,
        "stream": False,
    }

    try:
        response = httpx.post(
            f"{base_url}/chat/completions",
            json=payload,
            headers=headers,
            timeout=getattr(settings, "DEEPSEEK_TIMEOUT", 120),
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, ValueError, IndexError) as exc:
        logger.error("Local DeepSeek call failed", exc_info=True)
        raise AIUnavailable("The local AI service is temporarily unavailable.") from exc

    text = _THINK_RE.sub("", content or "").strip()
    if not text:
        raise AIUnavailable("The local AI service returned an empty response.")
    return text


def summarize_document(filename: str, text: str) -> str:
    excerpt = (text or "").strip()[:_MAX_INPUT_CHARS]
    if not excerpt:
        raise AIUnavailable("No extractable text to summarise.")
    prompt = (
        "Summarise the following tender document in 4-6 concise bullet points a "
        "bid manager can scan: key scope, deadlines, commercial terms, and any "
        f"risks. Use plain text bullets (- ). Document: {filename}\n\n{excerpt}"
    )
    return _chat(prompt)


def draft_client_email(client_name: str, title: str, status_display: str, purpose: str) -> str:
    prompt = (
        "Write a warm, professional email (British English, ~120 words) from London Summit "
        "Consultancy, a London-based UK construction consultancy, to a client. Make them feel "
        "genuinely looked after. Do not invent facts, prices, or dates.\n"
        f"Client: {client_name}\nProject: {title}\nCurrent status: {status_display}\n"
        f"Purpose of the email: {purpose or 'a friendly progress touchpoint'}\n"
        "Return only the email body, no subject line."
    )
    return _chat(prompt)


def answer_tender_question(title: str, context: str, question: str) -> str:
    prompt = (
        "You are a tender assistant. Answer the staff member's question using only "
        "the tender context provided. If the answer isn't in the context, say so.\n"
        f"Tender: {title}\nContext:\n{(context or '')[:_MAX_INPUT_CHARS]}\n\n"
        f"Question: {question}"
    )
    return _chat(prompt)


def draft_tender_description(title: str, client_name: str, sector: str) -> str:
    prompt = (
        "Draft a concise, professional tender opportunity description (British "
        "English, 2-3 short paragraphs) for an internal bid tracker. Neutral, "
        "factual tone. Do not invent specific figures or dates.\n"
        f"Title: {title}\nClient: {client_name}\nSector: {sector}"
    )
    return _chat(prompt)
