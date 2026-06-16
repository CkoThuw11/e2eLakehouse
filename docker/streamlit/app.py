"""
Northwind Lakehouse — Analytics Dashboard
Streamlit app | iceberg.gold via Trino
Pages: Overview (Revenue + Products & Customers) · Forecast · Model Training
Floating AI Assistant in the bottom-right corner.

Module layout:
- app.py     → page config, global CSS, header, tab orchestration
- data.py    → Trino + MinIO data-loading helpers
- chat.py    → floating AI assistant component
"""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from chat import render_floating_assistant
from data import (
    date_bounds,
    load_prophet_model,
    load_training_history,
    qry,
    refresh_everything,
)

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

/* Leave room at the bottom so the floating chat never overlaps content */
.main .block-container { padding-bottom: 110px; }

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

/* ── Header alignment: keep date filter and Refresh on the same baseline ── */
.st-key-header_filter,
.st-key-header_refresh {
    display: flex;
    align-items: center;
    min-height: 56px;
}
.st-key-header_filter [data-testid="stDateInput"] { width: 100%; }
.st-key-header_filter [data-testid="stDateInput"] > div { margin: 0 !important; }
.st-key-header_refresh .stButton { width: 100%; }

/* ── Floating AI chat — circular FAB + square chat panel ── */
/* Closed state: round button pinned to bottom-right of viewport. */
.st-key-ai_fab {
    position: fixed !important;
    bottom: 22px;
    right: 22px;
    z-index: 9999;
    width: 64px !important;
}
.st-key-ai_fab .stButton > button {
    width: 60px !important;
    height: 60px !important;
    border-radius: 50% !important;
    background: linear-gradient(135deg, #2563EB 0%, #8B5CF6 100%) !important;
    color: #ffffff !important;
    border: none !important;
    box-shadow: 0 10px 28px rgba(37, 99, 235, 0.45) !important;
    font-size: 1.45rem !important;
    padding: 0 !important;
    line-height: 1 !important;
}
.st-key-ai_fab .stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 14px 32px rgba(37, 99, 235, 0.55) !important;
}

/* Open state: fixed-size square chat panel pinned to bottom-right. */
.st-key-ai_chat_panel {
    position: fixed !important;
    bottom: 22px;
    right: 22px;
    z-index: 9999;
    width: 520px !important;
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 16px;
    box-shadow: 0 18px 44px rgba(0,0,0,0.18);
    padding: 18px 18px 14px 18px !important;
}
.st-key-ai_chat_panel h4 {
    margin: 0;
    font-size: 1.05rem;
    font-weight: 700;
    color: #111827;
}

/* Header bar: title column flexes, action columns are pinned to identical
   narrow width so the trash and minimize icons match. */
.st-key-ai_header [data-testid="stHorizontalBlock"] {
    align-items: center;
    gap: 6px !important;
}
.st-key-ai_header [data-testid="column"]:nth-child(2),
.st-key-ai_header [data-testid="column"]:nth-child(3) {
    flex: 0 0 44px !important;
    width: 44px !important;
    min-width: 44px !important;
    max-width: 44px !important;
}
.st-key-ai_header .stButton { width: 40px !important; }
.st-key-ai_header .stButton > button {
    width: 40px !important;
    min-width: 40px !important;
    max-width: 40px !important;
    height: 40px !important;
    min-height: 40px !important;
    padding: 0 !important;
    border-radius: 10px !important;
    border: 1px solid #e5e7eb !important;
    background: #f9fafb !important;
    color: #374151 !important;
    font-size: 1.15rem !important;
    line-height: 1 !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
}
.st-key-ai_header .stButton > button:hover {
    background: #eff6ff !important;
    border-color: #93c5fd !important;
    color: #1d4ed8 !important;
}

/* Scrollable messages region between header and input. */
.st-key-ai_chat_messages {
    max-height: 420px;
    overflow-y: auto;
    padding: 6px 4px 8px 4px;
    border-top: 1px solid #f3f4f6;
    border-bottom: 1px solid #f3f4f6;
    margin: 10px 0 12px 0;
}
.st-key-ai_chat_messages [data-testid="stChatMessage"] {
    padding: 0.6rem 0.75rem;
    margin-bottom: 0.5rem;
    font-size: 0.92rem;
}

