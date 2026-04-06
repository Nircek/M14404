"""Database initialisation and lifecycle helpers.

Tortoise ORM models live in the subdomain modules that own them (e.g.
``M14404.subdomains.www``).  This module discovers those subdomain modules
automatically at startup so that any subdomain can define its own models
without needing to register itself here.
"""

import asyncio
import importlib
import inspect
import pkgutil

from tortoise import Tortoise
from tortoise.connection import connections
from tortoise.models import Model

from . import subdomains as subdomains_pkg
from .settings import load_settings

_init_lock = asyncio.Lock()


def _discover_subdomain_model_modules() -> list[str]:
    """Return the fully-qualified module name for every subdomain module that
    defines at least one concrete :class:`~tortoise.models.Model` subclass.

    Only modules with actual models are passed to Tortoise to avoid
    ``RuntimeWarning: Module … has no models`` warnings.
    """
    module_names: list[str] = []
    for module_info in pkgutil.iter_modules(subdomains_pkg.__path__):
        if module_info.name == "__init__":
            continue
        full_name = f"{subdomains_pkg.__name__}.{module_info.name}"
        module = importlib.import_module(full_name)
        has_models = any(
            inspect.isclass(obj) and issubclass(obj, Model) and obj is not Model
            for obj in vars(module).values()
        )
        if has_models:
            module_names.append(full_name)
    return module_names


async def ensure_db_ready() -> None:
    """Initialise the database connection if it has not already been set up.

    Designed to be called from request handlers that run before the app
    lifespan has completed (e.g. during testing).  Uses a lock to prevent
    concurrent initialisations.
    """
    if (
        getattr(Tortoise, "_inited", False)
        and getattr(connections, "_db_config", None) is not None
    ):
        return
    async with _init_lock:
        settings = load_settings()
        await init_db(settings.database_path)


async def init_db(database_path: str) -> None:
    """Initialise Tortoise ORM and create all schema tables.

    Subdomain model modules are discovered automatically so that new subdomains
    can define their own models without modifying this file.
    """
    subdomain_modules = _discover_subdomain_model_modules()
    await Tortoise.init(
        db_url=f"sqlite://{database_path}",
        modules={"models": subdomain_modules},
    )
    await Tortoise.generate_schemas()


async def close_db() -> None:
    """Close all active Tortoise database connections."""
    await Tortoise.close_connections()
