"""FDE AI Dispatcher — Operational Intelligence Copilot powered by LangGraph."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st
from langchain_core.messages import HumanMessage, ToolMessage

from src.data_access import check_pinecone_health, check_sql_health, write_audit_event
from src.orchestrator import build_fde_agent

SUGGESTED_PROMPTS = [
    "Show all high-risk vehicles and their latest temperatures.",
    "Which shipments need immediate attention based on SOP v2.4?",
    "Identify potential temperature excursions above 4.0°C.",
    "Analyze current fleet operational performance.",
    "Check weather conditions near Port of Los Angeles (33.77, -118.19).",
    "Retrieve the cold-chain incident and port diversion SOP rules.",
    "Which records have the highest delay probability (>0.65)?",
    "Generate today's executive operational briefing.",
]


@st.cache_resource(show_spinner=False)
def _get_cached_agent(provider: str, model_name: str):
    return build_fde_agent(provider=provider, model_name=model_name)


def _try_parse_sql_table(raw_output: str) -> pd.DataFrame | None:
    """Parse structured COLUMNS + tuple rows returned by query_telemetry_db into a DataFrame."""
    lines = [ln.strip() for ln in raw_output.splitlines() if ln.strip()]
    col_line = next((ln for ln in lines if ln.startswith("COLUMNS:")), None)
    if not col_line:
        return None
    columns = [c.strip() for c in col_line.replace("COLUMNS:", "", 1).split(",")]
    rows = []
    col_idx = lines.index(col_line)
    import ast

    for ln in lines[col_idx + 1 :]:
        if ln.startswith("(") and ln.endswith(")"):
            try:
                parsed = ast.literal_eval(ln)
                if isinstance(parsed, tuple) and len(parsed) == len(columns):
                    rows.append(parsed)
            except Exception:
                continue
    return pd.DataFrame(rows, columns=columns) if rows else None


def _render_traces(traces: list[dict[str, Any]]) -> None:
    """Render safe, expandable tool execution inputs, outputs, and parsed SQL tables."""
    if not traces:
        return
    with st.expander(f"Evidence & Tool Execution Trace ({len(traces)} steps)", expanded=False):
        for idx, trace in enumerate(traces):
            if trace["type"] == "tool_input":
                st.markdown(f"**{idx + 1}. Tool Call:** `{trace['name']}`")
                st.json(trace["args"])
            elif trace["type"] == "tool_output":
                st.markdown(f"**{idx + 1}. Tool Result:** `{trace['name']}`")
                parsed_df = _try_parse_sql_table(trace["content"]) if trace["name"] == "query_telemetry_db" else None
                if parsed_df is not None:
                    st.dataframe(parsed_df, hide_index=True)
                st.code(trace["content"], language="text")


def _run_dispatcher_turn(user_prompt: str, conv_id: str) -> None:
    """Execute one LangGraph agent turn with streaming status updates and audit persistence."""
    convs = st.session_state.conversations
    conv = convs[conv_id]
    if not conv["messages"]:
        conv["title"] = user_prompt[:38] + ("..." if len(user_prompt) > 38 else "")

    conv["messages"].append({"role": "user", "content": user_prompt})
    with st.chat_message("user", avatar=":material/person:"):
        st.markdown(user_prompt)

    provider = st.session_state.get("llm_provider", "OLLAMA")
    model_name = st.session_state.get("llm_model", "qwen2.5:7b")

    with st.chat_message("assistant", avatar=":material/smart_toy:"):
        final_response = ""
        current_traces: list[dict[str, Any]] = []
        error_text = ""

        with st.status("Initializing FDE LangGraph Reasoner...", expanded=True) as status:
            try:
                agent = _get_cached_agent(provider, model_name)
                thread_config = {"configurable": {"thread_id": conv_id}}

                events = agent.stream(
                    {"messages": [HumanMessage(content=user_prompt)]},
                    config=thread_config,
                    stream_mode="updates",
                )

                for event in events:
                    for node_name, node_state in event.items():
                        if node_name == "reasoner":
                            latest_msg = node_state["messages"][-1]
                            if hasattr(latest_msg, "tool_calls") and latest_msg.tool_calls:
                                status.update(label="Selecting & parameterizing operational tools...")
                                for tc in latest_msg.tool_calls:
                                    st.markdown(f":material/bolt: Invoking `{tc['name']}`")
                                    args_json = json.dumps(tc.get("args", {}), default=str)
                                    current_traces.append(
                                        {"type": "tool_input", "name": tc["name"], "args": tc.get("args", {})}
                                    )
                                    write_audit_event(
                                        session_id=conv_id,
                                        node_name="reasoner",
                                        tool_name=tc["name"],
                                        content=args_json,
                                        status="SUCCESS",
                                        input_summary=args_json,
                                    )

                            if getattr(latest_msg, "content", None):
                                content_val = latest_msg.content
                                if isinstance(content_val, list):
                                    content_val = "\n".join(
                                        str(item.get("text", item)) if isinstance(item, dict) else str(item)
                                        for item in content_val
                                    )
                                final_response = str(content_val)
                                status.update(label="Synthesizing grounded operational response...")
                                write_audit_event(
                                    session_id=conv_id,
                                    node_name="reasoner_final",
                                    tool_name=f"LLM ({provider}/{model_name})",
                                    content=final_response,
                                    status="SUCCESS",
                                    input_summary=user_prompt,
                                    output_summary=final_response,
                                )

                        elif node_name == "tools":
                            status.update(label="Retrieving live telemetry, weather, and SOP evidence...")
                            for msg in node_state.get("messages", []):
                                if isinstance(msg, ToolMessage):
                                    msg_text = str(msg.content)
                                    is_err = any(
                                        tok in msg_text
                                        for tok in ("SECURITY BLOCK", "Database Error", "Failure", "Error:")
                                    )
                                    current_traces.append(
                                        {"type": "tool_output", "name": msg.name, "content": msg_text}
                                    )
                                    write_audit_event(
                                        session_id=conv_id,
                                        node_name="tools",
                                        tool_name=msg.name or "unknown_tool",
                                        content=msg_text,
                                        status="BLOCKED_OR_ERROR" if is_err else "SUCCESS",
                                        output_summary=msg_text,
                                        error_info=msg_text if is_err else "",
                                    )

                status.update(label="Operational analysis complete", state="complete", expanded=False)
            except Exception as exc:
                error_text = str(exc)
                status.update(label="Agent execution encountered an error", state="error", expanded=True)
                write_audit_event(
                    session_id=conv_id,
                    node_name="reasoner_error",
                    tool_name=f"LLM ({provider}/{model_name})",
                    content=error_text,
                    status="ERROR",
                    input_summary=user_prompt,
                    error_info=error_text,
                )

        if error_text:
            st.error(
                f"**Orchestrator Execution Error ({provider} / {model_name}):** {error_text}\n\n"
                "Verify API credentials / local Ollama service in **Settings**."
            )
            conv["messages"].append(
                {"role": "assistant", "content": f"Execution error: {error_text}", "traces": current_traces}
            )
        elif final_response:
            _render_traces(current_traces)
            st.markdown(final_response)
            conv["messages"].append(
                {"role": "assistant", "content": final_response, "traces": current_traces}
            )
        else:
            fallback = "No final response was returned by the reasoning model."
            st.warning(fallback)
            conv["messages"].append({"role": "assistant", "content": fallback, "traces": current_traces})


# ==========================================
# PAGE HEADER & CONVERSATION CONTROLS
# ==========================================
st.caption(
    "FDE AI Dispatcher — Operational Intelligence Copilot · Tools: `query_telemetry_db` (Read-Only SQL), "
    "`fetch_corridor_conditions` (Open-Meteo), `search_compliance_sop` (Pinecone / SOP)"
)

sql_h = check_sql_health()
pc_h = check_pinecone_health()

ctrl_l, ctrl_m, ctrl_r = st.columns([1.4, 1.3, 1.3], vertical_alignment="center")
with ctrl_l:
    conv_ids = list(st.session_state.conversations.keys())
    cur_id = st.session_state.thread_id
    if cur_id not in st.session_state.conversations:
        cur_id = conv_ids[0]
        st.session_state.thread_id = cur_id

    selected_conv = st.selectbox(
        "Conversation Session",
        options=conv_ids,
        index=conv_ids.index(cur_id),
        format_func=lambda cid: f"{st.session_state.conversations[cid]['title']} ({st.session_state.conversations[cid]['created_at']})",
        key="dispatcher_session_select",
        label_visibility="collapsed",
    )
    if selected_conv != cur_id:
        st.session_state.thread_id = selected_conv
        st.rerun()

with ctrl_m:
    st.caption(
        f"Thread: `{st.session_state.thread_id[:8]}` · "
        f"SQL: `{'Live' if sql_h['ok'] else 'CSV Mirror'}` · "
        f"SOP: `{'Pinecone' if pc_h['ok'] else 'Local MD'}`"
    )

with ctrl_r:
    with st.container(horizontal=True, horizontal_alignment="right"):
        if st.button("New Conversation", icon=":material/add_comment:", width="content"):
            new_id = str(uuid.uuid4())
            idx_num = len(st.session_state.conversations) + 1
            st.session_state.conversations[new_id] = {
                "title": f"Dispatch Session {idx_num}",
                "created_at": datetime.now().strftime("%H:%M"),
                "messages": [],
            }
            st.session_state.thread_id = new_id
            st.rerun()

st.info(
    "**Human-in-the-Loop Safety:** AI Dispatcher recommendations are decision-support only. "
    "Critical cargo diversions and Tier 2 escalations require explicit human dispatcher authorization.",
    icon=":material/shield:",
)

# ==========================================
# SUGGESTED PROMPTS & CHAT STREAM
# ==========================================
active_conv_id = st.session_state.thread_id
active_messages = st.session_state.conversations[active_conv_id]["messages"]

if not active_messages:
    st.markdown("##### Suggested Dispatch Inquiries")
    chosen = st.pills("Quick prompts", SUGGESTED_PROMPTS, label_visibility="collapsed", key="dispatcher_pills")
    if chosen:
        st.session_state.pending_dispatcher_prompt = chosen
        st.rerun()

for msg_idx, entry in enumerate(active_messages):
    avatar = ":material/person:" if entry["role"] == "user" else ":material/smart_toy:"
    with st.chat_message(entry["role"], avatar=avatar):
        if entry.get("traces"):
            _render_traces(entry["traces"])
        st.markdown(entry["content"])
        if entry["role"] == "assistant":
            with st.container(horizontal=True):
                st.download_button(
                    "Download Report",
                    data=entry["content"],
                    file_name=f"fde_dispatch_report_{active_conv_id[:8]}_{msg_idx}.md",
                    mime="text/markdown",
                    icon=":material/download:",
                    key=f"dl_msg_{active_conv_id}_{msg_idx}",
                )
                with st.popover("Copy Raw Text", icon=":material/content_copy:"):
                    st.code(entry["content"], language="markdown")

# Handle pending prompt from Overview/Live Fleet/Pills OR direct chat input
queued = st.session_state.pop("pending_dispatcher_prompt", None)
user_text = st.chat_input(
    "Ask FDE AI Dispatcher about high-risk vehicles, corridor weather, delays, or SOP mitigations...",
    submit_mode="disable",
)

prompt_to_run = queued or user_text
if prompt_to_run:
    _run_dispatcher_turn(prompt_to_run, active_conv_id)