/* Loading indicator that sits ABOVE the input row while the agent thinks. */
.st-key-ai_chat_loading {
    padding: 6px 4px;
    margin-bottom: 6px;
}
.st-key-ai_chat_loading [data-testid="stSpinner"] {
    margin: 0 !important;
}

/* Sample-question chips inside the panel. */
.st-key-ai_chat_panel .stButton > button {
    font-size: 0.85rem;
    padding: 0.55rem 0.85rem;
}

/* Input row stays at the bottom of the panel (renders last) */
.st-key-ai_chat_input .stTextInput input {
    border-radius: 10px;
    padding: 0.55rem 0.75rem;
    font-size: 0.95rem;
}
.st-key-ai_chat_input .stFormSubmitButton > button {
    height: 42px !important;
    min-height: 42px !important;
    border-radius: 10px !important;
    font-size: 1.1rem !important;
    background: linear-gradient(135deg, #2563EB 0%, #8B5CF6 100%) !important;
    color: white !important;
    border: none !important;
}
/* Hide Streamlit's default "Press Enter to submit form" hint so the
   placeholder is the only guidance inside the input. */
.st-key-ai_chat_input [data-testid="InputInstructions"],
.st-key-ai_chat_input [data-testid="stWidgetInstructions"] {
    display: none !important;
}
</style>
""", unsafe_allow_html=True)


# ── UI helpers (kept local — used only by the tab renderers below) ────────────
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


# ── Page header: title · date filter · refresh ────────────────────────────────
with st.spinner(""):
    min_d, max_d = date_bounds()

title_col, filter_col, refresh_col = st.columns([5, 3, 1])

with title_col:
    st.markdown(
        '<h1 style="font-size:1.6rem;font-weight:800;color:#111827;margin:0.4rem 0 0">'
        '📊 Northwind Analytics Dashboard</h1>',
        unsafe_allow_html=True,
    )

with filter_col:
    with st.container(key="header_filter"):
        dr = st.date_input(
            "Date range",
            value=(min_d, max_d),
            min_value=min_d,
            max_value=max_d,
            format="YYYY-MM-DD",
            label_visibility="collapsed",
        )

with refresh_col:
    with st.container(key="header_refresh"):
        if st.button("🔄 Refresh", use_container_width=True, help="Reload latest data from the lakehouse"):
            refresh_everything()
            st.rerun()

if isinstance(dr, (list, tuple)) and len(dr) == 2:
    start_d, end_d = dr[0], dr[1]
elif isinstance(dr, (list, tuple)) and len(dr) == 1:
    start_d, end_d = dr[0], max_d
else:
    start_d, end_d = min_d, max_d

sd = start_d.strftime("%Y-%m-%d")
ed = end_d.strftime("%Y-%m-%d")

st.divider()

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_overview, tab_forecast, tab_model = st.tabs([
    "📈  Overview",
    "🔮  Forecast",
    "🧪  Model Training",
])


# ═══════════════════════════════════════════════════════════════════
# TAB 1 — Overview (Revenue + Products & Customers)
# ═══════════════════════════════════════════════════════════════════
with tab_overview:
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

    st.divider()
    st.markdown(
        '<h2 style="font-size:1.15rem;font-weight:700;color:#111827;margin:0.4rem 0 1rem">'
        '🛍️ Products & Customers</h2>',
        unsafe_allow_html=True,
    )

    pc_l, pc_r = st.columns(2, gap="large")

    with pc_l:
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

    with pc_r:
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
# TAB 2 — Forecast
# ═══════════════════════════════════════════════════════════════════
with tab_forecast:
    prophet_model, prophet_metrics = load_prophet_model()
    model_error = prophet_metrics.get("error") if isinstance(prophet_metrics, dict) else None
    has_prophet = prophet_model is not None and not model_error

    view_choice = st.radio(
        "Timeline view",
        ["Full timeline", "Last 6 months"],
        horizontal=True,
        label_visibility="collapsed",
        key="forecast_view",
    )

    df_h = qry(
        "SELECT sale_date, SUM(total_revenue) AS daily_revenue "
        "FROM iceberg.gold.wide_sales_forecast "
        "WHERE total_revenue > 0 "
        "GROUP BY sale_date ORDER BY sale_date",
        "Loading history…",
    )

    if df_h is not None and not df_h.empty:
        df_h["sale_date"] = pd.to_datetime(df_h["sale_date"])
        df_h = df_h.sort_values("sale_date").reset_index(drop=True)
        df_h["r7"]  = df_h["daily_revenue"].rolling(7,  min_periods=1).mean()
        df_h["r30"] = df_h["daily_revenue"].rolling(30, min_periods=1).mean()

        last_actual_date = df_h["sale_date"].max()

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_h["sale_date"], y=df_h["daily_revenue"],
            name="Daily revenue",
            line=dict(color="#93c5fd", width=1),
            fill="tozeroy",
            fillcolor="rgba(147,197,253,0.07)",
            hovertemplate="<b>%{x|%b %d, %Y}</b>  $%{y:,.0f}<extra>Daily</extra>",
        ))
        fig.add_trace(go.Scatter(
            x=df_h["sale_date"], y=df_h["r7"],
            name="7-day avg",
            line=dict(color=_ORANGE, width=2),
            hovertemplate="$%{y:,.0f}<extra>7d avg</extra>",
        ))
        fig.add_trace(go.Scatter(
            x=df_h["sale_date"], y=df_h["r30"],
            name="30-day avg",
            line=dict(color=_GREEN, width=2.5),
            hovertemplate="$%{y:,.0f}<extra>30d avg</extra>",
        ))

        fc_future: Optional[pd.DataFrame] = None

        if has_prophet:
            future_df  = prophet_model.make_future_dataframe(periods=30, freq="D")
            forecast   = prophet_model.predict(future_df)
            fc_future  = forecast[forecast["ds"] > last_actual_date].copy()

            fig.add_trace(go.Scatter(
                x=pd.concat([fc_future["ds"], fc_future["ds"].iloc[::-1]]),
                y=pd.concat([fc_future["yhat_upper"], fc_future["yhat_lower"].iloc[::-1]]),
                fill="toself",
                fillcolor="rgba(139,92,246,0.12)",
                line=dict(color="rgba(0,0,0,0)"),
                name="80% confidence",
                hoverinfo="skip",
            ))
            fig.add_trace(go.Scatter(
                x=fc_future["ds"], y=fc_future["yhat"],
                name="Prophet forecast",
                line=dict(color=_PURPLE, width=2.5, dash="dot"),
                hovertemplate="<b>%{x|%b %d, %Y}</b>  $%{y:,.0f}<extra>Prophet</extra>",
            ))
            fig.add_vline(
                x=last_actual_date.timestamp() * 1000,
                line_dash="dash", line_color="#9ca3af",
                annotation_text="Prophet forecast →",
                annotation_position="top right",
                annotation_font_color="#9ca3af",
            )
            fig.update_yaxes(tickprefix="$")
            if view_choice == "Last 6 months":
                fig.update_xaxes(range=[
                    last_actual_date - timedelta(days=180),
                    last_actual_date + timedelta(days=30),
                ])
            st.plotly_chart(fig_style(fig, height=500, legend=True), use_container_width=True)

            if fc_future is not None and not fc_future.empty:
                st.markdown("<br>", unsafe_allow_html=True)
                sh("Forecasted Revenue · Next 30 Days")

                total_fc = float(fc_future["yhat"].sum())
                avg_fc   = float(fc_future["yhat"].mean())
                peak_row = fc_future.loc[fc_future["yhat"].idxmax()]
                peak_date = pd.to_datetime(peak_row["ds"]).strftime("%b %d, %Y")
                peak_val  = float(peak_row["yhat"])

                k1, k2, k3 = st.columns(3, gap="medium")
                with k1:
                    kpi("30-Day Forecast Total",   f"${total_fc:,.0f}")
                with k2:
                    kpi("Avg Daily Forecast",      f"${avg_fc:,.0f}")
                with k3:
                    kpi(f"Peak Day · {peak_date}", f"${peak_val:,.0f}")

                st.markdown("<br>", unsafe_allow_html=True)
                sh("Day-by-Day Forecast Table")
                tbl = fc_future[["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()
                tbl["ds"]         = pd.to_datetime(tbl["ds"]).dt.strftime("%Y-%m-%d")
                tbl["yhat"]       = tbl["yhat"].map("${:,.0f}".format)
                tbl["yhat_lower"] = tbl["yhat_lower"].map("${:,.0f}".format)
                tbl["yhat_upper"] = tbl["yhat_upper"].map("${:,.0f}".format)
                tbl.columns = ["Date", "Forecast", "Lower (80% CI)", "Upper (80% CI)"]
                st.dataframe(tbl, use_container_width=True, hide_index=True, height=350)

        else:
            if len(df_h) >= 7:
                last_avg = float(df_h["r30"].iloc[-1])
                window   = df_h.tail(30)
                slope    = (float(window["r30"].iloc[-1]) - float(window["r30"].iloc[0])) / max(len(window) - 1, 1)
                fd = pd.date_range(last_actual_date + timedelta(days=1), periods=30)
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
                    name="Forecast (linear)",
                    line=dict(color=_PURPLE, width=2, dash="dot"),
                    hovertemplate="$%{y:,.0f}<extra>Forecast</extra>",
                ))
                fig.add_vline(
                    x=last_actual_date.timestamp() * 1000,
                    line_dash="dash", line_color="#9ca3af",
                    annotation_text="Forecast →",
                    annotation_position="top right",
                    annotation_font_color="#9ca3af",
                )
            fig.update_yaxes(tickprefix="$")
            if view_choice == "Last 6 months":
                fig.update_xaxes(range=[
                    last_actual_date - timedelta(days=180),
                    last_actual_date + timedelta(days=30),
                ])
            st.plotly_chart(fig_style(fig, height=500, legend=True), use_container_width=True)
            st.caption("Linear projection · Confidence band ±15%")


# ═══════════════════════════════════════════════════════════════════
# TAB 3 — Model Training
# ═══════════════════════════════════════════════════════════════════
with tab_model:
    hist_df = load_training_history()
    if hist_df.empty:
        st.info(
            "No training history yet. Run the `model_retrain_dag` in Airflow, "
            "then click **🔄 Refresh** above to update the dashboard."
        )
    else:
        latest      = hist_df.iloc[-1]
        n_runs      = len(hist_df)
        latest_mae  = float(latest.get("mae", 0))
        latest_rmse = float(latest.get("rmse", 0))

        k1, k2, k3 = st.columns(3, gap="medium")
        with k1:
            kpi("Training Runs", f"{n_runs}")
        with k2:
            kpi("Latest MAE",    f"${latest_mae:,.0f}")
        with k3:
            kpi("Latest RMSE",   f"${latest_rmse:,.0f}")

        st.markdown("<br>", unsafe_allow_html=True)
        sh("Training Run History")
        cols_keep = [c for c in ["trained_at", "train_end_date", "mae", "rmse",
                                 "mean_test_revenue", "meets_threshold", "model_key"]
                     if c in hist_df.columns]
        view = hist_df[cols_keep].copy().sort_values("trained_at", ascending=False)
        if "trained_at" in view.columns:
            view["trained_at"] = pd.to_datetime(view["trained_at"]).dt.strftime("%Y-%m-%d %H:%M")
        for moneycol in ("mae", "rmse", "mean_test_revenue"):
            if moneycol in view.columns:
                view[moneycol] = view[moneycol].map(lambda v: f"${v:,.0f}")
        if "meets_threshold" in view.columns:
            view["meets_threshold"] = view["meets_threshold"].map(lambda v: "✅" if v else "⚠️")
        view.columns = [c.replace("_", " ").title() for c in view.columns]
        st.dataframe(view, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════
# Floating AI Assistant
# ═══════════════════════════════════════════════════════════════════
render_floating_assistant()
