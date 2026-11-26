"""Analytics — Multi-dimensional fleet performance, excursion, and operational reporting."""

from __future__ import annotations

import altair as alt
import streamlit as st

from src.analytics import build_operational_report_md, compute_kpis
from src.charts import (
    chart_corridor_risk_comparison,
    chart_delay_probability_hist,
    chart_delivery_performance_trend,
    chart_excursion_frequency,
    chart_risk_distribution,
)
from src.components.shell import get_active_profile
from src.data_access import load_telemetry_data

df, source_info = load_telemetry_data()
profile = get_active_profile()

if df.empty:
    st.error("Telemetry data unavailable.")
    st.stop()

# ==========================================
# ANALYTICS FILTERS
# ==========================================
with st.container(border=True):
    f1, f2, f3, f4 = st.columns(4)
    min_d, max_d = df["timestamp"].min().date(), df["timestamp"].max().date()
    date_rng = f1.date_input("Date Range", value=(min_d, max_d), min_value=min_d, max_value=max_d, key="ana_dates")
    corridor_sel = f2.multiselect("Corridor Zone", sorted(df["corridor_zone"].unique()), default=sorted(df["corridor_zone"].unique()), key="ana_corridors")
    risk_sel = f3.multiselect("Risk Category", ["High Risk", "Moderate Risk", "Low Risk"], default=["High Risk", "Moderate Risk", "Low Risk"], key="ana_risks")
    t_min, t_max = float(df["iot_temperature"].min()), float(df["iot_temperature"].max())
    temp_rng = f4.slider("Temperature Range (°C)", t_min, t_max, (t_min, t_max), key="ana_temp")

filtered = df[
    df["corridor_zone"].isin(corridor_sel)
    & df["risk_classification"].isin(risk_sel)
    & (df["iot_temperature"] >= temp_rng[0])
    & (df["iot_temperature"] <= temp_rng[1])
].copy()
if isinstance(date_rng, (list, tuple)) and len(date_rng) == 2:
    filtered = filtered[(filtered["timestamp"].dt.date >= date_rng[0]) & (filtered["timestamp"].dt.date <= date_rng[1])]

if filtered.empty:
    st.warning("No records match the selected analytics filters.")
    st.stop()

kpis = compute_kpis(filtered, profile)

# Export Bar
ex1, ex2 = st.columns([2, 1], vertical_alignment="center")
with ex1:
    st.caption(f"Analyzing **{len(filtered):,}** telemetry records · Source: **{source_info['source_label']}**")
with ex2:
    with st.container(horizontal=True, horizontal_alignment="right"):
        st.download_button(
            "Download Filtered CSV",
            data=filtered.head(10000).to_csv(index=False),
            file_name="fde_analytics_filtered.csv",
            mime="text/csv",
            icon=":material/download:",
        )
        st.download_button(
            "Download Summary (.md)",
            data=build_operational_report_md(filtered, kpis, profile, source_info),
            file_name="fde_analytics_summary.md",
            mime="text/markdown",
            icon=":material/description:",
        )

# Summary Metrics
m1, m2, m3, m4 = st.columns(4)
m1.metric("Filtered Observations", f"{kpis['total_records']:,}", border=True)
m2.metric("Excursion Rate", f"{(kpis['excursion_count'] / max(kpis['total_records'], 1)) * 100:.1f}%", border=True)
m3.metric("Mean Delay Probability", f"{kpis['avg_delay_prob']:.1%}", border=True)
m4.metric(kpis["performance_label"], f"{kpis['avg_performance_pct']:.1f}%", border=True)

# Charts Grid
r1_l, r1_r = st.columns(2)
with r1_l:
    with st.container(border=True):
        st.subheader("Delivery & Readiness Performance", anchor=False)
        st.altair_chart(chart_delivery_performance_trend(filtered), width="stretch")
with r1_r:
    with st.container(border=True):
        st.subheader("Monthly Temperature Excursion Frequency", anchor=False)
        st.altair_chart(chart_excursion_frequency(filtered, profile), width="stretch")

r2_l, r2_r = st.columns(2)
with r2_l:
    with st.container(border=True):
        st.subheader("Delay Probability Histogram", anchor=False)
        st.altair_chart(chart_delay_probability_hist(filtered), width="stretch")
with r2_r:
    with st.container(border=True):
        st.subheader("Risk Classification Breakdown", anchor=False)
        st.altair_chart(chart_risk_distribution(filtered), width="stretch")

r3_l, r3_r = st.columns(2)
with r3_l:
    with st.container(border=True):
        st.subheader("Corridor Route Risk Comparison", anchor=False)
        st.altair_chart(chart_corridor_risk_comparison(filtered), width="stretch")
with r3_r:
    with st.container(border=True):
        if "weather_condition_severity" in filtered.columns:
            st.subheader("Weather Severity vs. Disruption Likelihood", anchor=False)
            sample = filtered.tail(1500)
            wx_chart = (
                alt.Chart(sample)
                .mark_circle(size=36, opacity=0.6)
                .encode(
                    x=alt.X("weather_condition_severity:Q", title="Dataset Weather Severity"),
                    y=alt.Y("disruption_likelihood_score:Q", title="Disruption Likelihood"),
                    color=alt.Color(
                        "risk_classification:N",
                        scale=alt.Scale(
                            domain=["High Risk", "Moderate Risk", "Low Risk"],
                            range=["#FB7185", "#FBBF24", "#34D399"],
                        ),
                    ),
                    tooltip=["record_id:N", "corridor_zone:N", "weather_condition_severity:Q", "disruption_likelihood_score:Q"],
                )
                .properties(height=270)
                .configure_view(strokeWidth=0, fill="transparent")
                .configure(background="transparent")
                .configure_axis(gridColor="#1A2942", labelColor="#94A3B8", titleColor="#CBD5E1")
                .configure_legend(labelColor="#CBD5E1", titleColor="#94A3B8", orient="top")
            )
            st.altair_chart(wx_chart, width="stretch")
        else:
            st.subheader("Port Congestion vs. Route Risk", anchor=False)
            sample = filtered.tail(1500)
            pc_chart = (
                alt.Chart(sample)
                .mark_circle(size=36, opacity=0.6)
                .encode(
                    x=alt.X("port_congestion_level:Q", title="Port Congestion Level"),
                    y=alt.Y("route_risk_level:Q", title="Route Risk Index"),
                    color="risk_classification:N",
                )
                .properties(height=270)
                .configure_view(strokeWidth=0, fill="transparent")
                .configure(background="transparent")
            )
            st.altair_chart(pc_chart, width="stretch")
