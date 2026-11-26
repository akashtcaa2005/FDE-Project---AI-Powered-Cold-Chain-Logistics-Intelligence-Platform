"""Shipment Intelligence — Search, risk/delay filtering, analytics, and report exports."""

from __future__ import annotations

import streamlit as st

from src.charts import chart_delay_probability_hist, chart_delivery_performance_trend
from src.components.shell import get_active_profile
from src.config import SOP_DELAY_ESCALATION_THRESHOLD
from src.data_access import load_telemetry_data

df, source_info = load_telemetry_data()
profile = get_active_profile()

if df.empty:
    st.error("Telemetry dataset unavailable.")
    st.stop()

st.caption(
    f"Source: **{source_info['source_label']}**. Schema transparency: `FDE_VIEWS.VW_ACTIVE_FLEET` exposes "
    "9 telemetry fields; extended cost/ETA/fulfillment metrics appear automatically when loaded from the CSV dataset."
)

# ==========================================
# SEARCH & FILTERS
# ==========================================
with st.container(border=True):
    c1, c2, c3, c4 = st.columns([1.4, 1, 1, 1.2])
    q_default = st.session_state.get("global_search_query", "")
    search_q = c1.text_input("Search Record or Corridor", value=q_default, placeholder="REC-00100, Midwest...", key="ship_search")
    risk_f = c2.multiselect(
        "Risk Classification",
        ["High Risk", "Moderate Risk", "Low Risk"],
        default=["High Risk", "Moderate Risk", "Low Risk"],
        key="ship_risk_multi",
    )
    min_delay = c3.slider("Min Delay Probability", 0.0, 1.0, 0.0, 0.05, key="ship_min_delay")
    corridor_f = c4.selectbox("Corridor Zone", ["All", *sorted(df["corridor_zone"].unique())], key="ship_corridor")

filtered = df[df["risk_classification"].isin(risk_f) & (df["delay_probability"] >= min_delay)].copy()
if corridor_f != "All":
    filtered = filtered[filtered["corridor_zone"] == corridor_f]
if search_q.strip():
    s = search_q.strip().lower()
    filtered = filtered[
        filtered["record_id"].str.lower().str.contains(s, na=False)
        | filtered["corridor_zone"].str.lower().str.contains(s, na=False)
        | filtered["risk_classification"].str.lower().str.contains(s, na=False)
    ]

if filtered.empty:
    st.warning("No movement records match these filters.")
    st.stop()

# ==========================================
# SHIPMENT KPI STRIP
# ==========================================
m1, m2, m3, m4 = st.columns(4)
m1.metric("Filtered Movements", f"{len(filtered):,}", border=True)
m2.metric("SOP §3 Delay Escalations (>65%)", f"{int((filtered['delay_probability'] > SOP_DELAY_ESCALATION_THRESHOLD).sum()):,}", border=True)
m3.metric("Mean Delay Probability", f"{filtered['delay_probability'].mean():.1%}", border=True)
if "eta_variation_hours" in filtered.columns:
    m4.metric("Mean ETA Variation", f"{filtered['eta_variation_hours'].mean():.2f} hrs", border=True)
else:
    m4.metric("Mean Cargo Condition", f"{filtered['cargo_condition_status'].mean():.3f}", border=True)

# ==========================================
# DELIVERY PERFORMANCE ANALYTICS
# ==========================================
ch1, ch2 = st.columns(2)
with ch1:
    with st.container(border=True):
        st.subheader("Delivery & Readiness Performance", anchor=False)
        st.altair_chart(chart_delivery_performance_trend(filtered), width="stretch")
with ch2:
    with st.container(border=True):
        st.subheader("Delay Probability Distribution", anchor=False)
        st.altair_chart(chart_delay_probability_hist(filtered), width="stretch")

# ==========================================
# SHIPMENT TABLE + EXPORT + DETAIL VIEW
# ==========================================
with st.container(border=True):
    h_l, h_r = st.columns([2, 1], vertical_alignment="center")
    with h_l:
        st.subheader("Shipment Telemetry Records", anchor=False)
    with h_r:
        with st.container(horizontal=True, horizontal_alignment="right"):
            st.download_button(
                "Export CSV",
                data=filtered.head(5000).to_csv(index=False),
                file_name="fde_shipments_filtered.csv",
                mime="text/csv",
                icon=":material/download:",
            )

    page_size = 25
    num_pages = max(1, (len(filtered) + page_size - 1) // page_size)
    table_slot = st.empty()
    with st.container(horizontal=True, horizontal_alignment="right"):
        cur_page = st.pagination(num_pages, key="ship_table_page")

    start = (cur_page - 1) * page_size
    page_df = filtered.iloc[start : start + page_size].copy()

    cols = [
        "record_id",
        "timestamp",
        "corridor_zone",
        "risk_classification",
        "iot_temperature",
        "delay_probability",
        "route_risk_level",
        "cargo_condition_status",
    ]
    for extra in ("eta_variation_hours", "order_fulfillment_status", "shipping_costs", "lead_time_days"):
        if extra in page_df.columns:
            cols.append(extra)

    sel = table_slot.dataframe(
        page_df[cols],
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="ship_df_widget",
    )

    detail_id = page_df.iloc[sel.selection.rows[0]]["record_id"] if sel.selection.rows else page_df.iloc[0]["record_id"]
    rec = filtered[filtered["record_id"] == detail_id].iloc[0]

    with st.expander(f"Detailed Inspection — {rec['record_id']} ({rec['corridor_zone']})", expanded=True):
        d1, d2, d3 = st.columns(3)
        d1.write(f"**Timestamp:** `{rec['timestamp']}`")
        d1.write(f"**GPS:** `{rec['vehicle_gps_latitude']:.4f}, {rec['vehicle_gps_longitude']:.4f}`")
        d2.write(f"**Temperature:** `{rec['iot_temperature']:.2f} °C`")
        d2.write(f"**Risk Class:** `{rec['risk_classification']}`")
        d3.write(f"**Delay Prob:** `{rec['delay_probability']:.1%}`")
        d3.write(f"**Route Risk:** `{rec['route_risk_level']:.2f} / 10`")
        if "shipping_costs" in rec.index:
            st.caption(
                f"Extended Metrics — ETA Variation: `{rec['eta_variation_hours']:.2f}h` | "
                f"Order Fulfillment: `{rec['order_fulfillment_status']:.2%}` | "
                f"Shipping Cost: `${rec['shipping_costs']:.2f}` | Lead Time: `{rec['lead_time_days']:.1f}d`"
            )
