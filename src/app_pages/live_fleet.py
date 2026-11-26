"""Live Fleet Intelligence — Geospatial map, filters, inspector, and paginated table."""

from __future__ import annotations

import streamlit as st

from src.charts import build_fleet_pydeck
from src.components.shell import get_active_profile
from src.config import SOP_DELAY_ESCALATION_THRESHOLD, SOP_PORT_CONGESTION_CRITICAL
from src.data_access import fetch_corridor_weather, load_telemetry_data

df, source_info = load_telemetry_data()
profile = get_active_profile()

if df.empty:
    st.error("Fleet telemetry unavailable.")
    st.stop()

st.caption(
    f"Source: **{source_info['source_label']}** · Loaded `{source_info['loaded_at']}`. "
    "Note: Telemetry coordinates represent observed records from `FDE_VIEWS.VW_ACTIVE_FLEET` rather than live hardware GPS streams."
)

# ==========================================
# FILTERS BAR
# ==========================================
with st.container(border=True):
    f1, f2, f3, f4 = st.columns([1.3, 1.1, 1.2, 1.4])
    search_default = st.session_state.get("global_search_query", "")
    search_text = f1.text_input(
        "Search Record / Corridor / Risk",
        value=search_default,
        placeholder="REC-00012 or California...",
        key="fleet_search_input",
    )
    risk_opts = ["All", "High Risk", "Moderate Risk", "Low Risk"]
    risk_sel = f2.selectbox("Risk Classification", risk_opts, key="fleet_risk_filter")

    temp_status_sel = f3.selectbox(
        "Temperature Status",
        ["All", "Within Safe Range", f"High Breach (>{profile.critical_temp_c:.1f}°C)", f"Below Min (<{profile.min_temp_c:.1f}°C)"],
        key="fleet_temp_filter",
    )

    corridor_opts = ["All", *sorted(df["corridor_zone"].unique().tolist())]
    corridor_sel = f4.selectbox("Corridor Zone", corridor_opts, key="fleet_corridor_filter")

filtered = df.copy()
if risk_sel != "All":
    filtered = filtered[filtered["risk_classification"] == risk_sel]
if corridor_sel != "All":
    filtered = filtered[filtered["corridor_zone"] == corridor_sel]
if temp_status_sel == "Within Safe Range":
    filtered = filtered[
        (filtered["iot_temperature"] >= profile.min_temp_c)
        & (filtered["iot_temperature"] <= profile.critical_temp_c)
    ]
elif temp_status_sel.startswith("High Breach"):
    filtered = filtered[filtered["iot_temperature"] > profile.critical_temp_c]
elif temp_status_sel.startswith("Below Min"):
    filtered = filtered[filtered["iot_temperature"] < profile.min_temp_c]

if search_text.strip():
    q = search_text.strip().lower()
    mask = (
        filtered["record_id"].str.lower().str.contains(q, na=False)
        | filtered["corridor_zone"].str.lower().str.contains(q, na=False)
        | filtered["risk_classification"].str.lower().str.contains(q, na=False)
    )
    filtered = filtered[mask]

st.caption(f"Showing **{len(filtered):,}** matching telemetry observations (of {len(df):,} total).")

if filtered.empty:
    st.warning("No telemetry records match the selected filters. Adjust filters above to inspect fleet records.")
    st.stop()

# ==========================================
# MAP + SELECTED RECORD INSPECTOR
# ==========================================
map_col, detail_col = st.columns([1.65, 1], gap="medium")

with map_col:
    with st.container(border=True):
        st.subheader("Geospatial Fleet Distribution", anchor=False)
        st.caption("Rendering latest 1,200 filtered points · Hover any marker for telemetry")
        st.pydeck_chart(build_fleet_pydeck(filtered, max_points=1200), height=440)

