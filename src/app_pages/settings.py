"""Settings & System Health — Subsystem diagnostics, model selection, and security posture."""

from __future__ import annotations

import streamlit as st

from src.config import COLD_CHAIN_PROFILES, get_safe_runtime_summary
from src.data_access import (
    check_llm_health,
    check_open_meteo_health,
    check_pinecone_health,
    check_sql_health,
    load_telemetry_data,
)

summary = get_safe_runtime_summary()
_, source_info = load_telemetry_data()

sql_h = check_sql_health()
pc_h = check_pinecone_health()
wx_h = check_open_meteo_health()
llm_h = check_llm_health(st.session_state.get("llm_provider"))

# ==========================================
# SYSTEM HEALTH MATRIX
# ==========================================
h_l, h_r = st.columns([2, 1], vertical_alignment="center")
with h_l:
    st.subheader("Subsystem Connectivity & Health", anchor=False)
with h_r:
    with st.container(horizontal=True, horizontal_alignment="right"):
        if st.button("Run Live Health Checks", icon=":material/refresh:", type="primary"):
            check_sql_health.clear()
            check_pinecone_health.clear()
            check_open_meteo_health.clear()
            check_llm_health.clear()
            load_telemetry_data.clear()
            st.rerun()

c1, c2, c3, c4 = st.columns(4)
with c1:
    with st.container(border=True):
        st.markdown("**Microsoft SQL Server**")
        st.markdown(":green-badge[Connected]" if sql_h["ok"] else f":orange-badge[{sql_h['status']}]")
        st.caption(sql_h["detail"])
with c2:
    with st.container(border=True):
        st.markdown("**Pinecone Vector DB**")
        st.markdown(":green-badge[Connected]" if pc_h["ok"] else f":orange-badge[{pc_h['status']}]")
        st.caption(pc_h["detail"])
with c3:
    with st.container(border=True):
        st.markdown("**Open-Meteo Weather API**")
        st.markdown(":green-badge[Connected]" if wx_h["ok"] else f":red-badge[{wx_h['status']}]")
        st.caption(wx_h["detail"])
with c4:
    with st.container(border=True):
        st.markdown("**LangGraph AI Reasoner**")
        st.markdown(":green-badge[Ready]" if llm_h["ok"] else f":red-badge[{llm_h['status']}]")
        st.caption(llm_h["detail"])

st.space("small")

# ==========================================
# SAFE RUNTIME CONFIGURATION
# ==========================================
left_col, right_col = st.columns(2)

with left_col:
    with st.container(border=True):
        st.subheader("AI Dispatcher Model Configuration", anchor=False)
        st.caption("Runtime session override (credentials remain strictly inside server-side `.env`).")

        providers = ["GROQ", "GEMINI", "OPENAI", "DEEPSEEK", "OLLAMA"]
        cur_provider = st.session_state.get("llm_provider", summary["agent_llm"])
        sel_provider = st.selectbox(
            "Reasoning Provider",
            providers,
            index=providers.index(cur_provider) if cur_provider in providers else 0,
        )

        suggested_models = {
            "GROQ": ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"],
            "GEMINI": ["gemini-3.8-flash", "gemini-flash-latest", "gemini-pro-latest"],
            "OPENAI": ["gpt-4o", "gpt-4o-mini"],
            "DEEPSEEK": ["deepseek-v4-flash", "deepseek-v4-pro"],
            "OLLAMA": ["qwen2.5:7b", "llama3.1:8b"],
        }
        default_m = suggested_models[sel_provider][0]
        cur_m = st.session_state.get("llm_model", default_m)
        model_input = st.text_input(
            "Model Identifier",
            value=cur_m if sel_provider == cur_provider else default_m,
            help=f"Suggested for {sel_provider}: {', '.join(suggested_models[sel_provider])}",
        )

        if st.button("Apply Model Setting", icon=":material/check:", type="primary"):
            st.session_state.llm_provider = sel_provider
            st.session_state.llm_model = model_input.strip() or default_m
            check_llm_health.clear()
            st.success(f"Active AI Dispatcher updated to `{sel_provider}` / `{st.session_state.llm_model}`.")
            st.rerun()

with right_col:
    with st.container(border=True):
        st.subheader("Platform Metadata & Security Posture", anchor=False)
        st.markdown(
            f"- **Application:** `{summary['app_name']}` (`v{summary['app_version']}`)\n"
            f"- **Telemetry Source:** `{source_info['source_label']}`\n"
            f"- **Embedding Mode:** `{summary['embeddings_mode']}` (`{summary['local_embedding_model']}`)\n"
            f"- **SQL Target:** `{summary['sql_host']}:{summary['sql_port']}` · Agent User: `{summary['sql_agent_user']}`\n"
            f"- **Default Cargo Standard:** `{COLD_CHAIN_PROFILES[st.session_state.get('active_profile_key', 'fresh_perishables')].label}`"
        )
        st.markdown("**Credential Configuration Status (Keys Redacted)**")
        st.markdown(
            f"- `GROQ_API_KEY`: `{summary['groq_configured']}`\n"
            f"- `GEMINI_API_KEY`: `{summary['gemini_configured']}`\n"
            f"- `PINECONE_API_KEY`: `{summary['pinecone_configured']}`\n"
            f"- `OPENAI_API_KEY`: `{summary['openai_configured']}`\n"
            f"- `DEEPSEEK_API_KEY`: `{summary['deepseek_configured']}`"
        )
        st.success(
            "Secrets are isolated in `.env` and never serialized to browser state or UI outputs.",
            icon=":material/verified_user:",
        )
