"""Route Intelligence — Corridor risk comparison and SOP §2 port congestion diversion monitor."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from src.charts import chart_corridor_risk_comparison
from src.config import CORRIDOR_HUBS, SOP_PORT_CONGESTION_CRITICAL
from src.data_access import load_telemetry_data

df, source_info = load_telemetry_data()
if df.empty:
    st.error("Telemetry unavailable.")
    st.stop()

port_breaches = df[df["port_congestion_level"] > SOP_PORT_CONGESTION_CRITICAL]
high_route = df[df["route_risk_level"] >= 7.0]

k1, k2, k3, k4 = st.columns(4)
k1.metric("Monitored Corridor Zones", f"{df['corridor_zone'].nunique()}", border=True)
k2.metric("SOP §2 Port Breaches (>7.0)", f"{len(port_breaches):,}", border=True)
k3.metric("Elevated Route Risk (>=7.0)", f"{len(high_route):,}", border=True)
k4.metric("Mean Port Congestion", f"{df['port_congestion_level'].mean():.2f} / 10", border=True)

if not port_breaches.empty:
    st.warning(
        f"**SOP v2.4 §2 Diversion Rule Active:** {len(port_breaches):,} telemetry observations exceed "
        f"port congestion severity `{SOP_PORT_CONGESTION_CRITICAL:.1f}`. Standard port holding is suspended; "
        "active SoCal shipments should be evaluated for diversion to **Inland Empire Overflow Depot (San Bernardino)**.",
        icon=":material/alt_route:",
    )

col_l, col_r = st.columns([1.25, 1])
with col_l:
    with st.container(border=True):
        st.subheader("Corridor Risk Index & Port Congestion", anchor=False)
        st.altair_chart(chart_corridor_risk_comparison(df), width="stretch")

with col_r:
    with st.container(border=True):
        st.subheader("Corridor Performance Matrix", anchor=False)
        corridor_summary = (
            df.groupby("corridor_zone", as_index=False)
            .agg(
                Observations=("record_id", "count"),
                Avg_Route_Risk=("route_risk_level", "mean"),
                Avg_Port_Congestion=("port_congestion_level", "mean"),
                Avg_Delay_Prob=("delay_probability", "mean"),
                High_Risk_Count=("risk_classification", lambda s: int((s == "High Risk").sum())),
            )
            .sort_values("Avg_Route_Risk", ascending=False)
        )
        st.dataframe(
            corridor_summary,
            column_config={
                "corridor_zone": "Corridor Zone",
                "Observations": st.column_config.NumberColumn("Records", format="%d"),
                "Avg_Route_Risk": st.column_config.NumberColumn("Route Risk", format="%.2f"),
                "Avg_Port_Congestion": st.column_config.NumberColumn("Port Cong.", format="%.2f"),
                "Avg_Delay_Prob": st.column_config.ProgressColumn("Delay Prob", min_value=0.0, max_value=1.0, format="%.1%"),
                "High_Risk_Count": st.column_config.NumberColumn("High Risk", format="%d"),
            },
            hide_index=True,
        )

st.space("small")

with st.container(border=True):
    st.subheader("Route Risk vs. Delay Probability (Sampled 2,000 Latest Records)", anchor=False)
    sample = df.tail(2000).copy()
    scatter = (
        alt.Chart(sample)
        .mark_circle(size=42, opacity=0.65)
        .encode(
            x=alt.X("route_risk_level:Q", title="Route Risk Index (0–10)"),
            y=alt.Y("delay_probability:Q", title="Delay Probability"),
            color=alt.Color(
                "risk_classification:N",
                scale=alt.Scale(
                    domain=["High Risk", "Moderate Risk", "Low Risk"],
                    range=["#FB7185", "#FBBF24", "#34D399"],
                ),
                title="Risk Class",
            ),
            tooltip=["record_id:N", "corridor_zone:N", "route_risk_level:Q", "port_congestion_level:Q", "delay_probability:Q"],
        )
        .properties(height=280)
        .configure_view(strokeWidth=0, fill="transparent")
        .configure(background="transparent")
        .configure_axis(gridColor="#1A2942", labelColor="#94A3B8", titleColor="#CBD5E1")
        .configure_legend(labelColor="#CBD5E1", titleColor="#94A3B8", orient="top")
    )
    st.altair_chart(scatter, width="stretch")

with st.container(border=True):
    st.subheader("Reference Logistics Hubs & Diversion Facilities", anchor=False)
    hub_df = pd.DataFrame(
        [
            {
                "Hub Code": h.code,
                "Facility / Corridor": h.name,
                "Region": h.region,
                "Latitude": h.latitude,
                "Longitude": h.longitude,
                "Operational Notes": h.notes,
            }
            for h in CORRIDOR_HUBS
        ]
    )
    st.dataframe(hub_df, hide_index=True)
