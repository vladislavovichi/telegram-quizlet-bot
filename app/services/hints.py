from __future__ import annotations

import asyncio
import logging
from typing import Callable, List

log = logging.getLogger(__name__)

_func: Callable[..., str] | None = None
try:
    import importlib

    mdl = importlib.import_module("neuralnet")
    for name in ("generate_hint", "make_hint", "infer", "generate"):
        f = getattr(mdl, name, None)
        if callable(f):
            _func = f
            break
    if _func is None and hasattr(mdl, "ask"):
        _func = getattr(mdl, "ask")
except Exception as e:
    log.warning("model.py is not available or failed to import: %s", e)
    _func = None


async def generate_hint_async(
    question: str, prev_hints: List[str] | None = None
) -> str:
    prev_hints = prev_hints or []
    if _func is None:
        return "Подсказки выключены: не найдена функция генерации в model.py"

    def _call():
        try:
            if _func.__code__.co_argcount >= 2:
                return _func(question, prev_hints)
            if _func.__code__.co_argcount == 1:
                return _func(question)

            return _func(
                [
                    {
                        "role": "user",
                        "content": f"Дай краткую подсказку к вопросу: {question}",
                    }
                ]
            )
        except Exception as e:
            log.exception("hint generation error: %s", e)
            return ""

    return await asyncio.to_thread(_call)
