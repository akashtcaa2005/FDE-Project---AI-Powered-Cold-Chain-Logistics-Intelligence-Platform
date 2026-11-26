"""Cold Chain Monitoring — SOP-grounded & configurable cargo temperature intelligence."""

from __future__ import annotations

import streamlit as st

from src.charts import chart_excursion_frequency, chart_temperature_trend_with_thresholds
from src.components.shell import get_active_profile
from src.config import COLD_CHAIN_PROFILES
from src.data_access import load_telemetry_data

df, source_info = load_telemetry_data()
if df.empty:
    st.error("Telemetry dataset unavailable.")
    st.stop()

# ==========================================
# PROFILE & FILTER BAR
# ==========================================
with st.container(border=True):
    c1, c2, c3 = st.columns([1.6, 1.2, 1.2])
    profile_keys = list(COLD_CHAIN_PROFILES.keys())
    cur_key = st.session_state.get("active_profile_key", "fresh_perishables")
    sel_key = c1.selectbox(
        "Cargo Temperature Standard",
        options=profile_keys,
        index=profile_keys.index(cur_key) if cur_key in profile_keys else 0,
        format_func=lambda k: COLD_CHAIN_PROFILES[k].label,
        key="cold_chain_profile_select",
    )
    st.session_state.active_profile_key = sel_key
    profile = COLD_CHAIN_PROFILES[sel_key]

    corridor_sel = c2.selectbox("Corridor Zone", ["All", *sorted(df["corridor_zone"].unique())], key="cc_corridor")
    min_dt, max_dt = df["timestamp"].min().date(), df["timestamp"].max().date()
    date_range = c3.date_input("Observation Window", value=(min_dt, max_dt), min_value=min_dt, max_value=max_dt, key="cc_dates")

if profile.sop_verified:
    st.success(f"**Verified Policy:** {profile.source}", icon=":material/verified:")
else:
    st.info(
        f"**Configurable Threshold Profile:** {profile.source}. "
        "Note: Only *Fresh Perishables (0.0°C–4.0°C)* is explicitly specified in `Cold_Chain_Incident_SOP_v2.md`.",
        icon=":material/tune:",
    )

work = df.copy()
if corridor_sel != "All":
    work = work[work["corridor_zone"] == corridor_sel]
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    work = work[(work["timestamp"].dt.date >= date_range[0]) & (work["timestamp"].dt.date <= date_range[1])]

if work.empty:
    st.warning("No observations in selected window.")
    st.stop()

in_range = (work["iot_temperature"] >= profile.min_temp_c) & (work["iot_temperature"] <= profile.critical_temp_c)
warning_zone = (work["iot_temperature"] > profile.warning_temp_c) & (work["iot_temperature"] <= profile.critical_temp_c)
critical_high = work["iot_temperature"] > profile.critical_temp_c
below_min = work["iot_temperature"] < profile.min_temp_c

k1, k2, k3, k4 = st.columns(4)
k1.metric("Compliance Rate", f"{in_range.mean() * 100:.1f}%", border=True)
k2.metric(f"Critical High (>{profile.critical_temp_c:.1f}°C)", f"{int(critical_high.sum()):,}", border=True)
k3.metric(f"Warning Band ({profile.warning_temp_c:.1f}–{profile.critical_temp_c:.1f}°C)", f"{int(warning_zone.sum()):,}", border=True)
k4.metric(f"Under-Temp (<{profile.min_temp_c:.1f}°C)", f"{int(below_min.sum()):,}", border=True)

ch1, ch2 = st.columns([1.45, 1])
with ch1:
    with st.container(border=True):
        st.subheader("Measured Cargo Temperature vs. Safe Envelope", anchor=False)
        freq = st.segmented_control("Aggregation", ["D", "W", "ME"], default="W", format_func=lambda x: {"D": "Daily", "W": "Weekly", "ME": "Monthly"}[x])
        st.altair_chart(chart_temperature_trend_with_thresholds(work, profile, freq=freq or "W"), width="stretch")

with ch2:
    with st.container(border=True):
        st.subheader("Monthly Excursion Frequency", anchor=False)
        st.altair_chart(chart_excursion_frequency(work, profile), width="stretch")

with st.container(border=True):
    st.subheader("Temperature Excursion Log", anchor=False)
    excursions = work[~in_range].sort_values("timestamp", ascending=False).copy()
    excursions["excursion_type"] = excursions["iot_temperature"].map(
        lambda t: "Critical High Breach" if t > profile.critical_temp_c else "Below Minimum Bound"
    )
    st.caption(f"**{len(excursions):,}** excursion observations detected under `{profile.label}`.")
    st.dataframe(
        excursions.head(500)[
            [
                "record_id",
                "timestamp",
                "corridor_zone",
                "iot_temperature",
                "excursion_type",
                "cargo_condition_status",
                "risk_classification",
                "delay_probability",
            ]
        ],
        column_config={
            "iot_temperature": st.column_config.NumberColumn("Measured °C", format="%.2f"),
            "delay_probability": st.column_config.ProgressColumn("Delay Prob", min_value=0.0, max_value=1.0, format="%.1%"),
        },
        hide_index=True,
    )
