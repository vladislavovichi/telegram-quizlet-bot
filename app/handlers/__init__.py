from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
from dataclasses import dataclass
from types import ModuleType
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

from aiogram import Router

log = logging.getLogger(__name__)

_HANDLERS_PKG = __name__ 
_PRIVATE_PREFIXES = ("_",)
_FACTORY_PREFIX = "get_"
_FACTORY_SUFFIX = "_router"


@dataclass(frozen=True)
class _RouterRef:
    source: str
    name: str
    router: Router


def _iter_modules(package: str) -> Iterable[Tuple[str, ModuleType]]:
    pkg = importlib.import_module(package)
    if not hasattr(pkg, "__path__"):
        return []
    for modinfo in pkgutil.iter_modules(pkg.__path__, package + "."):
        mod_name = modinfo.name
        # пропускаем приватные
        if mod_name.rsplit(".", 1)[-1].startswith(_PRIVATE_PREFIXES):
            continue
        try:
            mod = importlib.import_module(mod_name)
        except Exception as e:
            log.exception("handlers: skip module import error: %s (%s)", mod_name, e)
            continue
        yield mod_name, mod


def _module_priority(mod: ModuleType) -> int:
    p = getattr(mod, "PRIORITY", None)
    if isinstance(p, int):
        return p
    return 0


def _sorted_modules(package: str) -> List[Tuple[str, ModuleType]]:
    mods = list(_iter_modules(package))
    mods.sort(key=lambda t: (_module_priority(t[1]), t[0]))
    return mods


def _available_deps(dp: Router, extra_deps: Dict[str, Any]) -> Dict[str, Any]:
    deps: Dict[str, Any] = {}
    if hasattr(dp, "workflow_data"):
        deps.update(dict(dp.workflow_data))
    deps.update(extra_deps or {})
    return deps


def _resolve_factory_call(
    func: Callable[..., Any], deps: Dict[str, Any]
) -> Dict[str, Any]:
    sig = inspect.signature(func)
    call_kwargs: Dict[str, Any] = {}
    missing: List[str] = []

    for name, param in sig.parameters.items():
        if name in deps:
            call_kwargs[name] = deps[name]
        elif param.default is inspect._empty and param.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        ):
            missing.append(name)

    if missing:
        raise TypeError(
            f"Factory {func.__module__}.{func.__name__} requires missing deps: {', '.join(missing)}"
        )
    return call_kwargs


def _collect_module_routers(
    mod: ModuleType, dp: Router, deps: Dict[str, Any]
) -> Tuple[List[_RouterRef], Optional[Callable[..., Any]]]:
    refs: List[_RouterRef] = []

    r = getattr(mod, "router", None)
    if isinstance(r, Router):
        refs.append(_RouterRef(source=mod.__name__, name="router", router=r))

    factories: List[Tuple[int, str, Callable[..., Any]]] = []
    for attr_name, obj in vars(mod).items():
        if not callable(obj):
            continue
        if not attr_name.startswith(_FACTORY_PREFIX) or not attr_name.endswith(
            _FACTORY_SUFFIX
        ):
            continue
        priority = getattr(obj, "priority", 0)
        factories.append((priority, attr_name, obj))

    factories.sort(key=lambda t: (t[0], t[1]))

    for _, fname, factory in factories:
        try:
            call_kwargs = _resolve_factory_call(factory, deps)
            res = factory(**call_kwargs)
            if not isinstance(res, Router):
                if inspect.isawaitable(res):
                    res = dp.loop.run_until_complete(
                        res
                    )
            if not isinstance(res, Router):
                raise TypeError(f"{mod.__name__}.{fname} did not return aiogram.Router")
            refs.append(_RouterRef(source=mod.__name__, name=fname, router=res))
        except Exception as e:
            log.exception("handlers: skip factory %s.%s: %s", mod.__name__, fname, e)
            continue

    setup = getattr(mod, "setup", None)
    if callable(setup):

        def _setup_wrapper() -> None:
            try:
                kwargs = {
                    k: v
                    for k, v in deps.items()
                    if k in inspect.signature(setup).parameters
                }
                setup(dp, **kwargs)
            except Exception as e:
                log.exception("handlers: setup failed in %s: %s", mod.__name__, e)

        return refs, _setup_wrapper

    return refs, None


def _dedupe(routers: List[_RouterRef]) -> List[_RouterRef]:
    seen_keys: Set[Tuple[str, str]] = set()
    seen_ids: Set[int] = set()
    result: List[_RouterRef] = []
    for ref in routers:
        key = (ref.source, ref.name)
        if key in seen_keys:
            continue
        if id(ref.router) in seen_ids:
            continue
        seen_keys.add(key)
        seen_ids.add(id(ref.router))
        result.append(ref)
    return result


def register_handlers(dp: Router, **deps: Any) -> None:
    all_deps = _available_deps(dp, deps)
    all_refs: List[_RouterRef] = []
    setups: List[Callable[[], None]] = []

    for mod_name, mod in _sorted_modules(_HANDLERS_PKG):
        try:
            refs, setup = _collect_module_routers(mod, dp, all_deps)
            if refs:
                log.debug(
                    "handlers: collected %d router(s) from %s", len(refs), mod_name
                )
                all_refs.extend(refs)
            if setup:
                setups.append(setup)
        except Exception as e:
            log.exception("handlers: module processing error: %s (%s)", mod_name, e)
            continue

    all_refs = _dedupe(all_refs)

    for ref in all_refs:
        try:
            dp.include_router(ref.router)
            log.info("handlers: included %s (%s)", ref.name, ref.source)
        except Exception as e:
            log.exception(
                "handlers: include failed for %s.%s: %s", ref.source, ref.name, e
            )

    for s in setups:
        s()

    log.info("handlers: total routers included: %d", len(all_refs))
