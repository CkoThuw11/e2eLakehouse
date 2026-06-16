"""
Northwind Lakehouse — Analytics Dashboard
Streamlit app | iceberg.gold via Trino
Tabs: Revenue · Products & Customers · Forecast · AI Assistant
"""
from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from trino.dbapi import connect

# ── Page config (must be first Streamlit call) ─────────────────────────────────
st.set_page_config(
    page_title="Northwind Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Colour palette ─────────────────────────────────────────────────────────────
_BLUE    = "#2563EB"
_ORANGE  = "#F59E0B"
_GREEN   = "#10B981"
_PURPLE  = "#8B5CF6"
_TEAL    = "#0891B2"
_PALETTE = [_BLUE, _ORANGE, _GREEN, _PURPLE, "#EF4444", _TEAL]

_CHART_BASE = dict(
    template="plotly_white",
    font=dict(family="Inter, Segoe UI, sans-serif", size=12, color="#374151"),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
)

# ── Global CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

/* Hide sidebar and its toggle button entirely */
section[data-testid="stSidebar"]  { display: none !important; }
[data-testid="collapsedControl"]   { display: none !important; }

/* ── Top filter bar ── */
.filter-bar {
    background: #f8fafc;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 0.9rem 1.25rem;
    margin-bottom: 1.25rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

/* ── KPI cards ── */
.kpi-card {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 1.3rem 1.5rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    height: 100%;
}
.kpi-label {
    font-size: 0.68rem;
    font-weight: 700;
    color: #9ca3af;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin: 0 0 0.4rem;
}
.kpi-value {
    font-size: 2rem;
    font-weight: 800;
    color: #111827;
    margin: 0;
    line-height: 1;
}

/* ── Section headings ── */
.sh {
    font-size: 0.72rem;
    font-weight: 700;
    color: #9ca3af;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin: 0 0 0.8rem;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: #f3f4f6;
    border-radius: 10px;
    padding: 3px;
    gap: 2px;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px;
    font-weight: 500;
    color: #6b7280;
    font-size: 0.88rem;
    padding: 0.45rem 1.1rem;
}
.stTabs [aria-selected="true"] {
    background: #ffffff !important;
    color: #111827 !important;
    box-shadow: 0 1px 5px rgba(0,0,0,0.1);
}
.stTabs [data-baseweb="tab-border"] { display: none; }

/* ── Sample question chips ── */
div[data-testid="column"] .stButton > button {
    border-radius: 8px;
    border: 1px solid #e5e7eb;
    background: #f9fafb;
    color: #374151;
    font-size: 0.82rem;
    text-align: left;
    white-space: normal;
    height: auto;
    padding: 0.55rem 0.85rem;
    transition: all 0.15s ease;
    width: 100%;
}
div[data-testid="column"] .stButton > button:hover {
    background: #eff6ff;
    border-color: #93c5fd;
    color: #1d4ed8;
}
</style>
""", unsafe_allow_html=True)

# ── Agent bootstrap ────────────────────────────────────────────────────────────
_AGENT_AVAILABLE = False
_AGENT_IMPORT_ERR: str | None = None
try:
    from agent import AgentResult, GroqAgent       # type: ignore[import]
    from agent.config import get_groq_config       # type: ignore[import]
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


# ── Trino helpers ──────────────────────────────────────────────────────────────
_T_HOST = os.getenv("TRINO_HOST", "localhost")
_T_PORT = int(os.getenv("TRINO_PORT", "8090"))
_T_USER = os.getenv("TRINO_USER", "streamlit_dashboard")


@st.cache_data(ttl=3600, show_spinner=False)
def run_query(sql: str) -> pd.DataFrame:
    conn = connect(
        host=_T_HOST, port=_T_PORT, user=_T_USER,
        catalog="iceberg", schema="gold",
        http_scheme="http", request_timeout=60,
    )
    try:
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        cols = [d[0] for d in (cur.description or [])]
        return pd.DataFrame(rows, columns=cols)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def qry(sql: str, msg: str = "Loading…") -> Optional[pd.DataFrame]:
    try:
        with st.spinner(msg):
            return run_query(sql)
    except Exception as exc:
        st.error(f"Query error: {exc}")
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def date_bounds() -> tuple[date, date]:
    try:
        df = run_query(
            "SELECT MIN(sale_date) mn, MAX(sale_date) mx "
            "FROM iceberg.gold.wide_sales_forecast WHERE total_revenue > 0"
        )
        if df.empty:
            raise ValueError
        mn, mx = df["mn"].iloc[0], df["mx"].iloc[0]
        mn = mn.date() if hasattr(mn, "date") else mn
        mx = mx.date() if hasattr(mx, "date") else mx
        return date(mn.year, mn.month, mn.day), date(mx.year, mx.month, mx.day)
    except Exception:
        return date(1996, 7, 4), date(1998, 5, 6)


# ── UI helpers ─────────────────────────────────────────────────────────────────
def kpi(label: str, value: str) -> None:
    st.markdown(
        f'<div class="kpi-card">'
        f'<p class="kpi-label">{label}</p>'
        f'<p class="kpi-value">{value}</p>'
        f'</div>',
        unsafe_allow_html=True,
    )


def sh(text: str) -> None:
    st.markdown(f'<p class="sh">{text}</p>', unsafe_allow_html=True)


def fig_style(fig: go.Figure, height: int = 320, legend: bool = False) -> go.Figure:
    fig.update_layout(
        **_CHART_BASE,
        height=height,
        margin=dict(t=15, b=15, l=0, r=5),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_xaxes(showgrid=False, linecolor="#e5e7eb", tickfont=dict(size=11))
    fig.update_yaxes(showgrid=True, gridcolor="#f3f4f6", linecolor="rgba(0,0,0,0)", tickfont=dict(size=11))
    return fig


def render_agent_reply(result) -> None:
    """Render an AgentResult inside an active st.chat_message block."""
    # Answer — shown in full
    if result.ok and result.answer:
        st.markdown(result.answer)
    if result.error:
        st.error(result.error)
    # SQL — collapsed button, user opens if they want to inspect
    if result.sql:
        with st.expander("🔍 View SQL", expanded=False):
            st.code(result.sql, language="sql")
    # Data — shown directly, no extra click needed
    df = result.result_df
    if df is not None and isinstance(df, pd.DataFrame) and not df.empty:
        st.dataframe(df.head(20), use_container_width=True, hide_index=True)


# ── Page header + inline date filter ──────────────────────────────────────────
with st.spinner(""):
    min_d, max_d = date_bounds()

title_col, gap_col, filter_col = st.columns([5, 1, 3])

with title_col:
    st.markdown(
        '<h1 style="font-size:1.6rem;font-weight:800;color:#111827;margin:0.4rem 0 0">'
        '📊 Northwind Analytics Dashboard</h1>',
        unsafe_allow_html=True,
    )

with filter_col:
    dr = st.date_input(
        "Date range",
        value=(min_d, max_d),
        min_value=min_d,
        max_value=max_d,
        format="YYYY-MM-DD",
        label_visibility="collapsed",
    )

if isinstance(dr, (list, tuple)) and len(dr) == 2:
    start_d, end_d = dr[0], dr[1]
elif isinstance(dr, (list, tuple)) and len(dr) == 1:
    start_d, end_d = dr[0], max_d
else:
    start_d, end_d = min_d, max_d

sd = start_d.strftime("%Y-%m-%d")
ed = end_d.strftime("%Y-%m-%d")

st.caption(f"Showing **{sd}** → **{ed}** · Source: `iceberg.gold` via Trino · AI: LLaMA 3.3 70B (Groq)")
st.divider()

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "📈  Revenue",
    "🛍️  Products & Customers",
    "🔮  Forecast",
    "🤖  AI Assistant",
])


# ═══════════════════════════════════════════════════════════════════
# TAB 1 — Revenue Overview
# ═══════════════════════════════════════════════════════════════════
with tab1:
    df_kpi = qry(f"""
        SELECT
            COALESCE(SUM(fs.line_revenue), 0)                                           AS total_revenue,
            COUNT(DISTINCT fs.order_id)                                                  AS total_orders,
            COALESCE(SUM(fs.line_revenue) / NULLIF(COUNT(DISTINCT fs.order_id), 0), 0)  AS aov
        FROM iceberg.gold.fact_sales fs
        JOIN iceberg.gold.dim_date dd ON fs.date_key = dd.date_key
        WHERE dd.full_date BETWEEN DATE '{sd}' AND DATE '{ed}'
    """, "Loading KPIs…")

    if df_kpi is not None and not df_kpi.empty:
        rev  = float(df_kpi["total_revenue"].iloc[0])
        ords = int(df_kpi["total_orders"].iloc[0])
        aov  = float(df_kpi["aov"].iloc[0])
        c1, c2, c3 = st.columns(3, gap="medium")
        with c1:
            kpi("Total Revenue",   f"${rev:,.0f}")
        with c2:
            kpi("Total Orders",    f"{ords:,}")
        with c3:
            kpi("Avg Order Value", f"${aov:,.2f}")

    st.markdown("<br>", unsafe_allow_html=True)
    col_l, col_r = st.columns([3, 2], gap="large")

    with col_l:
        sh("Daily Revenue")
        df_d = qry(f"""
            SELECT sale_date, SUM(total_revenue) AS revenue
            FROM iceberg.gold.wide_sales_forecast
            WHERE sale_date BETWEEN DATE '{sd}' AND DATE '{ed}'
            GROUP BY sale_date ORDER BY sale_date
        """, "Loading…")
        if df_d is not None and not df_d.empty:
            df_d["sale_date"] = pd.to_datetime(df_d["sale_date"])
            fig = go.Figure(go.Scatter(
                x=df_d["sale_date"], y=df_d["revenue"],
                mode="lines",
                fill="tozeroy",
                line=dict(color=_BLUE, width=2),
                fillcolor="rgba(37,99,235,0.07)",
                hovertemplate="<b>%{x|%b %d, %Y}</b><br>$%{y:,.0f}<extra></extra>",
            ))
            fig.update_yaxes(tickprefix="$")
            st.plotly_chart(fig_style(fig), use_container_width=True)

    with col_r:
        sh("Revenue by Category")
        df_c = qry(f"""
            SELECT product_category, SUM(total_revenue) AS revenue
            FROM iceberg.gold.wide_sales_forecast
            WHERE sale_date BETWEEN DATE '{sd}' AND DATE '{ed}'
            GROUP BY product_category ORDER BY revenue ASC
        """, "Loading…")
        if df_c is not None and not df_c.empty:
            fig = px.bar(
                df_c,
                x="revenue", y="product_category", orientation="h",
                color="revenue",
                color_continuous_scale=["#bfdbfe", _BLUE],
            )
            fig.update_coloraxes(showscale=False)
            fig.update_xaxes(tickprefix="$", title_text="")
            fig.update_yaxes(title_text="")
            fig.update_traces(hovertemplate="<b>%{y}</b><br>$%{x:,.0f}<extra></extra>")
            st.plotly_chart(fig_style(fig), use_container_width=True)


# ═══════════════════════════════════════════════════════════════════
# TAB 2 — Products & Customers
# ═══════════════════════════════════════════════════════════════════
with tab2:
    col_l, col_r = st.columns(2, gap="large")

    with col_l:
        sh("Top 10 Products by Revenue")
        df_p = qry(f"""
            SELECT dp.product_name, SUM(fs.line_revenue) AS revenue
            FROM iceberg.gold.fact_sales fs
            JOIN iceberg.gold.dim_products dp ON fs.product_key = dp.product_key
            JOIN iceberg.gold.dim_date      dd ON fs.date_key    = dd.date_key
            WHERE dd.full_date BETWEEN DATE '{sd}' AND DATE '{ed}'
            GROUP BY dp.product_name ORDER BY revenue ASC LIMIT 10
        """, "Loading…")
        if df_p is not None and not df_p.empty:
            fig = px.bar(
                df_p,
                x="revenue", y="product_name", orientation="h",
                color="revenue",
                color_continuous_scale=["#99f6e4", "#0d9488"],
            )
            fig.update_coloraxes(showscale=False)
            fig.update_xaxes(tickprefix="$", title_text="")
            fig.update_yaxes(title_text="")
            fig.update_traces(hovertemplate="<b>%{y}</b><br>$%{x:,.0f}<extra></extra>")
            st.plotly_chart(fig_style(fig, height=400), use_container_width=True)

    with col_r:
        sh("Revenue Share by Category")
        df_c2 = qry(f"""
            SELECT product_category, SUM(total_revenue) AS revenue
            FROM iceberg.gold.wide_sales_forecast
            WHERE sale_date BETWEEN DATE '{sd}' AND DATE '{ed}'
            GROUP BY product_category ORDER BY revenue DESC
        """, "Loading…")
        if df_c2 is not None and not df_c2.empty:
            fig = px.pie(
                df_c2, values="revenue", names="product_category",
                hole=0.44,
                color_discrete_sequence=_PALETTE,
            )
            fig.update_traces(
                textposition="inside",
                textinfo="percent+label",
                hovertemplate="<b>%{label}</b><br>$%{value:,.0f} (%{percent})<extra></extra>",
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig_style(fig, height=400), use_container_width=True)

    st.divider()
    sh("Top 10 Customers by Total Purchase")
    df_cu = qry(f"""
        SELECT
            dc.company_name, dc.country, dc.city,
            SUM(fs.line_revenue)                                               AS total_revenue,
            COUNT(DISTINCT fs.order_id)                                        AS orders,
            SUM(fs.line_revenue) / NULLIF(COUNT(DISTINCT fs.order_id), 0)     AS aov
        FROM iceberg.gold.fact_sales fs
        JOIN iceberg.gold.dim_customers dc ON fs.customer_key = dc.customer_key
        JOIN iceberg.gold.dim_date      dd ON fs.date_key     = dd.date_key
        WHERE dd.full_date BETWEEN DATE '{sd}' AND DATE '{ed}'
        GROUP BY dc.company_name, dc.country, dc.city
        ORDER BY total_revenue DESC LIMIT 10
    """, "Loading…")
    if df_cu is not None and not df_cu.empty:
        d = df_cu.copy()
        d["total_revenue"] = d["total_revenue"].map("${:,.0f}".format)
        d["aov"]           = d["aov"].map("${:,.2f}".format)
        d.columns = ["Company", "Country", "City", "Total Revenue", "Orders", "Avg Order Value"]
        st.dataframe(d, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════
# TAB 3 — Revenue Forecast
# ═══════════════════════════════════════════════════════════════════
with tab3:
    st.info(
        "Historical revenue with 7-day and 30-day rolling averages. "
        "The dashed line is a 30-day linear trend projected forward with a ±15% confidence band.",
        icon="ℹ️",
    )
    df_h = qry(
        "SELECT sale_date, SUM(total_revenue) AS daily_revenue "
        "FROM iceberg.gold.wide_sales_forecast GROUP BY sale_date ORDER BY sale_date",
        "Loading history…",
    )
    if df_h is not None and not df_h.empty:
        df_h["sale_date"] = pd.to_datetime(df_h["sale_date"])
        df_h = df_h.sort_values("sale_date").reset_index(drop=True)
        df_h["r7"]  = df_h["daily_revenue"].rolling(7,  min_periods=1).mean()
        df_h["r30"] = df_h["daily_revenue"].rolling(30, min_periods=1).mean()

        mask = (
            (df_h["sale_date"] >= pd.Timestamp(start_d)) &
            (df_h["sale_date"] <= pd.Timestamp(end_d))
        )
        dv = df_h[mask].copy()

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dv["sale_date"], y=dv["daily_revenue"],
            name="Daily",
            line=dict(color="#93c5fd", width=1),
            fill="tozeroy",
            fillcolor="rgba(147,197,253,0.07)",
            hovertemplate="<b>%{x|%b %d}</b>  $%{y:,.0f}<extra>Daily</extra>",
        ))
        fig.add_trace(go.Scatter(
            x=dv["sale_date"], y=dv["r7"],
            name="7-day avg",
            line=dict(color=_ORANGE, width=2),
            hovertemplate="$%{y:,.0f}<extra>7d avg</extra>",
        ))
        fig.add_trace(go.Scatter(
            x=dv["sale_date"], y=dv["r30"],
            name="30-day avg",
            line=dict(color=_GREEN, width=2.5),
            hovertemplate="$%{y:,.0f}<extra>30d avg</extra>",
        ))

        if len(dv) >= 7:
            last_d   = dv["sale_date"].max()
            last_avg = float(dv["r30"].iloc[-1])
            window   = dv.tail(30)
            slope    = (
                float(window["r30"].iloc[-1]) - float(window["r30"].iloc[0])
            ) / max(len(window) - 1, 1)
            fd = pd.date_range(last_d + timedelta(days=1), periods=30)
            fv = [last_avg + slope * i for i in range(1, 31)]

            fig.add_trace(go.Scatter(
                x=list(fd) + list(fd[::-1]),
                y=[v * 1.15 for v in fv] + [v * 0.85 for v in fv[::-1]],
                fill="toself",
                fillcolor="rgba(139,92,246,0.08)",
                line=dict(color="rgba(0,0,0,0)"),
                name="±15% band",
            ))
            fig.add_trace(go.Scatter(
                x=fd, y=fv,
                name="Forecast",
                line=dict(color=_PURPLE, width=2, dash="dot"),
                hovertemplate="$%{y:,.0f}<extra>Forecast</extra>",
            ))
            fig.add_vline(
                x=last_d.timestamp() * 1000,
                line_dash="dash", line_color="#9ca3af",
                annotation_text="Forecast →",
                annotation_position="top right",
                annotation_font_color="#9ca3af",
            )

        fig.update_yaxes(tickprefix="$")
        st.plotly_chart(fig_style(fig, height=500, legend=True), use_container_width=True)
        st.caption("Confidence band ±15% · Forecast = linear extrapolation of 30-day rolling average")


# ═══════════════════════════════════════════════════════════════════
# TAB 4 — AI Assistant
# ═══════════════════════════════════════════════════════════════════
with tab4:
    agent, agent_err = _load_agent()

    if agent_err:
        st.warning(f"**AI Assistant unavailable** — {agent_err}", icon="⚠️")
        st.markdown(
            "Add `GROQ_API_KEY=<your key from https://console.groq.com>` to `.env`, "
            "then run: `docker compose up -d --build streamlit-dashboard`"
        )
    else:
        # ── Sample questions ──────────────────────────────────────────────────
        sh("Suggested questions")
        st.caption("Powered by LLaMA 3.3 70B (Groq) · Answers in Vietnamese")

        SAMPLES = [
            "Top 5 best-selling products?",
            "Monthly revenue for the most recent year?",
            "Which customer has the highest average order value?",
            "Which category had the strongest growth last month?",
            "Which employee closed the most orders?",
            "Is revenue trending up or down over the last 30 days?",
        ]
        _question_to_ask: Optional[str] = None
        scols = st.columns(3, gap="small")
        for i, q in enumerate(SAMPLES):
            if scols[i % 3].button(q, key=f"sq_{i}"):
                _question_to_ask = q

        st.divider()

        # ── Chat history ──────────────────────────────────────────────────────
        if "chat" not in st.session_state:
            st.session_state.chat = []

        for msg in st.session_state.chat:
            with st.chat_message(msg["role"], avatar="🧑" if msg["role"] == "user" else "🤖"):
                if msg["role"] == "user":
                    st.write(msg["content"])
                else:
                    # Answer — full text
                    if msg.get("content"):
                        st.markdown(msg["content"])
                    if msg.get("error"):
                        st.error(msg["error"])
                    # SQL — collapsed button
                    if msg.get("sql"):
                        with st.expander("🔍 View SQL", expanded=False):
                            st.code(msg["sql"], language="sql")
                    # Data — shown directly, no expander
                    df_msg = msg.get("df")
                    if df_msg is not None and isinstance(df_msg, pd.DataFrame) and not df_msg.empty:
                        st.dataframe(df_msg.head(20), use_container_width=True, hide_index=True)

        # ── Handle new question (chat input OR sample button) ─────────────────
        if prompt := st.chat_input("Ask anything about the Northwind data…"):
            _question_to_ask = prompt

        if _question_to_ask:
            st.session_state.chat.append({"role": "user", "content": _question_to_ask})
            with st.chat_message("user", avatar="🧑"):
                st.write(_question_to_ask)
            with st.chat_message("assistant", avatar="🤖"):
                with st.spinner("Generating SQL and querying Trino…"):
                    result = agent.ask(_question_to_ask)
                render_agent_reply(result)
                st.session_state.chat.append({
                    "role":    "assistant",
                    "content": result.answer or "",
                    "sql":     result.sql,
                    "df":      result.result_df,
                    "error":   result.error,
                })
            st.rerun()

        # ── Clear button ──────────────────────────────────────────────────────
        if st.session_state.chat:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🗑️  Clear conversation", type="secondary"):
                st.session_state.chat = []
                st.rerun()
