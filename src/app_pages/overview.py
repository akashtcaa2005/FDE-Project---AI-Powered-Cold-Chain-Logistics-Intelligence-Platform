"""Overview — Enterprise Cold Chain Command Center."""

from __future__ import annotations

import streamlit as st

from src.analytics import (
    build_executive_briefing,
    build_operational_report_md,
    compute_kpis,
    generate_operational_alerts,
)
from src.charts import (
    chart_corridor_risk_comparison,
    chart_delay_probability_hist,
    chart_delivery_performance_trend,
    chart_fleet_activity_timeline,
    chart_risk_distribution,
    chart_temperature_trend_with_thresholds,
)
from src.components.shell import get_active_profile
from src.config import CORRIDOR_HUBS
from src.data_access import fetch_corridor_weather, load_telemetry_data

df, source_info = load_telemetry_data()
profile = get_active_profile()

if df.empty:
    st.error(f"Telemetry unavailable: {source_info.get('sql_note', 'Unknown error')}")
    st.stop()

if source_info.get("source_mode") == "csv_fallback":
    st.info(
        f"**Data Source Notice:** Connected to **{source_info['source_label']}** "
        f"({source_info['row_count']:,} records). Live SQL Server is currently offline "
        f"(`{source_info.get('sql_note')}`).",
        icon=":material/info:",
    )

kpis = compute_kpis(df, profile)
sparks = kpis.get("sparklines", {})
deltas = kpis.get("deltas", {})

# ==========================================
# KPI CARDS (2 ROWS x 4 CARDS)
# ==========================================
row1 = st.columns(4)
row1[0].metric(
    "Monitored Telemetry Records",
    f"{kpis['total_records']:,}",
    delta=deltas.get("records"),
    border=True,
    chart_data=sparks.get("records"),
    chart_type="bar",
    help="Total observations in FDE_VIEWS.VW_ACTIVE_FLEET / telemetry dataset (schema has no separate vehicle master table).",
)
row1[1].metric(
    "Active Window (Latest 30d)",
    f"{kpis['recent_30d_records']:,}",
    delta=f"{kpis['low_risk_count']:,} low-risk overall",
    delta_color="off",
    border=True,
)
row1[2].metric(
    "High-Risk Movements",
    f"{kpis['high_risk_count']:,}",
    delta=deltas.get("high_risk"),
    delta_color="inverse",
    border=True,
    chart_data=sparks.get("high_risk"),
    chart_type="line",
)
row1[3].metric(
    kpis["performance_label"],
    f"{kpis['avg_performance_pct']:.1f}%",
    delta=deltas.get("performance"),
    border=True,
    chart_data=sparks.get("performance"),
    chart_type="line",
)

row2 = st.columns(4)
row2[0].metric(
    "Delay Escalations (>65%)",
    f"{kpis['delayed_risk_count']:,}",
    delta=deltas.get("delayed"),
    delta_color="inverse",
    border=True,
    chart_data=sparks.get("delayed"),
    chart_type="line",
    help="SOP §3 threshold: delay_probability > 0.65.",
)
row2[1].metric(
    "Temperature Excursions",
    f"{kpis['excursion_count']:,}",
    delta=deltas.get("excursions"),
    delta_color="inverse",
    border=True,
    chart_data=sparks.get("excursions"),
    chart_type="bar",
    help=f"Outside {profile.min_temp_c:.1f}°C – {profile.critical_temp_c:.1f}°C ({profile.label}).",
)
row2[2].metric(
    "Port Congestion Breaches (>7.0)",
    f"{kpis['port_breach_count']:,}",
    delta=f"Avg Route Risk {kpis['avg_route_risk']:.2f}/10",
    delta_color="off",
    border=True,
    help="SOP §2 diversion threshold: port_congestion_level > 7.0.",
)
row2[3].metric(
    "Mean Cargo Temperature",
    f"{kpis['avg_temp']:.2f} °C",
    delta=deltas.get("temp"),
    delta_color="off",
    border=True,
    chart_data=sparks.get("temp"),
    chart_type="line",
)

st.space("small")

