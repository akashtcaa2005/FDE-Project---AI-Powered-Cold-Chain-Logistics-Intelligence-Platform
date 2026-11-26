"""Weather Intelligence — Live Open-Meteo conditions, forecasts, and derived corridor risk."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.charts import chart_weather_forecast
from src.config import CORRIDOR_HUBS
from src.data_access import check_open_meteo_health, fetch_corridor_weather

wx_health = check_open_meteo_health()

h1, h2 = st.columns([2.2, 1], vertical_alignment="center")
with h1:
    st.caption(
        "Live atmospheric observations retrieved from **Open-Meteo REST API** (`current_weather` + 24h hourly forecast). "
        "Observed API metrics are strictly separated from FDE derived corridor disruption calculations."
    )
with h2:
    with st.container(horizontal=True, horizontal_alignment="right"):
        if wx_health["ok"]:
            st.badge("Open-Meteo Connected", icon=":material/check_circle:", color="green")
        else:
            st.badge("Open-Meteo Offline", icon=":material/error:", color="red")

if not wx_health["ok"]:
    st.error(f"Open-Meteo API connectivity failed: {wx_health['detail']}")

# ==========================================
# MULTI-HUB LIVE WEATHER MATRIX
# ==========================================
with st.container(border=True):
    st.subheader("Live Corridor Hub Weather Matrix", anchor=False)
    hub_rows = []
    snapshots = {}
    for hub in CORRIDOR_HUBS:
        snap = fetch_corridor_weather(hub.latitude, hub.longitude)
        snapshots[hub.code] = snap
        hub_rows.append(
            {
                "Code": hub.code,
                "Corridor Hub": hub.name,
                "Lat": hub.latitude,
                "Lon": hub.longitude,
                "Observed Temp (°C)": snap["observed_temp_c"],
                "Observed Wind (km/h)": snap["observed_wind_kmh"],
                "Observation Time (UTC)": snap["observed_time"] or "N/A",
                "Derived Congestion Index": f"{snap['derived_congestion_index']}/10" if snap["ok"] else "N/A",
                "Derived Corridor Status": snap["derived_status"],
            }
        )

    st.dataframe(
        pd.DataFrame(hub_rows),
        column_config={
            "Observed Temp (°C)": st.column_config.NumberColumn(format="%.1f °C"),
            "Observed Wind (km/h)": st.column_config.NumberColumn(format="%.1f km/h"),
        },
        hide_index=True,
    )

st.space("small")

# ==========================================
# HUB FORECAST OR CUSTOM GPS LOOKUP
# ==========================================
left_col, right_col = st.columns([1, 1.45])

with left_col:
    with st.container(border=True):
        st.subheader("Corridor Coordinate Inspector", anchor=False)
        mode = st.segmented_control("Coordinate Source", ["Reference Hub", "Custom GPS"], default="Reference Hub")
        if mode == "Reference Hub":
            hub_codes = [h.code for h in CORRIDOR_HUBS]
            sel_code = st.selectbox(
                "Select Corridor Hub",
                hub_codes,
                format_func=lambda c: next(f"{h.code} — {h.name}" for h in CORRIDOR_HUBS if h.code == c),
            )
            hub_obj = next(h for h in CORRIDOR_HUBS if h.code == sel_code)
            target_lat, target_lon = hub_obj.latitude, hub_obj.longitude
            target_label = hub_obj.name
        else:
            with st.form("custom_wx_form"):
                target_lat = st.number_input("Latitude", min_value=-90.0, max_value=90.0, value=33.77, step=0.1)
                target_lon = st.number_input("Longitude", min_value=-180.0, max_value=180.0, value=-118.19, step=0.1)
                st.form_submit_button("Fetch Live Weather", icon=":material/cloud_sync:", width="stretch")
            target_label = f"Custom ({target_lat:.2f}, {target_lon:.2f})"

        active_snap = fetch_corridor_weather(float(target_lat), float(target_lon))
        if active_snap["ok"]:
            st.markdown("##### Observed Open-Meteo Telemetry")
            m1, m2 = st.columns(2)
            m1.metric("External Temp", f"{active_snap['observed_temp_c']:.1f} °C")
            m2.metric("Wind Speed", f"{active_snap['observed_wind_kmh']:.1f} km/h")
            st.caption(f"Observed at `{active_snap['observed_time']}` UTC")

            st.markdown("##### Derived Operational Risk (FDE Rule)")
            st.info(
                f"**Status:** {active_snap['derived_status']} · "
                f"**Congestion Index:** `{active_snap['derived_congestion_index']}/10` "
                "(Rule: wind > 10.0 km/h elevates index from 2.5 to 8.5).",
                icon=":material/analytics:",
            )
        else:
            st.error(f"Failed to retrieve weather for {target_label}: {active_snap['error']}")

with right_col:
    with st.container(border=True):
        st.subheader(f"24-Hour Temperature & Wind Forecast — {target_label}", anchor=False)
        if active_snap["ok"] and not active_snap["hourly_df"].empty:
            st.altair_chart(chart_weather_forecast(active_snap["hourly_df"]), width="stretch")
        else:
            st.info("Hourly forecast chart unavailable for this request.")
