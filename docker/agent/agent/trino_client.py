"""
trino_client.py
---------------
Connects to Trino and executes SQL, returning a pandas DataFrame.

This is the only module that communicates directly with Trino.
GroqAgent calls run_trino_query() and handles the typed exceptions below.
"""

from __future__ import annotations

import logging

import pandas as pd
import trino
from trino.dbapi import connect
from trino.exceptions import TrinoQueryError

from .config import TrinoConfig, get_trino_config

logger = logging.getLogger(__name__)

DEFAULT_REQUEST_TIMEOUT = 30  # seconds per query


class TrinoConnectionError(Exception):
    """Cannot reach the Trino coordinator (wrong host/port, Trino not running, etc.)."""


class TrinoSyntaxError(Exception):
    """SQL has a syntax error or references a non-existent table/column."""


class TrinoTimeoutError(Exception):
    """Query exceeded the allowed time limit."""


def _get_connection(cfg: TrinoConfig | None = None, request_timeout: int = DEFAULT_REQUEST_TIMEOUT):
    cfg = cfg or get_trino_config()
    return connect(
        host=cfg.host,
        port=cfg.port,
        user=cfg.user,
        catalog=cfg.catalog,
        schema=cfg.schema,
        http_scheme="http",
        request_timeout=request_timeout,
    )


def run_trino_query(
    sql: str,
    cfg: TrinoConfig | None = None,
    request_timeout: int = DEFAULT_REQUEST_TIMEOUT,
) -> pd.DataFrame:
    """
    Execute a single SELECT on Trino and return the result as a DataFrame.

    Raises
    ------
    TrinoConnectionError  — cannot reach Trino.
    TrinoTimeoutError     — query exceeded the time limit.
    TrinoSyntaxError      — SQL error, missing table/column, or permission denied.
    """
    try:
        conn = _get_connection(cfg=cfg, request_timeout=request_timeout)
        cur = conn.cursor()
    except Exception as exc:
        raise TrinoConnectionError(
            f"Unable to connect to Trino ({exc.__class__.__name__}): {exc}"
        ) from exc

    try:
        cur.execute(sql)
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description] if cur.description else []
        return pd.DataFrame(rows, columns=columns)
    except TrinoQueryError as exc:
        error_name = getattr(exc, "error_name", "") or ""
        if "TIME_LIMIT" in error_name or ("EXCEEDED" in error_name and "TIME" in error_name):
            raise TrinoTimeoutError(f"Query exceeded Trino time limit: {exc}") from exc
        raise TrinoSyntaxError(f"Trino returned an error executing the query: {exc}") from exc
    except (ConnectionError, OSError, TimeoutError) as exc:
        raise TrinoTimeoutError(f"Connection lost / timeout waiting for Trino result: {exc}") from exc
    except trino.exceptions.HttpError as exc:
        raise TrinoConnectionError(f"HTTP error communicating with Trino: {exc}") from exc
    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass
