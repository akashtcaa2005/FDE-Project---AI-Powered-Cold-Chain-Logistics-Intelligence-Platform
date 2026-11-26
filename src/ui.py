"""FDE Intelligence — Enterprise Cold Chain Command Center Entry Point."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

st.set_page_config(
    page_title="FDE Intelligence — Cold Chain Command Center",
    page_icon=":material/ac_unit:",
    layout="wide",
    initial_sidebar_state="expanded",
)

from src.components.shell import (  # noqa: E402
    init_session_state,
    render_sidebar_brand_and_status,
    render_sidebar_footer,
    render_top_command_bar,
)
from src.config import APP_PAGES_DIR  # noqa: E402
from src.data_access import load_telemetry_data  # noqa: E402

init_session_state()
render_sidebar_brand_and_status()

p_overview = st.Page(str(APP_PAGES_DIR / "overview.py"), title="Overview", icon=":material/space_dashboard:", default=True)
p_live_fleet = st.Page(str(APP_PAGES_DIR / "live_fleet.py"), title="Live Fleet", icon=":material/local_shipping:")
p_shipments = st.Page(str(APP_PAGES_DIR / "shipment_intel.py"), title="Shipment Intelligence", icon=":material/inventory_2:")
p_cold_chain = st.Page(str(APP_PAGES_DIR / "cold_chain.py"), title="Cold Chain Monitoring", icon=":material/thermostat:")
p_routes = st.Page(str(APP_PAGES_DIR / "route_intel.py"), title="Route Intelligence", icon=":material/alt_route:")
p_weather = st.Page(str(APP_PAGES_DIR / "weather_intel.py"), title="Weather Intelligence", icon=":material/cloud:")
p_dispatcher = st.Page(str(APP_PAGES_DIR / "ai_dispatcher.py"), title="AI Dispatcher", icon=":material/smart_toy:")
p_analytics = st.Page(str(APP_PAGES_DIR / "analytics.py"), title="Analytics", icon=":material/analytics:")
p_sop_kb = st.Page(str(APP_PAGES_DIR / "sop_kb.py"), title="SOP Knowledge Base", icon=":material/menu_book:")
p_audit = st.Page(str(APP_PAGES_DIR / "audit_center.py"), title="Audit Center", icon=":material/security:")
p_settings = st.Page(str(APP_PAGES_DIR / "settings.py"), title="Settings", icon=":material/settings:")

st.session_state["_page_refs"] = {
    "overview": p_overview,
    "live_fleet": p_live_fleet,
    "shipments": p_shipments,
    "cold_chain": p_cold_chain,
    "routes": p_routes,
    "weather": p_weather,
    "ai_dispatcher": p_dispatcher,
    "analytics": p_analytics,
    "sop_kb": p_sop_kb,
    "audit": p_audit,
    "settings": p_settings,
}

SECTION_MAP = {
    "Overview": "Command",
    "Live Fleet": "Operations",
    "Shipment Intelligence": "Operations",
    "Cold Chain Monitoring": "Operations",
    "Route Intelligence": "Operations",
    "Weather Intelligence": "Operations",
    "AI Dispatcher": "Intelligence & AI",
    "Analytics": "Intelligence & AI",
    "SOP Knowledge Base": "Intelligence & AI",
    "Audit Center": "Governance",
    "Settings": "Governance",
}

current_page = st.navigation(
    {
        "Command": [p_overview],
        "Operations": [p_live_fleet, p_shipments, p_cold_chain, p_routes, p_weather],
        "Intelligence & AI": [p_dispatcher, p_analytics, p_sop_kb],
        "Governance": [p_audit, p_settings],
    },
    position="sidebar",
)

_, source_info = load_telemetry_data()
render_top_command_bar(
    page_title=current_page.title,
    section_name=SECTION_MAP.get(current_page.title, "Command"),
    dispatcher_page=p_dispatcher,
    fleet_page=p_live_fleet,
)
render_sidebar_footer(source_info)

current_page.run()
