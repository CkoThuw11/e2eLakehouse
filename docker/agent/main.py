"""
main.py
-------
Entrypoint for the Groq Agent (Task 11 — feature/groq-agent).

Usage:
    cd docker/agent
    pip install -r requirements.txt
    cp .env.example .env          # fill in GROQ_API_KEY
    python main.py                # run 5 sample questions
    python main.py --interactive  # free-form mode, type "exit"/"quit" to stop
    python main.py -q "..."       # run a single question and exit
"""

from __future__ import annotations

import argparse
import logging
import sys

import pandas as pd

from agent import AgentResult, GroqAgent
from agent.config import get_groq_config

logging.basicConfig(level=logging.WARNING, format="%(levelname)s | %(name)s | %(message)s")

# 5 sample questions for the Task 11 demo
SAMPLE_QUESTIONS = [
    "What are the top 5 best-selling products last month?",
    "What is the monthly revenue for the most recent year with data?",
    "Which customer has the highest average order value?",
    "Which product category had the strongest growth compared to the previous month?",
    "Is the revenue trend over the last 30 days increasing or decreasing, "
    "and what is a rough projection for the next 30 days based on that trend?",
]


def _print_result(idx: int, result: AgentResult) -> None:
    print("=" * 80)
    print(f"[{idx}] Question: {result.question}")
    print("-" * 80)

    for i, sql_attempt in enumerate(result.attempts, start=1):
        label = "SQL" if len(result.attempts) == 1 else f"SQL (attempt {i})"
        print(f"{label}:\n{sql_attempt}\n")

    if not result.ok:
        print(f"ERROR: {result.error}")
        return

    df = result.result_df
    if df is not None:
        print(f"Result ({len(df)} row(s)):")
        if df.empty:
            print("(no rows)")
        else:
            with pd.option_context("display.max_columns", None, "display.width", 200):
                print(df.head(10).to_string(index=False))

    print("-" * 80)
    print(f"Answer:\n{result.answer}")


def run_sample_questions(agent: GroqAgent) -> int:
    """Run all SAMPLE_QUESTIONS, print results, return the number of successes."""
    success = 0
    for idx, question in enumerate(SAMPLE_QUESTIONS, start=1):
        result = agent.ask(question)
        _print_result(idx, result)
        print()
        if result.ok:
            success += 1

    print("=" * 80)
    print(f"SUMMARY: {success}/{len(SAMPLE_QUESTIONS)} questions answered successfully.")
    return success


def run_interactive(agent: GroqAgent) -> None:
    print("Groq Agent — Northwind Gold Layer. Type 'exit' or 'quit' to stop.\n")
    idx = 1
    while True:
        try:
            question = input("Your question > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not question:
            continue
        if question.lower() in {"exit", "quit"}:
            break
        _print_result(idx, agent.ask(question))
        print()
        idx += 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Groq Agent — text-to-SQL for the Northwind Gold layer (Trino)."
    )
    parser.add_argument("--interactive", action="store_true", help="Run in free-form interactive mode.")
    parser.add_argument("--question", "-q", help="Run a single question and exit.")
    args = parser.parse_args()

    try:
        get_groq_config()
    except RuntimeError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    agent = GroqAgent()

    if args.question:
        result = agent.ask(args.question)
        _print_result(1, result)
        return 0 if result.ok else 1

    if args.interactive:
        run_interactive(agent)
        return 0

    return 0 if run_sample_questions(agent) >= 4 else 1


if __name__ == "__main__":
    raise SystemExit(main())
