from __future__ import annotations

import importlib
import inspect
import logging
from typing import Any, Dict, Optional

from aiogram import Router

log = logging.getLogger(__name__)
__all__ = ["register_handlers"]


def _try_import(name: str):
    try:
        module = importlib.import_module(f".{name}", package=__name__)
        log.info("Imported handlers.%s (relative)", name)
        return module
    except Exception as e_rel:
        log.debug("Relative import handlers.%s failed: %s", name, e_rel)

    try:
        module = importlib.import_module(f"app.handlers.{name}")
        log.info("Imported handlers.%s (absolute)", name)
        return module
    except Exception as e_abs:
        log.exception("Failed to import handlers.%s: %s", name, e_abs)
        return None


_user_mod = _try_import("user")


def _filter_kwargs_for_callable(
    callable_obj: Any, deps: Dict[str, Any]
) -> Dict[str, Any]:
    try:
        sig = inspect.signature(callable_obj)
    except (ValueError, TypeError):
        return {}
    names = [
        n
        for n, p in sig.parameters.items()
        if p.kind
        in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    ]
    return {k: v for k, v in deps.items() if k in names}


def _resolve_router(obj: Any, deps: Dict[str, Any]) -> Router:
    if isinstance(obj, Router):
        return obj

    if isinstance(obj, type) and issubclass(obj, Router):
        return obj()

    if callable(obj):
        kw = _filter_kwargs_for_callable(obj, deps)
        try:
            r = obj(**kw)
            if isinstance(r, Router):
                return r
            raise TypeError(f"Router factory returned non-Router: {r!r}")
        except TypeError as e_kw:
            log.debug("Keyword call failed for %r with %r: %s", obj, kw, e_kw)

        try:
            sig = inspect.signature(obj)
            args = []
            missing = []
            for name, param in sig.parameters.items():
                if param.kind in (
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                ):
                    if name in deps:
                        args.append(deps[name])
                    elif param.default is inspect._empty:
                        missing.append(name)
            if missing:
                raise TypeError(f"Missing required positional deps: {missing}")
            r = obj(*args)
            if isinstance(r, Router):
                return r
            raise TypeError(f"Router factory returned non-Router (positional): {r!r}")
        except TypeError as e_pos:
            raise TypeError(
                f"Callable router factory is not compatible: {e_pos}"
            ) from e_pos

    raise TypeError(
        f"router should be Router or a factory returning Router, got {obj!r}"
    )


def register_handlers(
    dp: Router,
    async_session_maker,
    redis=None,
    admin_ids: Optional[list] = None,
    engine=None,
):
    if admin_ids is None:
        admin_ids = []

    deps: Dict[str, Any] = {
        "async_session_maker": async_session_maker,
        "redis": redis,
        "admin_ids": admin_ids,
        "engine": engine,
    }

    modules = [
        (_user_mod, ("get_user_router", "router", "UserRouter")),
    ]

    for module, names in modules:
        if module is None:
            continue
        resolved = False
        for name in names:
            if hasattr(module, name):
                candidate = getattr(module, name)
                try:
                    router = _resolve_router(candidate, deps)
                    dp.include_router(router)
                    log.info(
                        "Included router from %s: attribute=%s", module.__name__, name
                    )
                    resolved = True
                    break
                except Exception as e:
                    log.exception(
                        "Failed to include router from %s.%s: %s",
                        module.__name__,
                        name,
                        e,
                    )
        if not resolved:
            log.warning(
                "No usable router found in module %s (checked %s)",
                module.__name__,
                names,
            )