# ==========================================
# EXECUTIVE BRIEFING & REPORT EXPORT
# ==========================================
with st.container(border=True):
    b_head_l, b_head_r = st.columns([2.2, 1], vertical_alignment="center")
    with b_head_l:
        st.subheader("Executive Operational Briefing", anchor=False)
    with b_head_r:
        with st.container(horizontal=True, horizontal_alignment="right"):
            report_md = build_operational_report_md(df, kpis, profile, source_info)
            st.download_button(
                "Download Report (.md)",
                data=report_md,
                file_name="fde_operational_briefing.md",
                mime="text/markdown",
                icon=":material/download:",
            )
            if st.button("Ask AI Dispatcher for Deep Briefing", icon=":material/smart_toy:"):
                st.session_state.pending_dispatcher_prompt = (
                    "Generate today's executive operational briefing using fleet telemetry, "
                    "live corridor weather at Southern California (33.77, -118.19), and SOP v2.4 rules."
                )
                st.switch_page(st.session_state["_page_refs"]["ai_dispatcher"])

    st.markdown(build_executive_briefing(df, kpis, profile, source_info))

st.space("small")

# ==========================================
# MAIN VISUALIZATIONS
# ==========================================
col_l, col_r = st.columns([1.4, 1])
with col_l:
    with st.container(border=True):
        st.subheader("Temperature Trend vs. SOP Thresholds", anchor=False)
        st.caption(f"Active Envelope: {profile.source}")
        st.altair_chart(chart_temperature_trend_with_thresholds(df, profile), width="stretch")

with col_r:
    with st.container(border=True):
        st.subheader("Risk Classification Distribution", anchor=False)
        st.caption("Breakdown across monitored telemetry observations")
        st.altair_chart(chart_risk_distribution(df), width="stretch")

col2_l, col2_r = st.columns(2)
with col2_l:
    with st.container(border=True):
        st.subheader("Delivery & Fulfillment Performance Trend", anchor=False)
        st.altair_chart(chart_delivery_performance_trend(df), width="stretch")

with col2_r:
    with st.container(border=True):
        st.subheader("Delay Probability Distribution", anchor=False)
        st.altair_chart(chart_delay_probability_hist(df), width="stretch")

col3_l, col3_r = st.columns(2)
with col3_l:
    with st.container(border=True):
        st.subheader("Corridor Route Risk Comparison", anchor=False)
        st.altair_chart(chart_corridor_risk_comparison(df), width="stretch")

with col3_r:
    with st.container(border=True):
        st.subheader("Fleet Activity Timeline by Risk Class", anchor=False)
        st.altair_chart(chart_fleet_activity_timeline(df), width="stretch")

st.space("small")

# ==========================================
# OPERATIONAL ALERTS FEED
# ==========================================
with st.container(border=True):
    a_col1, a_col2 = st.columns([2, 1], vertical_alignment="center")
    with a_col1:
        st.subheader("Operational Alerts & SOP Triggers", anchor=False)
        st.caption("Derived directly from telemetry threshold violations and live SoCal Open-Meteo weather.")
    with a_col2:
        include_live_wx = st.toggle("Include live Open-Meteo hub checks", value=True)

    wx_snaps = []
    if include_live_wx:
        for hub in CORRIDOR_HUBS[:2]:
            snap = fetch_corridor_weather(hub.latitude, hub.longitude)
            snap["hub_code"] = hub.code
            snap["hub_name"] = hub.name
            wx_snaps.append(snap)

    alerts = generate_operational_alerts(df, profile, weather_snapshots=wx_snaps, limit=10)
    if not alerts:
        st.success("No active SOP alerts detected under current criteria.", icon=":material/check_circle:")
    else:
        for idx, alert in enumerate(alerts):
            sev = alert["severity"]
            badge = (
                ":red-badge[CRITICAL]"
                if sev == "CRITICAL"
                else (":orange-badge[HIGH]" if sev == "HIGH" else ":yellow-badge[WARNING]")
            )
            with st.container(border=True):
                c_info, c_btn = st.columns([4, 1], vertical_alignment="center")
                with c_info:
                    st.markdown(
                        f"{badge} **{alert['category']}** · `{alert['record_id']}` · "
                        f"{alert['corridor']} · `{alert['timestamp']}`"
                    )
                    st.write(alert["summary"])
                    st.caption(alert["recommendation"])
                with c_btn:
                    if st.button("Investigate", key=f"inv_alert_{idx}", icon=":material/search:"):
                        st.session_state.pending_dispatcher_prompt = (
                            f"Investigate alert for {alert['record_id']} ({alert['category']}): "
                            f"{alert['summary']} Check telemetry, corridor weather, and SOP mitigation."
                        )
                        st.switch_page(st.session_state["_page_refs"]["ai_dispatcher"])
