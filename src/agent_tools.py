"""FDE LangGraph agent tools for SQL telemetry, Open-Meteo weather, and Pinecone SOP retrieval."""

from __future__ import annotations

import os
import sys
from pathlib import Path
import requests
from dotenv import load_dotenv
from langchain_core.tools import tool

script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

load_dotenv(dotenv_path=project_root / ".env")

_EMBEDDINGS_CACHE = None
_VECTOR_STORE_CACHE = None


def get_embeddings():
    """Lazily load and cache the configured OpenAI or local HuggingFace embedding model."""
    global _EMBEDDINGS_CACHE
    if _EMBEDDINGS_CACHE is not None:
        return _EMBEDDINGS_CACHE

    mode = os.getenv("Embeddings_model", "LOCAL").strip().upper()
    if mode == "OPENAI":
        from langchain_openai import OpenAIEmbeddings

        _EMBEDDINGS_CACHE = OpenAIEmbeddings()
        return _EMBEDDINGS_CACHE

    local_model_target = os.getenv("Local_Embedding_Model", "BAAI/bge-m3").strip()
    try:
        import streamlit as st

        if st.runtime.exists():
            @st.cache_resource(show_spinner=False)
            def _load_st_hf(name: str):
                from langchain_huggingface import HuggingFaceEmbeddings

                return HuggingFaceEmbeddings(model_name=name, model_kwargs={"device": "cpu"})

            _EMBEDDINGS_CACHE = _load_st_hf(local_model_target)
            return _EMBEDDINGS_CACHE
    except Exception:
        pass

    from langchain_huggingface import HuggingFaceEmbeddings

    _EMBEDDINGS_CACHE = HuggingFaceEmbeddings(model_name=local_model_target, model_kwargs={"device": "cpu"})
    return _EMBEDDINGS_CACHE


def get_vector_store():
    """Lazily attach to the Pinecone vector index if configured and provisioned."""
    global _VECTOR_STORE_CACHE
    if _VECTOR_STORE_CACHE is not None:
        return _VECTOR_STORE_CACHE

    api_key = os.getenv("PINECONE_API_KEY", "").strip()
    if not api_key:
        return None

    mode = os.getenv("Embeddings_model", "LOCAL").strip().upper()
    index_name = "fde-sop-index-openai" if mode == "OPENAI" else "fde-sop-index-local"

    from pinecone import Pinecone
    from langchain_pinecone import PineconeVectorStore

    pc = Pinecone(api_key=api_key)
    if index_name not in list(pc.list_indexes().names()):
        return None

    embeddings = get_embeddings()
    _VECTOR_STORE_CACHE = PineconeVectorStore(index_name=index_name, embedding=embeddings)
    return _VECTOR_STORE_CACHE


# ==========================================
# CORE FDE AGENT TOOLS (PRESERVED NAMES)
# ==========================================

@tool
def query_telemetry_db(sql_query: str) -> str:
    """
    Executes a SQL SELECT query against the FDE_VIEWS.VW_ACTIVE_FLEET view.
    Columns available:
    Timestamp, Latitude, Longitude, Current_Temperature_C, Cargo_Condition_Code,
    Risk_Classification, Delay_Probability, Port_Congestion_Level, Route_Risk_Index.
    Always write standard T-SQL queries.
    """
    from src.data_access import execute_readonly_sql

    result = execute_readonly_sql(sql_query, max_rows=15)
    if not result["ok"]:
        return result["error"] or "Database query failed."

    rows = result["rows"]
    if not rows:
        return f"[SOURCE: {result['source']}]\nNo records matched the query criteria."

    formatted = [f"[SOURCE: {result['source']}]", f"COLUMNS: {', '.join(result['columns'])}"]
    for row in rows:
        formatted.append(str(tuple(row)))
    return "\n".join(formatted)


@tool
def fetch_corridor_conditions(latitude: float, longitude: float) -> str:
    """
    Fetches real-time weather and corridor conditions from a live REST API for given GPS coordinates.
    Provides temperature, wind speed, and computed corridor congestion index.
    """
    try:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={latitude}&longitude={longitude}&current_weather=true"
        )
        response = requests.get(url, timeout=6)
        response.raise_for_status()

        payload = response.json().get("current_weather", {})
        temp = payload.get("temperature", "N/A")
        wind = float(payload.get("windspeed", 0.0) or 0.0)
        obs_time = payload.get("time", "N/A")

        congestion_index = 8.5 if wind > 10.0 else 2.5
        status_note = "High Transit Disruption" if wind > 10.0 else "Corridor Normal"

        return (
            f"--- LIVE CORRIDOR TELEMETRY (Open-Meteo Observed + Derived Risk) ---\n"
            f"Target GPS: {latitude}, {longitude}\n"
            f"Observation Time (UTC): {obs_time}\n"
            f"Observed External Temp: {temp}°C | Observed Wind Speed: {wind} km/h\n"
            f"Derived Corridor Risk: {status_note} (Derived Congestion Index: {congestion_index}/10)\n"
            f"---------------------------------------------------------------------"
        )
    except Exception as e:
        return f"Corridor API Communication Failure: {str(e)}"


@tool
def search_compliance_sop(query: str) -> str:
    """
    Searches enterprise Standard Operating Procedures (SOPs) indexed in the Pinecone Vector DB.
    Use this to retrieve regulatory thresholds, cold-chain breach mitigations, and rerouting rules.
    """
    try:
        vs = get_vector_store()
        if vs is not None:
            matched_docs = vs.as_retriever(search_kwargs={"k": 3}).invoke(query)
            if matched_docs:
                formatted_context = "\n\n".join(
                    [
                        f"[Source: {doc.metadata.get('source_file', 'SOP')} | Format: {doc.metadata.get('file_format', 'RAW')} | Backend: Pinecone]\n{doc.page_content}"
                        for doc in matched_docs
                    ]
                )
                return f"--- COMPLIANCE SOP CONTEXT (Pinecone) ---\n{formatted_context}\n----------------------------------------"

        # Graceful fallback to local policy files if Pinecone index is not yet created
        from src.data_access import search_local_policy_fallback

        local_hits = search_local_policy_fallback(query, k=3)
        if not local_hits:
            return "No matching compliance clauses found in Pinecone or local policy store."

        formatted_local = "\n\n".join(
            [
                f"[Source: {hit['source_file']} | Format: {hit['file_format']} | Backend: {hit['backend']}]\n{hit['content']}"
                for hit in local_hits
            ]
        )
        return f"--- COMPLIANCE SOP CONTEXT (Local Policy Fallback) ---\n{formatted_local}\n-----------------------------------------------------"
    except Exception as e:
        return f"Vector Store Retrieval Error: {str(e)}"


if __name__ == "__main__":
    print("\n--- Testing Tool 1: SQL Telemetry View ---")
    print(query_telemetry_db.invoke("SELECT TOP 2 Latitude, Longitude, Current_Temperature_C FROM FDE_VIEWS.VW_ACTIVE_FLEET"))

    print("\n--- Testing Tool 2: Live Corridor API ---")
    print(fetch_corridor_conditions.invoke({"latitude": 33.77, "longitude": -118.19}))

    print("\n--- Testing Tool 3: Compliance SOP Retrieval ---")
    print(search_compliance_sop.invoke("What are the temperature rules for fresh perishables?"))
