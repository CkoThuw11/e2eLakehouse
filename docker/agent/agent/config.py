"""
config.py
---------
Central configuration for the Groq Agent, read from environment variables.
See .env.example for the full list of supported variables.

Never hardcode secrets in any other module — always go through this module.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class TrinoConfig:
    host: str
    port: int
    user: str
    catalog: str
    schema: str


@dataclass(frozen=True)
class GroqConfig:
    api_key: str
    model: str


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def get_trino_config() -> TrinoConfig:
    return TrinoConfig(
        host=os.getenv("TRINO_HOST", "localhost"),
        port=_get_int("TRINO_PORT", 8090),
        user=os.getenv("TRINO_USER", "groq_agent"),
        catalog=os.getenv("TRINO_CATALOG", "iceberg"),
        schema=os.getenv("TRINO_SCHEMA", "gold"),
    )


def get_groq_config() -> GroqConfig:
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Create a .env file (copy from .env.example) "
            "and add your API key from https://console.groq.com"
        )
    return GroqConfig(
        api_key=api_key,
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
    )
