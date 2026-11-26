from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = PROJECT_ROOT / "data" / "raw" / "dynamic_supply_chain_logistics_dataset.csv"

st.set_page_config(
    page_title="FDE Control Tower",
    page_icon="❄️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@600;700;800&display=swap');
:root { --navy:#07111f; --panel:#101b2b; --panel2:#152238; --cyan:#38bdf8; --green:#34d399; --amber:#fbbf24; --red:#fb7185; }
html, body, [class*="css"] { font-family:'DM Sans',sans-serif; }
.stApp { background: radial-gradient(circle at 85% 10%, #10233b 0, #091423 28%, #07111f 58%); color:#e7eef8; }
section[data-testid="stSidebar"] { background:#091422; border-right:1px solid rgba(148,163,184,.12); }
.block-container { padding-top:1.4rem; padding-bottom:2.5rem; max-width:1500px; }
h1,h2,h3 { font-family:'Manrope',sans-serif; letter-spacing:-.03em; }
.hero { display:flex; justify-content:space-between; align-items:flex-end; padding:.25rem 0 1.35rem; }
.hero h1 { margin:0; font-size:2rem; color:#f8fafc; }
.hero p { margin:.35rem 0 0; color:#8fa1b8; }
.live-pill { border:1px solid rgba(52,211,153,.24); background:rgba(52,211,153,.08); color:#86efac; border-radius:999px; padding:.45rem .75rem; font-size:.78rem; font-weight:700; }
.metric-card { background:linear-gradient(145deg,rgba(21,34,56,.95),rgba(13,25,42,.95)); border:1px solid rgba(148,163,184,.10); border-radius:16px; padding:1rem 1.1rem; min-height:124px; }
.metric-label { color:#91a2b8; font-size:.76rem; font-weight:700; text-transform:uppercase; letter-spacing:.08em; }
.metric-value { color:#f8fafc; font-family:'Manrope'; font-size:1.75rem; font-weight:800; margin:.38rem 0 .15rem; }
.metric-foot { color:#7f92aa; font-size:.78rem; }
.panel { background:rgba(15,27,44,.92); border:1px solid rgba(148,163,184,.10); border-radius:16px; padding:1rem 1rem .65rem; }
.panel-title { color:#f1f5f9; font-weight:750; font-size:.92rem; margin:0 0 .8rem; }
.status-ok { color:#34d399; } .status-warn { color:#fbbf24; } .status-risk { color:#fb7185; }
[data-testid="stMetric"] { background:transparent; }
.stTabs [data-baseweb="tab-list"] { gap:.25rem; }
.stTabs [data-baseweb="tab"] { height:46px; background:transparent; color:#91a2b8; }
.stTabs [aria-selected="true"] { color:#38bdf8; border-bottom-color:#38bdf8; }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data():
    df = pd.read_csv(DATA_PATH)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df

try:
    df = load_data()
except Exception as exc:
    st.error(f"Could not load fleet data: {exc}")
    st.stop()

with st.sidebar:
    st.markdown("## ❄️ **FDE**")
    st.caption("COLD CHAIN CONTROL")
    page = st.radio("Navigation", ["Operations Overview", "Fleet Map", "Shipment Data", "Dispatch Console"], label_visibility="collapsed")
    st.markdown("---")
    st.markdown("**Data source**")
    st.caption("Dynamic supply-chain logistics dataset")
    st.markdown("**Last updated**")
    st.caption(str(df["timestamp"].max().strftime("%d %b %Y · %H:%M")))
    if st.button("↻ Refresh data", width="stretch"):
        st.cache_data.clear()
        st.rerun()

st.markdown('<div class="hero"><div><h1>Cold Chain Operations</h1><p>Live fleet intelligence and incident monitoring</p></div><div class="live-pill">● SYSTEM OPERATIONAL</div></div>', unsafe_allow_html=True)

risk_counts = df["risk_classification"].value_counts()
high_risk = int(risk_counts.get("High Risk", 0))
moderate = int(risk_counts.get("Moderate Risk", 0))
low = int(risk_counts.get("Low Risk", 0))
avg_temp = df["iot_temperature"].mean()
avg_delay = df["eta_variation_hours"].mean()
avg_disruption = df["disruption_likelihood_score"].mean() * 100

def summarize_fleet_context(query: str) -> str:
    """Return concise answers grounded in the loaded logistics dataset."""
    q = query.lower()

    if any(word in q for word in ("high risk", "high-risk", "critical", "danger")):
        subset = df[df["risk_classification"] == "High Risk"]
        hottest = subset.nlargest(5, "iot_temperature")
        worst = subset.nlargest(5, "disruption_likelihood_score")
        return (
            f"**Executive assessment:** {len(subset):,} records are classified as High Risk "
            f"({len(subset) / len(df):.1%} of the monitored fleet).\n\n"
            "**Immediate priorities:**\n"
            f"1. Review shipments with temperatures above **{hottest['iot_temperature'].mean():.1f} °C** on average.\n"
            f"2. Escalate the **{len(worst)}** highest disruption-likelihood movements for rerouting.\n"
            f"3. Prioritize routes where delay probability exceeds **{subset['delay_probability'].quantile(0.90):.1%}**."
        )

    if any(word in q for word in ("temperature", "cold", "perishable", "breach")):
        cold = df[df["iot_temperature"] < 2]
        warm = df[df["iot_temperature"] > 8]
        outliers = df.nlargest(5, "iot_temperature")
        locations = ", ".join(
            f"({row.vehicle_gps_latitude:.2f}, {row.vehicle_gps_longitude:.2f})"
            for row in outliers.itertuples()
        )
        return (
            f"**Temperature review:** Average fleet temperature is **{avg_temp:.1f} °C**. "
            f"**{len(warm):,}** records exceed 8 °C and **{len(cold):,}** are below 2 °C.\n\n"
            "**Recommended action:** Isolate high-temperature cargo, verify sensor calibration, "
            "and preserve a chain-of-custody log before moving or unloading stock.\n"
            f"Highest readings are concentrated near: {locations}."
        )

    if any(word in q for word in ("delay", "late", "eta", "arrival")):
        delayed = df[df["delay_probability"] >= 0.70]
        avg_eta = delayed["eta_variation_hours"].mean()
        return (
            f"**Delay analysis:** {len(delayed):,} shipments have at least 70% predicted delay probability.\n\n"
            f"The affected records show an average ETA variation of **{avg_eta:.1f} hours**. "
            "Coordinate carrier outreach, reallocate available inventory, and update downstream receiving windows."
        )

    if any(word in q for word in ("route", "corridor", "congestion", "port")):
        high_route = df["route_risk_level"].quantile(0.90)
        subset = df[df["route_risk_level"] >= high_route]
        avg_congestion = subset["port_congestion_level"].mean()
        return (
            f"**Corridor assessment:** The route-risk P90 threshold is **{high_route:.2f}**. "
            f"{len(subset):,} movements sit at or above this level, with average port congestion "
            f"of **{avg_congestion:.2f}/10**.\n\n"
            "**Action:** Select an alternate corridor, confirm port appointments, and stage refrigerated trailers for extended dwell."
        )

    if any(word in q for word in ("summary", "overview", "status", "health")):
        return (
            "**Operations snapshot:**\n"
            f"• {len(df):,} monitored shipment records\n"
            f"• {high_risk:,} high-risk movements\n"
            f"• Average temperature: **{avg_temp:.1f} °C**\n"
            f"• Average ETA variation: **{avg_delay:.1f} hours**\n"
            f"• Average disruption probability: **{avg_disruption:.1f}%**\n\n"
            "**Best next step:** Review the high-risk shipments and any temperature readings outside the approved range."
        )

    if any(word in q for word in ("mitigate", "problem", "recommend", "plan", "escalate")):
        return (
            "**Recommended incident response:**\n"
            "1. Isolate affected cargo and confirm the physical sensor reading.\n"
            "2. Capture temperature, route, dwell, and driver context.\n"
            "3. Escalate High Risk movements to the duty dispatcher.\n"
            "4. Re-route through the lowest-risk corridor if transit is safe.\n"
            "5. Notify receiving, quality, and customer teams before arrival.\n"
            "6. Record corrective actions and retain evidence in the audit trail."
        )

    return (
        "I can answer from the current fleet dataset. Try asking about high-risk shipments, "
        "temperature breaches, ETA delays, corridor congestion, or an incident-response plan."
    )

if page == "Operations Overview":
    c1, c2, c3, c4, c5 = st.columns(5)
    cards = [
        ("ACTIVE SHIPMENTS", f"{len(df):,}", "Across monitored routes", "status-ok"),
        ("AVG. TEMPERATURE", f"{avg_temp:.1f} °C", "IoT sensor network", "status-warn"),
        ("HIGH RISK", f"{high_risk:,}", f"{high_risk / len(df):.1%} of fleet", "status-risk"),
        ("AVG. DELAY", f"{avg_delay:.1f} hrs", "Estimated arrival variance", "status-warn"),
        ("DISRUPTION RISK", f"{avg_disruption:.1f}%", "Predicted fleet exposure", "status-risk"),
    ]
    for col, (label, value, foot, cls) in zip([c1,c2,c3,c4,c5], cards):
        with col:
            st.markdown(f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value {cls}">{value}</div><div class="metric-foot">{foot}</div></div>', unsafe_allow_html=True)

    left, right = st.columns([1.45, 1])
    with left:
        st.markdown('<div class="panel"><div class="panel-title">Risk distribution over time</div></div>', unsafe_allow_html=True)
        trend = df.set_index("timestamp").resample("D")[["disruption_likelihood_score", "delay_probability"]].mean().reset_index()
        trend["Disruption risk"] = trend["disruption_likelihood_score"] * 100
        trend["Delay probability"] = trend["delay_probability"] * 100
        st.line_chart(trend.set_index("timestamp")[["Disruption risk", "Delay probability"]], height=280, color=["#38bdf8", "#fb7185"])
    with right:
        st.markdown('<div class="panel"><div class="panel-title">Fleet risk profile</div></div>', unsafe_allow_html=True)
        risk_df = risk_counts.rename_axis("Risk").reset_index(name="Shipments")
        st.bar_chart(risk_df.set_index("Risk"), height=280, color="#34d399")

    st.markdown("<div style='height:.35rem'></div>", unsafe_allow_html=True)
    bottom_left, bottom_right = st.columns([1.2, 1])
    with bottom_left:
        st.markdown('<div class="panel"><div class="panel-title">Route risk vs. temperature</div></div>', unsafe_allow_html=True)
        scatter = df[["route_risk_level", "iot_temperature", "risk_classification"]].tail(2500)
        scatter.columns = ["Route risk", "Temperature", "Classification"]
        st.scatter_chart(scatter, x="Route risk", y="Temperature", color="Classification", height=310)
    with bottom_right:
        st.markdown('<div class="panel"><div class="panel-title">Operational health</div></div>', unsafe_allow_html=True)
        health = pd.DataFrame({
            "Area": ["Fleet coverage", "Temperature monitoring", "Route reliability", "Inventory availability", "Supplier reliability"],
            "Score": [
                min(len(df) / 320, 100),
                df["cargo_condition_status"].mean() * 100,
                (1 - df["route_risk_level"].mean() / 10) * 100,
                df["warehouse_inventory_level"].mean() / 10,
                df["supplier_reliability_score"].mean() * 100,
            ],
        })
        st.dataframe(health, hide_index=True, use_container_width=True, height=310)

elif page == "Fleet Map":
    map_df = df[["vehicle_gps_latitude", "vehicle_gps_longitude", "risk_classification", "iot_temperature"]].copy()
    map_df.columns = ["lat", "lon", "Risk", "Temperature"]
    st.markdown('<div class="panel"><div class="panel-title">Fleet positions</div></div>', unsafe_allow_html=True)
    st.map(map_df, latitude="lat", longitude="lon", size=4, zoom=3)
    f1, f2, f3 = st.columns(3)
    f1.metric("High-risk vehicles", f"{high_risk:,}")
    f2.metric("Moderate-risk vehicles", f"{moderate:,}")
    f3.metric("Low-risk vehicles", f"{low:,}")

elif page == "Shipment Data":
    c1, c2, c3 = st.columns([1, 1, 2])
    risk_filter = c1.selectbox("Risk classification", ["All", *sorted(df["risk_classification"].dropna().unique())])
    temp_min, temp_max = c2.slider("Temperature range (°C)", float(df["iot_temperature"].min()), float(df["iot_temperature"].max()), (float(df["iot_temperature"].min()), float(df["iot_temperature"].max())))
    search = c3.text_input("Search", placeholder="Filter the shipment table")

    filtered = df.copy()
    if risk_filter != "All":
        filtered = filtered[filtered["risk_classification"] == risk_filter]
    filtered = filtered[(filtered["iot_temperature"] >= temp_min) & (filtered["iot_temperature"] <= temp_max)]

    st.markdown(f"**{len(filtered):,} shipments**")
    visible = filtered[["timestamp", "vehicle_gps_latitude", "vehicle_gps_longitude", "iot_temperature", "cargo_condition_status", "route_risk_level", "delay_probability", "risk_classification"]].copy()
    visible.columns = ["Timestamp", "Latitude", "Longitude", "Temperature °C", "Cargo status", "Route risk", "Delay probability", "Risk"]
    st.dataframe(visible, width="stretch", hide_index=True, height=560)

else:
    st.markdown('<div class="panel"><div class="panel-title">FDE Operations Copilot</div></div>', unsafe_allow_html=True)

    if "copilot_messages" not in st.session_state:
        st.session_state.copilot_messages = [
            {
                "role": "assistant",
                "content": "I’m ready to analyze the loaded fleet dataset. Choose a scenario below or ask a problem-solving question.",
            }
        ]

    c_main, c_context = st.columns([1.7, 1], gap="large")

    with c_context:
        st.markdown("#### Suggested scenarios")
        suggestions = [
            "Which shipments are high risk and what should we do?",
            "Are there temperature breaches across the fleet?",
            "Which corridors are likely to cause delays?",
            "Give me an incident-response plan.",
            "Summarize current cold-chain operations status.",
        ]
        for suggestion in suggestions:
            if st.button(suggestion, width="stretch", key=f"q_{suggestion}"):
                st.session_state.copilot_messages.append({"role": "user", "content": suggestion})
                st.session_state.copilot_messages.append({"role": "assistant", "content": summarize_fleet_context(suggestion)})
                st.rerun()

        st.markdown("#### Fleet snapshot")
        st.metric("High-risk records", f"{high_risk:,}")
        st.metric("Average temperature", f"{avg_temp:.1f} °C")
        st.metric("Average disruption risk", f"{avg_disruption:.1f}%")

    with c_main:
        chat_box = st.container(height=470)
        with chat_box:
            for message in st.session_state.copilot_messages:
                st.chat_message(message["role"], avatar="🧊" if message["role"] == "assistant" else "👤").write(message["content"])

        prompt = st.chat_input("Ask an operations or problem-solving question...")
        if prompt:
            st.session_state.copilot_messages.append({"role": "user", "content": prompt})
            answer = summarize_fleet_context(prompt)
            st.session_state.copilot_messages.append({"role": "assistant", "content": answer})
            st.rerun()
