import os
from dataclasses import dataclass


@dataclass
class Settings:
    debug: bool
    database_path: str
    origin_domain_name: str


def get_environment() -> str:
    return os.getenv("M14404_ENV") or os.getenv("APP_ENV") or "dev"


def load_settings() -> Settings:
    env = get_environment()

    origin_domain_name = (os.getenv("M14404_ORIGIN_DOMAIN_NAME") or "").strip()

    if env == "test":
        db_path: str = (
            os.getenv("M14404_DB_PATH") or os.getenv("APP_DB_PATH") or ":memory:"
        )
        debug = False
    elif env == "prod":
        db_path = (
            os.getenv("M14404_DB_PATH")
            or os.getenv("APP_DB_PATH")
            or "/var/lib/asgi-server/M14404.db"
        )
        debug = False
    elif env == "dev":
        db_path = (
            os.getenv("M14404_DB_PATH") or os.getenv("APP_DB_PATH") or "./M14404.db"
        )
        debug = True
    else:
        raise ValueError(f"Unknown environment: {env}")

    return Settings(
        debug=debug, database_path=db_path, origin_domain_name=origin_domain_name
    )
