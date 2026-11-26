"""Shared session initialization, top navigation command bar, and sidebar status footer."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

import streamlit as st

from src.analytics import generate_operational_alerts
from src.config import (
    APP_NAME,
    APP_SUBTITLE,
    APP_VERSION,
    ASSETS_DIR,
    COLD_CHAIN_PROFILES,
    ColdChainProfile,
    get_safe_runtime_summary,
)
from src.data_access import (
    check_llm_health,
    check_open_meteo_health,
    check_pinecone_health,
    check_sql_health,
    load_telemetry_data,
)


def init_session_state() -> None:
    """Initialize global Streamlit session state once per user session."""
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = str(uuid.uuid4())

    if "conversations" not in st.session_state:
        first_id = st.session_state.thread_id
        st.session_state.conversations = {
            first_id: {
                "title": "Dispatch Session 1",
                "created_at": datetime.now().strftime("%H:%M"),
                "messages": [],
            }
        }

    st.session_state.setdefault("active_profile_key", "fresh_perishables")
    st.session_state.setdefault("llm_provider", os.getenv("Agent_llm", "OLLAMA").strip().upper())
    default_model_map = {
        "GROQ": os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip(),
        "GEMINI": os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip(),
        "OPENAI": os.getenv("OPENAI_MODEL", "gpt-4o").strip(),
        "DEEPSEEK": os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash").strip(),
        "OLLAMA": os.getenv("OLLAMA_MODEL", "qwen2.5:7b").strip(),
    }
    st.session_state.setdefault(
        "llm_model", default_model_map.get(st.session_state.llm_provider, "qwen2.5:7b")
    )
    st.session_state.setdefault("global_search_query", "")
    st.session_state.setdefault("selected_record_id", None)
    st.session_state.setdefault("pending_dispatcher_prompt", None)
    st.session_state.setdefault("operator_name", "Duty Dispatcher")
    st.session_state.setdefault("admin_authenticated", False)


def get_active_profile() -> ColdChainProfile:
    """Return the active ColdChainProfile object."""
    key = st.session_state.get("active_profile_key", "fresh_perishables")
    return COLD_CHAIN_PROFILES.get(key, COLD_CHAIN_PROFILES["fresh_perishables"])


def render_sidebar_brand_and_status() -> None:
    """Render sidebar top logo/branding and bottom system health metadata."""
    logo_path = ASSETS_DIR / "fde_logo.svg"
    if logo_path.exists():
        st.logo(str(logo_path))

    with st.sidebar:
        st.caption(f"{APP_SUBTITLE} · v{APP_VERSION}")


def render_sidebar_footer(source_info: dict[str, Any]) -> None:
    """Render bottom sidebar status panel without exposing secrets."""
    sql_h = check_sql_health()
    pc_h = check_pinecone_health()
    wx_h = check_open_meteo_health()
    llm_h = check_llm_health(st.session_state.get("llm_provider"))

    with st.sidebar:
        st.markdown("---")
        st.markdown("**System Telemetry & Health**")
        st.caption(f":material/person: **User:** {st.session_state.get('operator_name', 'Duty Dispatcher')}")
        st.caption(
            f":material/psychology: **Active Model:** `{st.session_state.get('llm_provider')}` · "
            f"`{st.session_state.get('llm_model')}`"
        )

        sql_badge = ":green-badge[SQL Live]" if sql_h["ok"] else ":orange-badge[CSV Fallback]"
        pc_badge = ":green-badge[Pinecone OK]" if pc_h["ok"] else ":orange-badge[SOP Local]"
        wx_badge = ":green-badge[Weather OK]" if wx_h["ok"] else ":red-badge[Weather Off]"
        llm_badge = ":green-badge[LLM Ready]" if llm_h["ok"] else ":red-badge[LLM Offline]"
        st.markdown(f"{sql_badge} {pc_badge}")
        st.markdown(f"{wx_badge} {llm_badge}")

        st.caption(f":material/database: Source: {source_info.get('source_label', 'Unknown')}")

        profile_options = list(COLD_CHAIN_PROFILES.keys())
        current_key = st.session_state.get("active_profile_key", "fresh_perishables")
        selected_key = st.selectbox(
            "Cargo Temperature Profile",
            options=profile_options,
            index=profile_options.index(current_key) if current_key in profile_options else 0,
            format_func=lambda k: COLD_CHAIN_PROFILES[k].label,
            key="sidebar_profile_selector",
        )
        if selected_key != current_key:
            st.session_state.active_profile_key = selected_key
            st.rerun()

        if st.button("Refresh Live Checks", icon=":material/refresh:", width="stretch"):
            load_telemetry_data.clear()
            check_sql_health.clear()
            check_pinecone_health.clear()
            check_open_meteo_health.clear()
            check_llm_health.clear()
            st.rerun()


def render_top_command_bar(
    page_title: str,
    section_name: str,
    dispatcher_page: Any,
    fleet_page: Any,
) -> None:
    """Render top navigation bar: title, breadcrumb, search, notifications, AI shortcut, time, user."""
    df, source_info = load_telemetry_data()
    profile = get_active_profile()
    alerts = generate_operational_alerts(df, profile, limit=8) if not df.empty else []

    top_left, top_right = st.columns([1.35, 1.65], vertical_alignment="center")
    with top_left:
        st.caption(f"{APP_NAME} / {section_name} / {page_title}")
        st.title(page_title)

    with top_right:
        with st.container(horizontal=True, horizontal_alignment="right", vertical_alignment="center"):
            search_val = st.text_input(
                "Global search",
                value=st.session_state.get("global_search_query", ""),
                placeholder="Search REC-00001, corridor, High Risk...",
                label_visibility="collapsed",
                key="top_global_search",
                width=230,
            )
            if search_val != st.session_state.get("global_search_query", ""):
                st.session_state.global_search_query = search_val

            if search_val.strip():
                if st.button("Find", icon=":material/search:", key="top_search_go"):
                    st.switch_page(fleet_page)

            with st.popover(f"Alerts ({len(alerts)})", icon=":material/notifications:"):
                st.markdown("**Active Operational Alerts**")
                if not alerts:
                    st.caption("No active SOP threshold violations detected.")
                else:
                    for alert in alerts[:5]:
                        sev = alert["severity"]
                        badge = (
                            ":red-badge[CRITICAL]"
                            if sev == "CRITICAL"
                            else (":orange-badge[HIGH]" if sev == "HIGH" else ":yellow-badge[WARNING]")
                        )
                        st.markdown(f"{badge} **{alert['category']}** · `{alert['record_id']}`")
                        st.caption(alert["summary"])

            if st.button("AI Dispatcher", icon=":material/smart_toy:", type="primary", key="top_ai_btn"):
                st.switch_page(dispatcher_page)

            now_utc = datetime.now(timezone.utc).strftime("%d %b %Y · %H:%M UTC")
            st.caption(f":material/schedule: {now_utc} · :material/account_circle: {st.session_state.get('operator_name')}")
