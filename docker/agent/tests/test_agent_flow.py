"""
Tests for agent/groq_agent.py — Groq client and run_trino_query are fully mocked
so the suite runs offline (no GROQ_API_KEY or live Trino required).

Run: pytest tests/test_agent_flow.py -v
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.config import GroqConfig  # noqa: E402
from agent.groq_agent import AgentResult, GroqAgent  # noqa: E402
from agent.sql_guard import SQLValidationError  # noqa: E402
from agent.trino_client import TrinoConnectionError, TrinoSyntaxError  # noqa: E402

_GROQ_CFG = GroqConfig(api_key="test-key", model="llama-3.3-70b-versatile")


def _mock_response(text: str) -> MagicMock:
    """Build a minimal mock matching groq.chat.completions.create() return shape."""
    msg = MagicMock()
    msg.content = text
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _mock_client(sql_responses: list[str], answer_text: str = "Sample answer.") -> MagicMock:
    """
    Return a mock Groq client where each generate_sql call returns the next
    item from sql_responses, and the final format_answer call returns answer_text.
    """
    client = MagicMock()
    responses = [_mock_response(s) for s in sql_responses] + [_mock_response(answer_text)]
    client.chat.completions.create.side_effect = responses
    return client


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "product_name":  ["Chai", "Chang", "Aniseed Syrup"],
        "total_revenue": [1000.0, 850.5, 700.25],
    })


def test_ask_success_first_try(sample_df):
    sql = (
        "SELECT product_name, SUM(line_revenue) AS total_revenue "
        "FROM iceberg.gold.fact_sales f "
        "JOIN iceberg.gold.dim_products p ON f.product_key = p.product_key "
        "GROUP BY product_name ORDER BY total_revenue DESC LIMIT 5"
    )
    client = _mock_client([sql], answer_text="Top 5 best-selling products: Chai, Chang, Aniseed Syrup.")

    with patch("agent.groq_agent.run_trino_query", return_value=sample_df) as mock_run:
        result = GroqAgent(groq_cfg=_GROQ_CFG, client=client).ask("Top 5 best-selling products?")

    assert result.ok
    assert result.sql == sql
    assert len(result.attempts) == 1
    mock_run.assert_called_once_with(sql)
    assert result.result_df.equals(sample_df)
    assert "Top 5" in result.answer


def test_ask_retries_after_sql_validation_error(sample_df):
    bad  = "SELECT * FROM iceberg.gold.fact_sales; DROP TABLE iceberg.gold.fact_sales"
    good = "SELECT * FROM iceberg.gold.fact_sales LIMIT 5"
    client = _mock_client([bad, good], answer_text="OK.")

    with patch("agent.groq_agent.run_trino_query", return_value=sample_df) as mock_run:
        result = GroqAgent(groq_cfg=_GROQ_CFG, client=client).ask("Any question", max_sql_retries=1)

    assert result.ok
    assert result.sql == good
    assert result.attempts == [bad, good]
    mock_run.assert_called_once_with(good)


def test_ask_retries_after_trino_syntax_error(sample_df):
    bad  = "SELECT bad_col FROM iceberg.gold.fact_sales"
    good = "SELECT product_name FROM iceberg.gold.dim_products LIMIT 5"
    client = _mock_client([bad, good], answer_text="OK.")

    def side_effect(sql):
        if sql == bad:
            raise TrinoSyntaxError("Column 'bad_col' cannot be resolved")
        return sample_df

    with patch("agent.groq_agent.run_trino_query", side_effect=side_effect) as mock_run:
        result = GroqAgent(groq_cfg=_GROQ_CFG, client=client).ask("Any question", max_sql_retries=1)

    assert result.ok
    assert result.sql == good
    assert mock_run.call_count == 2


def test_ask_fails_after_exhausting_retries():
    bad1 = "SELECT 1; DROP TABLE x"
    bad2 = "DROP TABLE iceberg.gold.fact_sales"
    client = _mock_client([bad1, bad2])

    with patch("agent.groq_agent.run_trino_query") as mock_run:
        result = GroqAgent(groq_cfg=_GROQ_CFG, client=client).ask("Any question", max_sql_retries=1)

    assert not result.ok
    assert "Failed to generate valid SQL" in result.error
    assert len(result.attempts) == 2
    mock_run.assert_not_called()


def test_ask_connection_error_stops_immediately():
    sql = "SELECT * FROM iceberg.gold.fact_sales LIMIT 5"
    client = _mock_client([sql, "never used"])

    with patch("agent.groq_agent.run_trino_query", side_effect=TrinoConnectionError("Trino is down")) as mock_run:
        result = GroqAgent(groq_cfg=_GROQ_CFG, client=client).ask("Any question", max_sql_retries=2)

    assert not result.ok
    assert "Trino is down" in result.error
    assert len(result.attempts) == 1  # no retry — connection errors are not SQL problems
    mock_run.assert_called_once_with(sql)


def test_ask_empty_dataframe_still_formats_answer():
    sql = "SELECT * FROM iceberg.gold.fact_sales WHERE 1 = 0"
    client = _mock_client([sql], answer_text="No data found.")
    empty_df = pd.DataFrame(columns=["order_id"])

    with patch("agent.groq_agent.run_trino_query", return_value=empty_df):
        result = GroqAgent(groq_cfg=_GROQ_CFG, client=client).ask("Question with no data")

    assert result.ok
    assert result.result_df.empty
    assert "No data" in result.answer
