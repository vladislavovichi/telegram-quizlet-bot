from __future__ import annotations

import logging
from typing import List

import httpx

from app.config import settings

log = logging.getLogger(__name__)


async def _request_hint(question: str, prev_hints: List[str]) -> str:
    payload = {
        "question": question,
        "prev_hints": prev_hints,
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(settings.HINT_ENDPOINT, json=payload)
            resp.raise_for_status()
            data = resp.json()
            hint = (data.get("hint") or "").strip()
            return hint
    except Exception as e:
        log.exception("neuralnet request error: %s", e)
        return ""


async def generate_hint_async(question: str, prev_hints: List[str] | None = None) -> str:
    return await _request_hint(question, prev_hints or [])
