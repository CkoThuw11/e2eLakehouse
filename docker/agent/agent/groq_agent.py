"""
groq_agent.py
-------------
GroqAgent: converts a natural-language question into SQL via the Groq API,
validates it, executes it on Trino, and returns a natural-language answer.

Pipeline:
    1. Receive question
    2. generate_sql()              — call Groq → SQL string
    3. validate_select_only()      — allow only SELECT/WITH
    4. run_trino_query()           — execute on Trino → DataFrame
    5. format_answer()             — call Groq → natural-language answer
    6. Return AgentResult
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd
from groq import Groq

from .config import GroqConfig, get_groq_config
from .schema_context import SCHEMA_CONTEXT
from .sql_guard import SQLValidationError, validate_select_only
from .trino_client import (
    TrinoConnectionError,
    TrinoSyntaxError,
    TrinoTimeoutError,
    run_trino_query,
)

logger = logging.getLogger(__name__)

_SQL_SYSTEM_PROMPT = f"""\ You are a Data Analyst specializing in ANSI/Trino SQL (Iceberg connector) for answering revenue and sales questions from the Northwind Data Warehouse. 

{SCHEMA_CONTEXT} RESPONSE RULES (MANDATORY): 
- Return ONLY a single SQL statement (SELECT or WITH ... SELECT). 
- Do NOT explain anything, do NOT add extra text, and do NOT use markdown code fences (do not write ```sql ... ```). Return plain SQL only. 
- The SQL statement must be self-contained (no trailing ';').
 - Use exactly the table/column names described above, prefixed with iceberg.gold.<table>. 
 - If the question asks for "top N", use ORDER BY ... LIMIT N. 
 - If the question compares "last month / this month", determine the periods based on MAX(sale_date) currently available in wide_sales_forecast."""


_ANSWER_SYSTEM_PROMPT = """\ You are a data analysis assistant. You are given: the user's question, the SQL that was executed, and the returned result table. Write a CONCISE and CLEAR answer in ENGLISH based entirely on the result data. Rules: 
- If the result table is empty, clearly say that no matching data was found, and do NOT invent numbers. 
- If the question is about "forecast" / "future", answer according to the FORECAST guidance in the schema context (estimate based on rolling averages). 
- Round decimals to at most 2 digits and format numbers for readability (1,234,567.89). 
- Do not repeat the entire table; mention only the most important figures."""

@dataclass
class AgentResult:
    question: str
    sql: Optional[str] = None
    result_df: Optional[pd.DataFrame] = None
    answer: Optional[str] = None
    error: Optional[str] = None
    attempts: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.error is None


class GroqAgent:
    def __init__(
        self,
        groq_cfg: GroqConfig | None = None,
        client: Groq | None = None,
    ):
        self.cfg    = groq_cfg or get_groq_config()
        self.client = client  or Groq(api_key=self.cfg.api_key)

    def generate_sql(self, question: str, previous_error: Optional[tuple[str, str]] = None) -> str:
        """
        Call Groq to generate SQL from a natural-language question.

        previous_error: (failed_sql, error_message) — passed on retry so the model
        can fix the previously generated SQL.
        """
        messages = [
            {"role": "system", "content": _SQL_SYSTEM_PROMPT},
            {"role": "user",   "content": question},
        ]
        if previous_error is not None:
            failed_sql, error_msg = previous_error
            messages += [
                {"role": "assistant", "content": failed_sql},
                {
                    "role": "user",
                    "content": (
                        "The SQL above failed when executed on Trino:\n"
                        f"{error_msg}\n\n"
                        "Please fix it and return a DIFFERENT single SQL statement "
                        "(SELECT/WITH only, no explanation, no markdown)."
                    ),
                },
            ]

        resp = self.client.chat.completions.create(
            model=self.cfg.model,
            messages=messages,
            temperature=0.0,
        )
        return resp.choices[0].message.content.strip()

    def format_answer(self, question: str, sql: str, df: pd.DataFrame) -> str:
        """Call Groq to produce a natural-language answer from the query result."""
        table_str = "(no rows returned)" if df.empty else df.head(30).to_markdown(index=False)
        user_content = (
            f"Question: {question}\n\n"
            f"Executed SQL:\n{sql}\n\n"
            f"Result ({len(df)} rows):\n{table_str}"
        )
        resp = self.client.chat.completions.create(
            model=self.cfg.model,
            messages=[
                {"role": "system", "content": _ANSWER_SYSTEM_PROMPT},
                {"role": "user",   "content": user_content},
            ],
            temperature=0.2,
        )
        return resp.choices[0].message.content.strip()

    def ask(self, question: str, max_sql_retries: int = 1) -> AgentResult:
        """Run the full pipeline and return an AgentResult."""
        result = AgentResult(question=question)
        previous_error: Optional[tuple[str, str]] = None
        df: Optional[pd.DataFrame]  = None
        validated_sql: Optional[str] = None

        for attempt in range(max_sql_retries + 1):
            try:
                raw_sql = self.generate_sql(question, previous_error=previous_error)
            except Exception as exc:
                result.error = f"Groq API error while generating SQL: {exc}"
                return result

            result.attempts.append(raw_sql)

            try:
                validated_sql = validate_select_only(raw_sql)
                df = run_trino_query(validated_sql)
                break  # success
            except SQLValidationError as exc:
                previous_error = (raw_sql, f"[Invalid SQL] {exc}")
            except TrinoSyntaxError as exc:
                previous_error = (raw_sql, f"[Trino syntax error] {exc}")
            except (TrinoConnectionError, TrinoTimeoutError) as exc:
                # Connection/timeout — retrying the same SQL won't help
                result.sql   = raw_sql
                result.error = str(exc)
                return result

            if attempt == max_sql_retries:
                result.sql   = previous_error[0] if previous_error else None
                result.error = (
                    f"Failed to generate valid SQL after {max_sql_retries + 1} attempt(s). "
                    f"Last error: {previous_error[1]}"
                )
                return result

        result.sql       = validated_sql
        result.result_df = df

        try:
            result.answer = self.format_answer(question, validated_sql, df)
        except Exception as exc:
            result.error = f"Query succeeded but failed to format the answer: {exc}"

        return result
