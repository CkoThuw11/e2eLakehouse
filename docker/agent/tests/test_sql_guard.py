"""
Unit tests for agent/sql_guard.py — runs offline, no Trino or Groq required.

Run: pytest tests/test_sql_guard.py -v
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.sql_guard import SQLValidationError, clean_sql, validate_select_only  # noqa: E402


def test_simple_select_passes():
    sql = "SELECT * FROM iceberg.gold.fact_sales LIMIT 10"
    assert validate_select_only(sql) == sql


def test_with_cte_passes():
    sql = "WITH x AS (SELECT 1) SELECT * FROM x"
    assert validate_select_only(sql) == sql


def test_strips_code_fence_and_trailing_semicolon():
    assert validate_select_only("```sql\nSELECT 1\n```;") == "SELECT 1"


def test_strips_plain_code_fence():
    assert validate_select_only("```\nSELECT 1\n```") == "SELECT 1"


@pytest.mark.parametrize(
    "bad_sql",
    [
        "DROP TABLE iceberg.gold.fact_sales",
        "DELETE FROM iceberg.gold.fact_sales",
        "INSERT INTO iceberg.gold.fact_sales VALUES (1)",
        "UPDATE iceberg.gold.fact_sales SET quantity = 0",
        "CREATE TABLE evil AS SELECT * FROM iceberg.gold.fact_sales",
        "TRUNCATE TABLE iceberg.gold.fact_sales",
        "ALTER TABLE iceberg.gold.fact_sales DROP COLUMN quantity",
        "MERGE INTO iceberg.gold.fact_sales USING x ON true WHEN MATCHED THEN DELETE",
        "GRANT SELECT ON iceberg.gold.fact_sales TO bob",
        "CALL some_procedure()",
    ],
)
def test_forbidden_statements_rejected(bad_sql):
    with pytest.raises(SQLValidationError):
        validate_select_only(bad_sql)


def test_multi_statement_rejected():
    with pytest.raises(SQLValidationError):
        validate_select_only("SELECT 1; DROP TABLE iceberg.gold.fact_sales")


def test_non_select_rejected():
    with pytest.raises(SQLValidationError):
        validate_select_only("EXPLAIN SELECT * FROM iceberg.gold.fact_sales")


def test_empty_sql_rejected():
    with pytest.raises(SQLValidationError):
        validate_select_only("")
    with pytest.raises(SQLValidationError):
        validate_select_only("   ")


def test_column_named_like_keyword_substring_is_ok():
    # "created_at" contains "CREATE" but \b word-boundary prevents a false match
    sql = "SELECT created_at, updated_by FROM iceberg.gold.fact_sales"
    assert validate_select_only(sql) == sql


def test_comment_with_forbidden_word_is_stripped_before_check():
    sql = "SELECT * FROM iceberg.gold.fact_sales -- DROP TABLE later\nLIMIT 5"
    assert validate_select_only(sql).startswith("SELECT")


def test_clean_sql_strips_fence_and_semicolon():
    assert clean_sql("```sql\nSELECT 1;\n```") == "SELECT 1"
    assert clean_sql("  SELECT 1 ;  ") == "SELECT 1"
