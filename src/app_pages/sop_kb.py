"""SOP Knowledge Base — Pinecone vector search, document previews, and safe re-indexing."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from src.config import POLICY_DIR
from src.data_access import (
    check_pinecone_health,
    list_policy_documents,
    query_sop_knowledge_base,
    sync_policy_to_pinecone,
)

pc_health = check_pinecone_health()

h1, h2 = st.columns([2, 1], vertical_alignment="center")
with h1:
    st.caption(
        "Enterprise policy & compliance retrieval powered by **Pinecone Vector DB** and "
        "`BAAI/bge-m3` / OpenAI embeddings (`scripts/ingest_sop_pinecone.py`)."
    )
with h2:
    with st.container(horizontal=True, horizontal_alignment="right"):
        if pc_health["ok"]:
            st.badge(f"Pinecone: {pc_health['detail']}", icon=":material/check_circle:", color="green")
        else:
            st.badge(f"Pinecone: {pc_health['status']}", icon=":material/warning:", color="orange")

if not pc_health["ok"]:
    st.info(
        f"**Retrieval Notice:** {pc_health['detail']}. Queries currently fall back safely to local "
        "markdown/text matching on `data/policy/`, or click **Sync Policy Docs to Pinecone** below to provision and index.",
        icon=":material/info:",
    )

# ==========================================
# SEMANTIC SEARCH CONSOLE
# ==========================================
with st.container(border=True):
    st.subheader("Semantic Compliance Search", anchor=False)
    with st.form("sop_search_form", border=False):
        s1, s2, s3 = st.columns([3, 0.8, 0.9], vertical_alignment="bottom")
        sop_query = s1.text_input(
            "Search Compliance SOPs",
            value="What are the temperature limits and port diversion procedures?",
            placeholder="Search cold-chain thresholds, port congestion rules, Tier 2 escalation...",
        )
        top_k = s2.number_input("Top K", min_value=1, max_value=10, value=4, step=1)
        run_search = s3.form_submit_button("Search SOPs", icon=":material/search:", type="primary", width="stretch")

    if run_search or sop_query:
        res = query_sop_knowledge_base(sop_query, top_k=int(top_k))
        st.caption(f"Retrieval Backend: **{res['backend']}**")
        if res.get("error") and not res["matches"]:
            st.error(res["error"])
        elif not res["matches"]:
            st.info("No matching policy clauses found.")
        else:
            for idx, m in enumerate(res["matches"], start=1):
                with st.container(border=True):
                    st.markdown(
                        f"**Match {idx}** · Source: `{m['source_file']}` (`{m['file_format']}`) · "
                        f"Relevance Score: `{m['score']}`"
                    )
                    st.markdown(m["content"])

st.space("small")

# ==========================================
# DOCUMENT INVENTORY, PREVIEW & SYNC
# ==========================================
left_col, right_col = st.columns([1.1, 1.2])

with left_col:
    with st.container(border=True):
        st.subheader("Policy Asset Inventory", anchor=False)
        docs = list_policy_documents()
        if docs:
            doc_table = pd.DataFrame(
                [
                    {
                        "Document": d["file_name"],
                        "Format": d["format"],
                        "Size (KB)": d["size_kb"],
                        "Modified": d["modified"],
                        "Hash Synced": d["hash_cached"],
                    }
                    for d in docs
                ]
            )
            st.dataframe(doc_table, hide_index=True)
        else:
            st.info("No policy documents found in `data/policy/`.")

        if st.button("Sync / Re-Index Policy Docs to Pinecone", icon=":material/sync:", type="primary", width="stretch"):
            with st.spinner("Running Pinecone ingestion pipeline (`scripts/ingest_sop_pinecone.py`)..."):
                sync_res = sync_policy_to_pinecone()
            if sync_res["ok"]:
                st.success("Pinecone SOP sync completed.")
                st.code(sync_res["message"], language="text")
                st.rerun()
            else:
                st.error(f"Pinecone sync failed: {sync_res['message']}")

        with st.expander("Upload New Compliance Document", expanded=False):
            uploaded = st.file_uploader(
                "Upload `.md`, `.txt`, or `.pdf` policy file",
                type=["md", "txt", "pdf"],
                key="sop_uploader",
            )
            if uploaded is not None:
                safe_name = Path(uploaded.name).name
                if st.button(f"Save `{safe_name}` to Policy Store", icon=":material/save:"):
                    POLICY_DIR.mkdir(parents=True, exist_ok=True)
                    dest = POLICY_DIR / safe_name
                    dest.write_bytes(uploaded.getvalue())
                    st.success(f"Saved `{safe_name}` to `data/policy/`. Click Sync above to index in Pinecone.")
                    st.rerun()

with right_col:
    with st.container(border=True):
        st.subheader("Document Preview", anchor=False)
        docs = list_policy_documents()
        if docs:
            doc_names = [d["file_name"] for d in docs]
            sel_doc_name = st.selectbox("Select Policy Document", doc_names, key="sop_preview_select")
            sel_doc = next(d for d in docs if d["file_name"] == sel_doc_name)
            path: Path = sel_doc["path"]
            if path.suffix.lower() in {".md", ".txt"}:
                st.markdown(path.read_text(encoding="utf-8", errors="ignore"))
            else:
                st.info(f"Binary preview not rendered for `{sel_doc['format']}` files. Use Semantic Search above to inspect indexed chunks.")
        else:
            st.caption("Upload or place a policy document in `data/policy/` to preview it.")
