"""Floating AI assistant component.

Renders a circular FAB that expands to a fixed-size square chat panel
pinned to the bottom-right corner of the dashboard.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd
import streamlit as st


_AGENT_AVAILABLE = False
_AGENT_IMPORT_ERR: str | None = None
try:
    from agent import GroqAgent                  # type: ignore[import]
    from agent.config import get_groq_config     # type: ignore[import]
    _AGENT_AVAILABLE = True
except ImportError as _e:
    _AGENT_IMPORT_ERR = str(_e)


@st.cache_resource
def _load_agent() -> tuple:
    if not _AGENT_AVAILABLE:
        return None, f"Agent module not found: {_AGENT_IMPORT_ERR}"
    try:
        cfg = get_groq_config()
        return GroqAgent(groq_cfg=cfg), None
    except RuntimeError as exc:
        return None, str(exc)


def _process_question(agent, question: str) -> None:
    st.session_state.chat.append({"role": "user", "content": question})
    try:
        result = agent.ask(question)
        st.session_state.chat.append({
            "role":    "assistant",
            "content": result.answer or "",
            "sql":     result.sql,
            "df":      result.result_df,
            "error":   result.error,
        })
    except Exception as exc:
        st.session_state.chat.append({
            "role": "assistant", "content": "",
            "sql": None, "df": None, "error": f"Agent error: {exc}",
        })


def _render_message(idx: int, msg: dict, agent) -> None:
    avatar = "🧑" if msg["role"] == "user" else "🤖"
    with st.chat_message(msg["role"], avatar=avatar):
        if msg["role"] == "user":
            st.write(msg["content"])
            return

        if msg.get("content"):
            st.markdown(msg["content"])
        if msg.get("error"):
            st.error(msg["error"])
        if msg.get("sql"):
            with st.expander("🔍 View SQL", expanded=False):
                st.code(msg["sql"], language="sql")

        df_msg = msg.get("df")
        if df_msg is not None and isinstance(df_msg, pd.DataFrame) and not df_msg.empty:
            st.dataframe(df_msg.head(20), use_container_width=True, hide_index=True)

        can_suggest = (
            msg.get("sql")
            and df_msg is not None
            and isinstance(df_msg, pd.DataFrame)
            and not df_msg.empty
        )
        if can_suggest:
            if msg.get("strategy"):
                st.markdown("**💡 Business Strategy**")
                st.markdown(msg["strategy"])
            elif st.button("💡 Business Strategy Suggestion", key=f"strat_{idx}"):
                with st.spinner("Generating concise recommendations…"):
                    try:
                        q = st.session_state.chat[idx - 1]["content"] if idx > 0 else ""
                        strategy = agent.suggest_strategy(q, msg["sql"], df_msg)
                        st.session_state.chat[idx]["strategy"] = strategy
                    except Exception as exc:
                        st.session_state.chat[idx]["strategy"] = f"⚠️ Could not generate strategy: {exc}"
                st.rerun()


def render_floating_assistant() -> None:
    """Render either the FAB (closed) or the chat panel (open)."""
    if "ai_open" not in st.session_state:
        st.session_state.ai_open = False
    if "chat" not in st.session_state:
        st.session_state.chat = []
    if "ai_pending" not in st.session_state:
        st.session_state.ai_pending = None

    if not st.session_state.ai_open:
        with st.container(key="ai_fab"):
            if st.button("💬", key="ai_fab_btn", help="Open AI Assistant"):
                st.session_state.ai_open = True
                st.rerun()
        return

    agent, agent_err = _load_agent()

    with st.container(key="ai_chat_panel"):
        # Header: title + clear + minimize. Action columns are sized via CSS so
        # both icon buttons have identical width.
        with st.container(key="ai_header"):
            h_title, h_clear, h_min = st.columns([6, 1, 1])
            with h_title:
                st.markdown("<h4>🤖 AI Assistant</h4>", unsafe_allow_html=True)
            with h_clear:
                if st.button("🗑", key="ai_clear_btn", help="Clear conversation"):
                    st.session_state.chat = []
                    st.session_state.ai_pending = None
                    st.rerun()
            with h_min:
                if st.button("–", key="ai_min_btn", help="Hide chat"):
                    st.session_state.ai_open = False
                    st.rerun()

        if agent_err:
            st.warning(f"AI Assistant unavailable — {agent_err}", icon="⚠️")
            st.caption("Add `GROQ_API_KEY` to `.env`, then rebuild the dashboard.")
            return

        _question_to_ask: Optional[str] = None

        # Sample question chips (only shown when conversation is empty)
        if not st.session_state.chat and not st.session_state.ai_pending:
            st.caption("Try a sample question:")
            SAMPLES = [
                "Top 5 best-selling products?",
                "Monthly revenue for the most recent year?",
                "Which customer has the highest average order value?",
            ]
            for i, q in enumerate(SAMPLES):
                if st.button(q, key=f"sq_{i}", use_container_width=True):
                    _question_to_ask = q

        # Scrollable messages region
        with st.container(key="ai_chat_messages"):
            for idx, msg in enumerate(st.session_state.chat):
                _render_message(idx, msg, agent)

        # Loading spinner sits above the input row so the user sees progress
        # before the next response renders.
        if st.session_state.ai_pending:
            pending_q = st.session_state.ai_pending
            with st.container(key="ai_chat_loading"):
                with st.spinner("Generating SQL and querying Trino…"):
                    _process_question(agent, pending_q)
            st.session_state.ai_pending = None
            st.rerun()

        # Input row pinned at the bottom of the panel (renders last)
        with st.container(key="ai_chat_input"):
            with st.form("ai_chat_form", clear_on_submit=True):
                in_col, send_col = st.columns([5, 1])
                with in_col:
                    user_msg = st.text_input(
                        "Ask anything…",
                        key="ai_chat_input_field",
                        label_visibility="collapsed",
                        placeholder="Ask anything about the Northwind data…",
                    )
                with send_col:
                    submitted = st.form_submit_button("➤", help="Send")
                if submitted and user_msg.strip():
                    _question_to_ask = user_msg.strip()

        if _question_to_ask:
            st.session_state.ai_pending = _question_to_ask
            st.rerun()
