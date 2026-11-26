"""Audit Center — Enterprise session trace inspection and SQL Server admin audit gate."""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from src.data_access import check_sql_health, read_local_audit_events, read_sql_audit_events

sql_h = check_sql_health()

st.caption(
    "Separated privilege model: `USR_FDE_RO` has read-only access to `FDE_VIEWS.VW_ACTIVE_FLEET` "
    "and insert-only access to `FDE_VIEWS.AgentAuditLog`. Reading SQL audit trails requires `SQL_ADMIN_USER`."
)

tab_local, tab_sql = st.tabs(
    ["Local Audit Trail (Always Available)", "SQL Server Admin Audit Gate (`FDE_VIEWS.AgentAuditLog`)"]
)

with tab_local:
    local_df = read_local_audit_events(limit=500)
    if local_df.empty:
        st.info(
            "No local audit records captured yet. Send a prompt in **AI Dispatcher** to record "
            "structured LangGraph node, tool input, tool output, and SQL sync events.",
            icon=":material/history:",
        )
    else:
        with st.container(border=True):
            f1, f2, f3, f4 = st.columns([1.4, 1, 1, 1])
            q = f1.text_input("Search payload / session", placeholder="Search text or session...", key="audit_search")
            sessions = ["All", *sorted(local_df["SessionID"].astype(str).unique().tolist())]
            sel_session = f2.selectbox("Session ID", sessions, key="audit_session_filter")
            tools = ["All", *sorted(local_df["ToolName"].astype(str).unique().tolist())]
            sel_tool = f3.selectbox("Tool / Node", tools, key="audit_tool_filter")
            statuses = ["All", *sorted(local_df["ExecutionStatus"].astype(str).unique().tolist())]
            sel_status = f4.selectbox("Status", statuses, key="audit_status_filter")

        filtered = local_df.copy()
        if sel_session != "All":
            filtered = filtered[filtered["SessionID"] == sel_session]
        if sel_tool != "All":
            filtered = filtered[filtered["ToolName"] == sel_tool]
        if sel_status != "All":
            filtered = filtered[filtered["ExecutionStatus"] == sel_status]
        if q.strip():
            s = q.strip().lower()
            filtered = filtered[
                filtered["SessionID"].astype(str).str.lower().str.contains(s, na=False)
                | filtered["ToolName"].astype(str).str.lower().str.contains(s, na=False)
                | filtered["InputSummary"].astype(str).str.lower().str.contains(s, na=False)
                | filtered["OutputSummary"].astype(str).str.lower().str.contains(s, na=False)
            ]

        c_left, c_right = st.columns([2, 1], vertical_alignment="center")
        c_left.caption(f"Showing **{len(filtered):,}** audit events")
        with c_right:
            with st.container(horizontal=True, horizontal_alignment="right"):
                st.download_button(
                    "Export Audit CSV",
                    data=filtered.to_csv(index=False),
                    file_name="fde_audit_trail.csv",
                    mime="text/csv",
                    icon=":material/download:",
                )

        sel_ev = st.dataframe(
            filtered[
                [
                    "LogID",
                    "Timestamp",
                    "SessionID",
                    "NodeExecuted",
                    "ToolName",
                    "ExecutionStatus",
                    "SqlSyncStatus",
                ]
            ],
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="audit_local_df",
        )

        if not filtered.empty:
            row_idx = sel_ev.selection.rows[0] if sel_ev.selection.rows else 0
            ev = filtered.iloc[row_idx]
            with st.expander(f"Event Detail — Log #{ev['LogID']} ({ev['NodeExecuted']} · {ev['ToolName']})", expanded=True):
                d1, d2 = st.columns(2)
                d1.write(f"**Timestamp (UTC):** `{ev['Timestamp']}`")
                d1.write(f"**Session ID:** `{ev['SessionID']}`")
                d2.write(f"**Execution Status:** `{ev['ExecutionStatus']}`")
                d2.write(f"**SQL Sync:** `{ev['SqlSyncStatus']}`")
                if ev["InputSummary"]:
                    st.markdown("**Input Summary**")
                    st.code(str(ev["InputSummary"]), language="text")
                if ev["OutputSummary"]:
                    st.markdown("**Output Summary**")
                    st.code(str(ev["OutputSummary"]), language="text")
                if ev["ErrorInfo"]:
                    st.error(f"**Error Info:** {ev['ErrorInfo']}")

with tab_sql:
    with st.container(border=True):
        st.subheader("SQL Server Database Authorization Gate", anchor=False)
        if not sql_h["ok"]:
            st.warning(f"SQL Server is currently **{sql_h['status']}** (`{sql_h['detail']}`).")

        with st.form("admin_auth_form"):
            col1, col2 = st.columns(2)
            with col1:
                input_user = st.text_input("Admin Username", value=os.getenv("SQL_ADMIN_USER", "sa"))
            with col2:
                input_pass = st.text_input("Admin Password", type="password", value="")
            submit_admin = st.form_submit_button("Authenticate & Query FDE_VIEWS.AgentAuditLog", icon=":material/lock_open:", type="primary", width="stretch")

        if submit_admin:
            sql_df, err = read_sql_audit_events(input_user, input_pass, limit=500)
            if err:
                st.error(err, icon=":material/error:")
            elif sql_df.empty:
                st.info("Authenticated successfully. No rows found in `FDE_VIEWS.AgentAuditLog`.")
            else:
                st.success(f"Authenticated successfully. Retrieved {len(sql_df):,} audit records.", icon=":material/check_circle:")
                st.download_button(
                    "Export SQL Audit CSV",
                    data=sql_df.to_csv(index=False),
                    file_name="fde_sql_agent_audit_log.csv",
                    mime="text/csv",
                    icon=":material/download:",
                )
                st.dataframe(sql_df, hide_index=True)