with detail_col:
    with st.container(border=True):
        st.subheader("Telemetry Record Inspector", anchor=False)
        available_ids = filtered["record_id"].tail(300).iloc[::-1].tolist()
        default_id = st.session_state.get("selected_record_id")
        if default_id not in available_ids:
            default_id = available_ids[0]

        picked_id = st.selectbox(
            "Inspect Observation",
            options=available_ids,
            index=available_ids.index(default_id),
            key="fleet_inspector_select",
        )
        st.session_state.selected_record_id = picked_id
        rec = filtered[filtered["record_id"] == picked_id].iloc[0]

        risk_val = rec["risk_classification"]
        badge = (
            ":red-badge[High Risk]"
            if risk_val == "High Risk"
            else (":orange-badge[Moderate Risk]" if risk_val == "Moderate Risk" else ":green-badge[Low Risk]")
        )
        st.markdown(f"**{rec['record_id']}** · {badge} · `{rec['corridor_zone']}`")
        st.caption(f"Last Telemetry Timestamp: `{rec['timestamp']}`")

        m1, m2 = st.columns(2)
        m1.metric("Cargo Temp", f"{rec['iot_temperature']:.2f} °C")
        m2.metric("Delay Probability", f"{rec['delay_probability']:.1%}")
        m3, m4 = st.columns(2)
        m3.metric("Route Risk Index", f"{rec['route_risk_level']:.2f} / 10")
        m4.metric("Port Congestion", f"{rec['port_congestion_level']:.2f} / 10")

        st.markdown(
            f"- **GPS Coordinates:** `{rec['vehicle_gps_latitude']:.4f}, {rec['vehicle_gps_longitude']:.4f}`\n"
            f"- **Cargo Condition Code:** `{rec['cargo_condition_status']:.3f}`"
        )

        if rec["iot_temperature"] > profile.critical_temp_c:
            st.error(f"SOP §1 Breach: Temp exceeds {profile.critical_temp_c:.1f}°C.", icon=":material/warning:")
        elif rec["port_congestion_level"] > SOP_PORT_CONGESTION_CRITICAL:
            st.warning("SOP §2 Trigger: Port congestion > 7.0 (divert to San Bernardino).", icon=":material/alt_route:")
        elif risk_val == "High Risk" and rec["delay_probability"] > SOP_DELAY_ESCALATION_THRESHOLD:
            st.warning("SOP §3 Escalation: High Risk + Delay Prob > 65%.", icon=":material/priority_high:")

        if st.button("Fetch Live Weather at GPS", icon=":material/cloud:", width="stretch"):
            wx = fetch_corridor_weather(float(rec["vehicle_gps_latitude"]), float(rec["vehicle_gps_longitude"]))
            if wx["ok"]:
                st.info(
                    f"Open-Meteo Observed: **{wx['observed_temp_c']}°C**, Wind **{wx['observed_wind_kmh']} km/h** "
                    f"({wx['derived_status']})."
                )
            else:
                st.error(f"Weather API error: {wx['error']}")

        if st.button("Analyze in AI Dispatcher", icon=":material/smart_toy:", type="primary", width="stretch"):
            st.session_state.pending_dispatcher_prompt = (
                f"Analyze telemetry near Lat {rec['vehicle_gps_latitude']:.2f}, Lon {rec['vehicle_gps_longitude']:.2f} "
                f"({rec['record_id']}, Temp {rec['iot_temperature']:.1f}°C, Risk {risk_val}). "
                "Check live corridor weather and provide SOP compliance actions."
            )
            st.switch_page(st.session_state["_page_refs"]["ai_dispatcher"])

st.space("small")

# ==========================================
# SORTABLE & PAGINATED FLEET TABLE
# ==========================================
with st.container(border=True):
    st.subheader("Fleet Telemetry Ledger", anchor=False)
    sort_col1, sort_col2 = st.columns([1.2, 1])
    sort_by = sort_col1.selectbox(
        "Sort by",
        ["timestamp", "iot_temperature", "delay_probability", "route_risk_level", "port_congestion_level"],
        key="fleet_sort_col",
    )
    sort_asc = sort_col2.segmented_control("Order", ["Descending", "Ascending"], default="Descending") == "Ascending"

    sorted_df = filtered.sort_values(sort_by, ascending=sort_asc).reset_index(drop=True)
    page_size = 25
    num_pages = max(1, (len(sorted_df) + page_size - 1) // page_size)

    table_slot = st.empty()
    with st.container(horizontal=True, horizontal_alignment="right"):
        cur_page = st.pagination(num_pages, key="fleet_table_page")

    start = (cur_page - 1) * page_size
    page_df = sorted_df.iloc[start : start + page_size].copy()

    display_cols = [
        "record_id",
        "timestamp",
        "corridor_zone",
        "vehicle_gps_latitude",
        "vehicle_gps_longitude",
        "iot_temperature",
        "cargo_condition_status",
        "risk_classification",
        "delay_probability",
        "port_congestion_level",
        "route_risk_level",
    ]
    event = table_slot.dataframe(
        page_df[display_cols],
        column_config={
            "record_id": st.column_config.TextColumn("Record ID", pinned=True),
            "timestamp": st.column_config.DatetimeColumn("Timestamp", format="YYYY-MM-DD HH:mm"),
            "corridor_zone": "Corridor Zone",
            "vehicle_gps_latitude": st.column_config.NumberColumn("Lat", format="%.3f"),
            "vehicle_gps_longitude": st.column_config.NumberColumn("Lon", format="%.3f"),
            "iot_temperature": st.column_config.NumberColumn("Temp (°C)", format="%.2f"),
            "cargo_condition_status": st.column_config.NumberColumn("Cargo Cond.", format="%.3f"),
            "risk_classification": "Risk Class",
            "delay_probability": st.column_config.ProgressColumn("Delay Prob", min_value=0.0, max_value=1.0, format="%.1%"),
            "port_congestion_level": st.column_config.NumberColumn("Port Cong.", format="%.2f"),
            "route_risk_level": st.column_config.NumberColumn("Route Risk", format="%.2f"),
        },
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="fleet_ledger_df",
    )
    if event.selection.rows:
        sel_idx = event.selection.rows[0]
        clicked_id = page_df.iloc[sel_idx]["record_id"]
        if clicked_id != st.session_state.get("selected_record_id"):
            st.session_state.selected_record_id = clicked_id
            st.rerun()
