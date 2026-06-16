"""
sql_guard.py
------------
Validates Groq-generated SQL before it reaches Trino.

Rules:
1. Strip comments before checking.
2. Single statement only — no ";" mid-query (prevents "SELECT 1; DROP TABLE ...").
3. Must start with SELECT or WITH.
4. Must not contain any dangerous keyword.
"""

from __future__ import annotations

import re

FORBIDDEN_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE",
    "MERGE", "GRANT", "REVOKE", "CALL", "COMMENT", "ATTACH", "DETACH",
    "COPY", "EXECUTE", "REPLACE", "VACUUM", "ANALYZE",
]

_LINE_COMMENT_RE  = re.compile(r"--[^\n]*")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
# Groq occasionally wraps SQL in markdown code fences
_CODE_FENCE_RE    = re.compile(r"^```(?:sql)?\s*|```$", re.IGNORECASE | re.MULTILINE)


class SQLValidationError(Exception):
    """SQL is invalid or unsafe and must not be forwarded to Trino."""


def clean_sql(raw_sql: str) -> str:
    """Remove markdown code fences and trailing semicolons."""
    return _CODE_FENCE_RE.sub("", raw_sql).strip().rstrip(";").strip()


def _strip_comments(sql: str) -> str:
    sql = _BLOCK_COMMENT_RE.sub(" ", sql)
    sql = _LINE_COMMENT_RE.sub(" ", sql)
    return sql


def validate_select_only(raw_sql: str) -> str:
    """
    Assert that raw_sql is a single SELECT/WITH statement with no dangerous
    keywords. Returns cleaned SQL on success; raises SQLValidationError otherwise.
    """
    if not raw_sql or not raw_sql.strip():
        raise SQLValidationError("Empty SQL — nothing to execute.")

    sql            = clean_sql(raw_sql)
    sql_no_comments = _strip_comments(sql)

    if ";" in sql_no_comments:
        raise SQLValidationError(
            "Multiple statements detected (';' found mid-query) — only a single SELECT is allowed."
        )

    if not re.match(r"^\s*(SELECT|WITH)\b", sql_no_comments.strip(), re.IGNORECASE):
        raise SQLValidationError(
            f"SQL must start with SELECT or WITH. Received: {sql_no_comments.strip()[:80]!r}"
        )

    for kw in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{kw}\b", sql_no_comments, re.IGNORECASE):
            raise SQLValidationError(
                f"Forbidden keyword '{kw}' detected. Only read-only SELECT/WITH statements are allowed."
            )

    return sql
