"""Subdomain resolver.

Maps an incoming ``Host`` header to the correct :class:`~M14404.base_subdomain.BaseSubdomainHandler`
subclass.  Handler discovery is automatic: every module inside
:mod:`M14404.subdomains` that exposes a :class:`~M14404.base_subdomain.BaseSubdomainHandler`
subclass is registered by its ``subdomain_key`` class attribute.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from functools import lru_cache
from typing import Dict, Optional, Type

from .base_subdomain import BaseSubdomainHandler
from . import subdomains as subdomains_pkg


def _normalize_host(host: str) -> str:
    normalized_host = (host or "").strip().lower()
    if not normalized_host:
        return ""
    if ":" in normalized_host:
        normalized_host = normalized_host.split(":", 1)[0]
    return normalized_host


def _resolve_subdomain_key(*, host: str, origin_domain_name: str) -> Optional[str]:
    origin = _normalize_host(origin_domain_name)
    normalized_host = _normalize_host(host)
    if not origin or not normalized_host:
        return None

    if normalized_host == origin:
        return "_"
    if normalized_host == f"www.{origin}":
        return "www"
    if normalized_host.endswith(f".{origin}"):
        return normalized_host[: -(len(origin) + 1)]
    return None


@lru_cache(maxsize=1)
def _discover_handlers() -> Dict[str, Type[BaseSubdomainHandler]]:
    """Walk :mod:`M14404.subdomains` and collect all handler classes, keyed by ``subdomain_key``.

    Result is cached after the first call so discovery runs only once per
    process lifetime.
    """
    handlers: Dict[str, Type[BaseSubdomainHandler]] = {}
    for module_info in pkgutil.iter_modules(subdomains_pkg.__path__):
        if module_info.name in {"__init__"}:
            continue
        module = importlib.import_module(
            f"{subdomains_pkg.__name__}.{module_info.name}"
        )
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if not issubclass(obj, BaseSubdomainHandler) or obj is BaseSubdomainHandler:
                continue
            key = getattr(obj, "subdomain_key", "") or module_info.name
            handlers[key] = obj
    return handlers


def resolve_handler(
    *, host: str, origin_domain_name: str
) -> Optional[BaseSubdomainHandler]:
    """Return an instantiated handler for *host*, or ``None`` if none is found."""
    subdomain_key = _resolve_subdomain_key(
        host=host, origin_domain_name=origin_domain_name
    )
    if not subdomain_key:
        return None
    handler_cls = _discover_handlers().get(subdomain_key)
    if not handler_cls:
        return None
    return handler_cls(origin_domain_name=_normalize_host(origin_domain_name))
