"""Database, telemetry, weather, Pinecone, and audit data access layer."""

from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import sqlite3
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from src.config import (
    AUDIT_DB_PATH,
    CACHE_DIR,
    HASH_CACHE_FILE,
    POLICY_DIR,
    RAW_DATA_PATH,
    assign_corridor_zone,
)

# Forbidden SQL statements / keywords for read-only agent queries
_FORBIDDEN_SQL_RE = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|MERGE|EXEC|EXECUTE|GRANT|REVOKE|DENY|XP_|SP_)\b",
    re.IGNORECASE,
)


def _build_mssql_odbc_url(uid: str, pwd: str, timeout: int = 3) -> str:
    host = os.getenv("SQL_SERVER_HOST", "localhost").strip()
    port = os.getenv("SQL_SERVER_PORT", "1433").strip()
    connection_string = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={host},{port};"
        f"DATABASE=master;"
        f"UID={uid};"
        f"PWD={pwd};"
        f"Encrypt=no;"
        f"TrustServerCertificate=yes;"
        f"Connection Timeout={timeout};"
    )
    params = urllib.parse.quote_plus(connection_string)
    return f"mssql+pyodbc:///?odbc_connect={params}"


@st.cache_resource(show_spinner=False)
def get_agent_sql_engine() -> Engine | None:
    """Create a cached SQLAlchemy engine for the restricted USR_FDE_RO agent user."""
    uid = os.getenv("SQL_AGENT_USER", "USR_FDE_RO").strip()
    pwd = os.getenv("SQL_AGENT_PASSWORD", "").strip()
    if not uid or not pwd:
        return None
    return create_engine(
        _build_mssql_odbc_url(uid, pwd, timeout=3),
        pool_pre_ping=True,
        pool_size=3,
        max_overflow=2,
    )


def create_admin_sql_engine(uid: str, pwd: str) -> Engine:
    """Create a short-lived, uncached SQLAlchemy engine for admin audit inspection."""
    return create_engine(
        _build_mssql_odbc_url(uid, pwd, timeout=4),
        pool_pre_ping=True,
    )


def is_tcp_reachable(host: str, port: int, timeout: float = 1.5) -> tuple[bool, str]:
    """Fast TCP probe to avoid waiting on driver timeouts when SQL/Ollama is stopped."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, int(port)))
        return True, "Reachable"
    except Exception as exc:
        return False, str(exc)
    finally:
        sock.close()


def validate_select_sql(sql_query: str) -> tuple[bool, str]:
    """Validate that a SQL query is strictly single-statement read-only SELECT."""
    cleaned = (sql_query or "").strip()
    if not cleaned:
        return False, "SECURITY BLOCK: Empty SQL query."

    # Strip trailing semicolon only; reject embedded semicolons
    no_trailing = cleaned.rstrip(";").strip()
    if ";" in no_trailing:
        return False, "SECURITY BLOCK: Multiple SQL statements are not permitted."

    if not re.match(r"^(WITH|SELECT)\b", no_trailing, re.IGNORECASE):
        return False, "SECURITY BLOCK: Only SELECT operations are authorized on FDE_VIEWS.VW_ACTIVE_FLEET."

    if _FORBIDDEN_SQL_RE.search(no_trailing):
        return False, "SECURITY BLOCK: Mutating or administrative SQL keywords are prohibited."

    return True, no_trailing


def _translate_tsql_to_sqlite(sql_query: str) -> str:
    """Translate basic T-SQL TOP N syntax and view name for the read-only CSV SQLite mirror."""
    q = sql_query.replace("FDE_VIEWS.VW_ACTIVE_FLEET", "VW_ACTIVE_FLEET")
    q = q.replace("[FDE_VIEWS].[VW_ACTIVE_FLEET]", "VW_ACTIVE_FLEET")
    top_match = re.match(r"^\s*SELECT\s+TOP\s+(\d+)\s+", q, re.IGNORECASE)
    if top_match:
        limit_val = top_match.group(1)
        q = re.sub(r"^\s*SELECT\s+TOP\s+\d+\s+", "SELECT ", q, count=1, flags=re.IGNORECASE)
        if not re.search(r"\bLIMIT\s+\d+\s*$", q, re.IGNORECASE):
            q = f"{q.rstrip(';')} LIMIT {limit_val}"
    return q


def _get_sqlite_fleet_mirror() -> sqlite3.Connection:
    """Build an in-memory read-only SQLite mirror of FDE_VIEWS.VW_ACTIVE_FLEET from the project CSV."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    df = pd.read_csv(RAW_DATA_PATH)
    mirror_df = pd.DataFrame(
        {
            "Timestamp": df["timestamp"],
            "Latitude": df["vehicle_gps_latitude"],
            "Longitude": df["vehicle_gps_longitude"],
            "Current_Temperature_C": df["iot_temperature"].astype(float),
            "Cargo_Condition_Code": df["cargo_condition_status"],
            "Risk_Classification": df["risk_classification"],
            "Delay_Probability": df["delay_probability"],
            "Port_Congestion_Level": df["port_congestion_level"],
            "Route_Risk_Index": df["route_risk_level"],
        }
    )
    mirror_df.to_sql("VW_ACTIVE_FLEET", conn, if_exists="replace", index=False)
    return conn


_SQLITE_MIRROR_CONN: sqlite3.Connection | None = None


def execute_readonly_sql(sql_query: str, max_rows: int = 25) -> dict[str, Any]:
    """Execute a validated read-only SELECT query against SQL Server or CSV mirror fallback."""
    ok, cleaned_or_err = validate_select_sql(sql_query)
    if not ok:
        return {"ok": False, "error": cleaned_or_err, "columns": [], "rows": [], "source": "Security Gate"}

    host = os.getenv("SQL_SERVER_HOST", "localhost").strip()
    port = int(os.getenv("SQL_SERVER_PORT", "1433").strip() or "1433")
    engine = get_agent_sql_engine()

    if engine is not None:
        tcp_ok, _ = is_tcp_reachable(host, port, timeout=1.0)
        if tcp_ok:
            try:
                with engine.connect() as conn:
                    cursor = conn.execute(text(cleaned_or_err))
                    columns = list(cursor.keys())
                    rows = [tuple(r) for r in cursor.fetchmany(max_rows)]
                return {
                    "ok": True,
                    "columns": columns,
                    "rows": rows,
                    "source": "SQL Server (FDE_VIEWS.VW_ACTIVE_FLEET)",
                    "error": None,
                }
            except Exception as exc:
                sql_err = str(exc)
        else:
            sql_err = f"SQL Server at {host}:{port} is unreachable."
    else:
        sql_err = "SQL_AGENT_PASSWORD is not configured in .env."

    # Fallback: read-only SQLite mirror of FDE_VIEWS.VW_ACTIVE_FLEET from the project dataset
    global _SQLITE_MIRROR_CONN
    try:
        if _SQLITE_MIRROR_CONN is None:
            _SQLITE_MIRROR_CONN = _get_sqlite_fleet_mirror()
        sqlite_sql = _translate_tsql_to_sqlite(cleaned_or_err)
        cur = _SQLITE_MIRROR_CONN.execute(sqlite_sql)
        columns = [desc[0] for desc in (cur.description or [])]
        rows = cur.fetchmany(max_rows)
        return {
            "ok": True,
            "columns": columns,
            "rows": rows,
            "source": f"Local VW_ACTIVE_FLEET CSV Mirror (Fallback — {sql_err})",
            "error": None,
        }
    except Exception as exc:
        return {
            "ok": False,
            "columns": [],
            "rows": [],
            "source": "Local VW_ACTIVE_FLEET CSV Mirror",
            "error": f"SQL Error ({sql_err}) | Fallback Error: {exc}",
        }


def _standardize_fleet_dataframe(df: pd.DataFrame, is_sql_view: bool) -> pd.DataFrame:
    """Normalize column names from either SQL Server VW_ACTIVE_FLEET or the raw CSV dataset."""
    out = df.copy()
    if is_sql_view:
        rename_map = {
            "Timestamp": "timestamp",
            "Latitude": "vehicle_gps_latitude",
            "Longitude": "vehicle_gps_longitude",
            "Current_Temperature_C": "iot_temperature",
            "Cargo_Condition_Code": "cargo_condition_status",
            "Risk_Classification": "risk_classification",
            "Delay_Probability": "delay_probability",
            "Port_Congestion_Level": "port_congestion_level",
            "Route_Risk_Index": "route_risk_level",
        }
        out = out.rename(columns=rename_map)

    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce")
    out = out.sort_values("timestamp").reset_index(drop=True)
    out["record_id"] = [f"REC-{i + 1:05d}" for i in range(len(out))]
    out["corridor_zone"] = [
        assign_corridor_zone(float(lat), float(lon))
        for lat, lon in zip(out["vehicle_gps_latitude"], out["vehicle_gps_longitude"])
    ]
    return out


@st.cache_data(ttl=300, show_spinner=False)
def load_telemetry_data() -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Load fleet telemetry from SQL Server FDE_VIEWS.VW_ACTIVE_FLEET when available,
    or fall back transparently to data/raw/dynamic_supply_chain_logistics_dataset.csv.
    """
    loaded_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    host = os.getenv("SQL_SERVER_HOST", "localhost").strip()
    port = int(os.getenv("SQL_SERVER_PORT", "1433").strip() or "1433")
    engine = get_agent_sql_engine()
    sql_note = "SQL_AGENT_PASSWORD not set"

    if engine is not None:
        tcp_ok, tcp_msg = is_tcp_reachable(host, port, timeout=1.0)
        if tcp_ok:
            try:
                with engine.connect() as conn:
                    sql_df = pd.read_sql("SELECT * FROM FDE_VIEWS.VW_ACTIVE_FLEET", conn)
                df = _standardize_fleet_dataframe(sql_df, is_sql_view=True)
                return df, {
                    "source_mode": "sql_live",
                    "source_label": "Microsoft SQL Server (FDE_VIEWS.VW_ACTIVE_FLEET)",
                    "loaded_at": loaded_at,
                    "row_count": len(df),
                    "has_extended_columns": False,
                    "sql_note": "Connected via USR_FDE_RO",
                }
            except Exception as exc:
                sql_note = str(exc)
        else:
            sql_note = f"TCP {host}:{port} unreachable ({tcp_msg})"

    if not RAW_DATA_PATH.exists():
        return pd.DataFrame(), {
            "source_mode": "unavailable",
            "source_label": "No Telemetry Source Available",
            "loaded_at": loaded_at,
            "row_count": 0,
            "has_extended_columns": False,
            "sql_note": sql_note,
        }

    csv_df = pd.read_csv(RAW_DATA_PATH)
    df = _standardize_fleet_dataframe(csv_df, is_sql_view=False)
    return df, {
        "source_mode": "csv_fallback",
        "source_label": "Historical Fleet Dataset CSV (SQL Server Offline)",
        "loaded_at": loaded_at,
        "row_count": len(df),
        "has_extended_columns": True,
        "sql_note": sql_note,
    }


# ==========================================
# HEALTH CHECKS
# ==========================================

@st.cache_data(ttl=60, show_spinner=False)
def check_sql_health() -> dict[str, Any]:
    host = os.getenv("SQL_SERVER_HOST", "localhost").strip()
    port = int(os.getenv("SQL_SERVER_PORT", "1433").strip() or "1433")
    pwd = os.getenv("SQL_AGENT_PASSWORD", "").strip()
    tcp_ok, tcp_msg = is_tcp_reachable(host, port, timeout=1.0)
    if not tcp_ok:
        return {"ok": False, "status": "Offline", "detail": f"{host}:{port} unreachable"}
    if not pwd:
        return {"ok": False, "status": "Credentials Missing", "detail": "SQL_AGENT_PASSWORD empty in .env"}
    engine = get_agent_sql_engine()
    if engine is None:
        return {"ok": False, "status": "Unconfigured", "detail": "Agent engine unavailable"}
    try:
        with engine.connect() as conn:
            val = conn.execute(text("SELECT COUNT(*) FROM FDE_VIEWS.VW_ACTIVE_FLEET")).scalar()
        return {"ok": True, "status": "Connected", "detail": f"VW_ACTIVE_FLEET ({int(val or 0):,} rows)"}
    except Exception as exc:
        return {"ok": False, "status": "Auth / View Error", "detail": str(exc)[:140]}


@st.cache_data(ttl=60, show_spinner=False)
def check_pinecone_health() -> dict[str, Any]:
    api_key = os.getenv("PINECONE_API_KEY", "").strip()
    if not api_key:
        return {"ok": False, "status": "Missing Key", "detail": "PINECONE_API_KEY not set", "indexes": []}

    emb_mode = os.getenv("Embeddings_model", "LOCAL").strip().upper()
    target_index = "fde-sop-index-openai" if emb_mode == "OPENAI" else "fde-sop-index-local"
    try:
        from pinecone import Pinecone

        pc = Pinecone(api_key=api_key)
        indexes = list(pc.list_indexes().names())
        if target_index in indexes:
            stats = pc.Index(target_index).describe_index_stats()
            total_vectors = int(stats.get("total_vector_count", 0))
            return {
                "ok": True,
                "status": "Connected",
                "detail": f"{target_index} ({total_vectors:,} vectors)",
                "indexes": indexes,
                "target_index": target_index,
                "vector_count": total_vectors,
            }
        return {
            "ok": False,
            "status": "Index Not Provisioned",
            "detail": f"Connected to Pinecone; target index '{target_index}' not created yet",
            "indexes": indexes,
            "target_index": target_index,
            "vector_count": 0,
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": "Connection Error",
            "detail": str(exc)[:140],
            "indexes": [],
            "target_index": target_index,
            "vector_count": 0,
        }


@st.cache_data(ttl=120, show_spinner=False)
def check_open_meteo_health() -> dict[str, Any]:
    try:
        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": 33.77, "longitude": -118.19, "current_weather": "true"},
            timeout=5,
        )
        resp.raise_for_status()
        cw = resp.json().get("current_weather", {})
        return {
            "ok": True,
            "status": "Connected",
            "detail": f"Live API OK ({cw.get('temperature', '?')}°C @ SoCal)",
        }
    except Exception as exc:
        return {"ok": False, "status": "Offline", "detail": str(exc)[:140]}


@st.cache_data(ttl=60, show_spinner=False)
def check_llm_health(provider: str | None = None) -> dict[str, Any]:
    active = (provider or os.getenv("Agent_llm", "OLLAMA")).strip().upper()
    if active == "GROQ":
        key = os.getenv("GROQ_API_KEY", "").strip()
        model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()
        return {
            "ok": bool(key),
            "status": "Configured" if key else "Missing Key",
            "detail": f"Groq ({model})",
        }
    if active == "GEMINI":
        key = os.getenv("GEMINI_API_KEY", "").strip()
        model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
        return {
            "ok": bool(key),
            "status": "Configured" if key else "Missing Key",
            "detail": f"Gemini ({model})",
        }
    if active == "OPENAI":
        key = os.getenv("OPENAI_API_KEY", "").strip()
        return {"ok": bool(key), "status": "Configured" if key else "Missing Key", "detail": "OpenAI (gpt-4o)"}
    if active == "DEEPSEEK":
        key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        return {"ok": bool(key), "status": "Configured" if key else "Missing Key", "detail": "DeepSeek (deepseek-v4-flash)"}
    ok, msg = is_tcp_reachable("127.0.0.1", 11434, timeout=0.8)
    return {
        "ok": ok,
        "status": "Connected" if ok else "Offline",
        "detail": "Ollama (qwen2.5:7b)" if ok else f"Ollama localhost:11434 ({msg})",
    }


# ==========================================
# WEATHER INTELLIGENCE (OPEN-METEO)
# ==========================================

@st.cache_data(ttl=300, show_spinner=False)
def fetch_corridor_weather(latitude: float, longitude: float) -> dict[str, Any]:
    """Fetch live Open-Meteo current weather + derived corridor risk classification."""
    try:
        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current_weather": "true",
                "hourly": "temperature_2m,windspeed_10m,precipitation_probability",
                "forecast_days": 1,
            },
            timeout=6,
        )
        resp.raise_for_status()
        data = resp.json()
        cw = data.get("current_weather", {})
        temp = float(cw.get("temperature")) if cw.get("temperature") is not None else None
        wind = float(cw.get("windspeed")) if cw.get("windspeed") is not None else 0.0
        wind_dir = cw.get("winddirection")
        obs_time = cw.get("time", "")

        # Clearly separated derived operational risk index
        congestion_index = 8.5 if wind > 10.0 else 2.5
        if wind > 25.0:
            corridor_status = "Severe Wind Advisory"
        elif wind > 10.0:
            corridor_status = "Elevated Transit Disruption"
        else:
            corridor_status = "Corridor Normal"

        hourly = data.get("hourly", {})
        hourly_df = pd.DataFrame(
            {
                "time": hourly.get("time", []),
                "temperature_c": hourly.get("temperature_2m", []),
                "wind_kmh": hourly.get("windspeed_10m", []),
                "precip_prob_pct": hourly.get("precipitation_probability", []),
            }
        )
        if not hourly_df.empty:
            hourly_df["time"] = pd.to_datetime(hourly_df["time"], errors="coerce")

        return {
            "ok": True,
            "latitude": latitude,
            "longitude": longitude,
            "observed_temp_c": temp,
            "observed_wind_kmh": wind,
            "observed_wind_dir": wind_dir,
            "observed_time": obs_time,
            "weathercode": cw.get("weathercode"),
            "derived_congestion_index": congestion_index,
            "derived_status": corridor_status,
            "hourly_df": hourly_df,
            "error": None,
        }
    except Exception as exc:
        return {
            "ok": False,
            "latitude": latitude,
            "longitude": longitude,
            "observed_temp_c": None,
            "observed_wind_kmh": None,
            "observed_wind_dir": None,
            "observed_time": None,
            "weathercode": None,
            "derived_congestion_index": None,
            "derived_status": "API Unavailable",
            "hourly_df": pd.DataFrame(),
            "error": str(exc),
        }


# ==========================================
# AUDIT LOGGING (SQL SERVER + LOCAL SQLITE STORE)
# ==========================================

def _ensure_local_audit_db() -> sqlite3.Connection:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(AUDIT_DB_PATH), check_same_thread=False)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS AgentAuditLogLocal (
            LogID INTEGER PRIMARY KEY AUTOINCREMENT,
            Timestamp TEXT NOT NULL,
            SessionID TEXT NOT NULL,
            NodeExecuted TEXT NOT NULL,
            ToolName TEXT NOT NULL,
            ExecutionStatus TEXT NOT NULL,
            InputSummary TEXT,
            OutputSummary TEXT,
            ErrorInfo TEXT,
            SqlSyncStatus TEXT
        )
        """
    )
    conn.commit()
    return conn


def write_audit_event(
    session_id: str,
    node_name: str,
    tool_name: str,
    content: str,
    *,
    status: str = "SUCCESS",
    input_summary: str = "",
    output_summary: str = "",
    error_info: str = "",
) -> dict[str, Any]:
    """
    Write an audit event to SQL Server FDE_VIEWS.AgentAuditLog (when reachable)
    and persist to the local SQLite audit store so traces are never lost or silently hidden.
    """
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    sql_synced = False
    sql_error = None

    host = os.getenv("SQL_SERVER_HOST", "localhost").strip()
    port = int(os.getenv("SQL_SERVER_PORT", "1433").strip() or "1433")
    engine = get_agent_sql_engine()

    if engine is not None:
        tcp_ok, tcp_msg = is_tcp_reachable(host, port, timeout=0.8)
        if tcp_ok:
            try:
                with engine.connect() as conn:
                    conn.execute(
                        text(
                            """
                            INSERT INTO FDE_VIEWS.AgentAuditLog (SessionID, NodeExecuted, ToolName, Content)
                            VALUES (:session_id, :node_name, :tool_name, :content)
                            """
                        ),
                        {
                            "session_id": session_id[:50],
                            "node_name": node_name[:50],
                            "tool_name": tool_name[:100],
                            "content": content,
                        },
                    )
                    conn.commit()
                sql_synced = True
            except Exception as exc:
                sql_error = str(exc)
        else:
            sql_error = f"SQL Server unreachable ({tcp_msg})"
    else:
        sql_error = "SQL_AGENT_PASSWORD not configured"

    sql_sync_label = "Synced to SQL Server" if sql_synced else f"Local Only ({sql_error})"

    try:
        conn = _ensure_local_audit_db()
        conn.execute(
            """
            INSERT INTO AgentAuditLogLocal
            (Timestamp, SessionID, NodeExecuted, ToolName, ExecutionStatus, InputSummary, OutputSummary, ErrorInfo, SqlSyncStatus)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ts,
                session_id,
                node_name,
                tool_name,
                status,
                input_summary[:2000],
                (output_summary or content)[:4000],
                error_info[:1000],
                sql_sync_label[:240],
            ),
        )
        conn.commit()
        conn.close()
    except Exception as local_exc:
        return {"sql_synced": sql_synced, "sql_error": sql_error, "local_error": str(local_exc)}

    return {"sql_synced": sql_synced, "sql_error": sql_error, "local_error": None}


def read_local_audit_events(limit: int = 500) -> pd.DataFrame:
    """Read structured audit logs from the local SQLite audit store."""
    if not AUDIT_DB_PATH.exists():
        return pd.DataFrame(
            columns=[
                "LogID",
                "Timestamp",
                "SessionID",
                "NodeExecuted",
                "ToolName",
                "ExecutionStatus",
                "InputSummary",
                "OutputSummary",
                "ErrorInfo",
                "SqlSyncStatus",
            ]
        )
    conn = _ensure_local_audit_db()
    try:
        df = pd.read_sql_query(
            f"SELECT * FROM AgentAuditLogLocal ORDER BY LogID DESC LIMIT {int(limit)}",
            conn,
        )
    finally:
        conn.close()
    return df


def read_sql_audit_events(admin_user: str, admin_password: str, limit: int = 500) -> tuple[pd.DataFrame, str | None]:
    """Authenticate with admin credentials and read FDE_VIEWS.AgentAuditLog from SQL Server."""
    expected_user = os.getenv("SQL_ADMIN_USER", "").strip()
    expected_pass = os.getenv("SQL_ADMIN_PASSWORD", "").strip()
    if not expected_user or not expected_pass:
        return pd.DataFrame(), "SQL_ADMIN_USER / SQL_ADMIN_PASSWORD are not configured in .env."
    if admin_user != expected_user or admin_password != expected_pass:
        return pd.DataFrame(), "Invalid administrator credentials."

    try:
        engine = create_admin_sql_engine(admin_user, admin_password)
        with engine.connect() as conn:
            query = text(
                f"""
                SELECT TOP {int(limit)} LogID, Timestamp, SessionID, NodeExecuted, ToolName, Content
                FROM FDE_VIEWS.AgentAuditLog
                ORDER BY Timestamp DESC
                """
            )
            df = pd.read_sql(query, conn)
        return df, None
    except Exception as exc:
        return pd.DataFrame(), f"Database query failed: {exc}"


# ==========================================
# POLICY DOCUMENTS & PINECONE SOP RETRIEVAL
# ==========================================

def list_policy_documents() -> list[dict[str, Any]]:
    """List policy assets on disk with hash cache status."""
    POLICY_DIR.mkdir(parents=True, exist_ok=True)
    hash_cache: dict[str, str] = {}
    if HASH_CACHE_FILE.exists():
        try:
            hash_cache = json.loads(HASH_CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            hash_cache = {}

    docs: list[dict[str, Any]] = []
    for ext in ("*.md", "*.txt", "*.pdf", "*.csv", "*.xlsx"):
        for path in sorted(POLICY_DIR.glob(ext)):
            raw = path.read_bytes()
            md5 = hashlib.md5(raw).hexdigest()
            docs.append(
                {
                    "file_name": path.name,
                    "format": path.suffix.lstrip(".").upper(),
                    "size_kb": round(len(raw) / 1024, 2),
                    "modified": datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                    "md5": md5,
                    "hash_cached": hash_cache.get(path.name) == md5,
                    "path": path,
                }
            )
    return docs


def search_local_policy_fallback(query: str, k: int = 3) -> list[dict[str, Any]]:
    """Deterministic keyword-scored search over data/policy/* when Pinecone index is unprovisioned."""
    query_terms = [t for t in re.findall(r"[a-zA-Z0-9_]+", query.lower()) if len(t) > 2]
    results: list[dict[str, Any]] = []
    for doc in list_policy_documents():
        path: Path = doc["path"]
        if path.suffix.lower() not in {".md", ".txt"}:
            continue
        text_content = path.read_text(encoding="utf-8", errors="ignore")
        sections = re.split(r"\n(?=#{1,3}\s)", text_content)
        for idx, section in enumerate(sections):
            sec_lower = section.lower()
            hits = sum(1 for term in query_terms if term in sec_lower)
            if hits > 0 or not query_terms:
                results.append(
                    {
                        "source_file": doc["file_name"],
                        "file_format": doc["format"],
                        "score": round(hits / max(len(query_terms), 1), 3),
                        "section_index": idx + 1,
                        "content": section.strip(),
                        "backend": "Local Policy Fallback (Pinecone index not provisioned)",
                    }
                )
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:k]


def query_sop_knowledge_base(query: str, top_k: int = 4) -> dict[str, Any]:
    """Query Pinecone vector store for SOP matches with relevance scores, falling back safely if unprovisioned."""
    pc_health = check_pinecone_health()
    if pc_health.get("ok"):
        try:
            from src.agent_tools import get_vector_store

            vs = get_vector_store()
            if vs is not None:
                scored = vs.similarity_search_with_score(query, k=top_k)
                matches = [
                    {
                        "source_file": doc.metadata.get("source_file", "SOP"),
                        "file_format": doc.metadata.get("file_format", "MD"),
                        "score": round(float(score), 4),
                        "content": doc.page_content,
                        "metadata": doc.metadata,
                        "backend": f"Pinecone ({pc_health.get('target_index')})",
                    }
                    for doc, score in scored
                ]
                return {"ok": True, "backend": f"Pinecone ({pc_health.get('target_index')})", "matches": matches, "error": None}
        except Exception as exc:
            fallback = search_local_policy_fallback(query, k=top_k)
            return {
                "ok": False,
                "backend": "Local Policy Fallback",
                "matches": fallback,
                "error": f"Pinecone query error: {exc}",
            }

    fallback = search_local_policy_fallback(query, k=top_k)
    return {
        "ok": True,
        "backend": "Local Policy Fallback (Pinecone index not provisioned)",
        "matches": fallback,
        "error": pc_health.get("detail"),
    }


def sync_policy_to_pinecone() -> dict[str, Any]:
    """Run the existing Pinecone SOP ingestion script logic safely from the UI."""
    api_key = os.getenv("PINECONE_API_KEY", "").strip()
    if not api_key:
        return {"ok": False, "message": "PINECONE_API_KEY is missing in .env."}
    try:
        import subprocess
        import sys

        script_path = Path(__file__).resolve().parent.parent / "scripts" / "ingest_sop_pinecone.py"
        proc = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=180,
        )
        check_pinecone_health.clear()
        if proc.returncode == 0:
            return {"ok": True, "message": proc.stdout.strip() or "Pinecone SOP sync completed."}
        return {"ok": False, "message": (proc.stderr or proc.stdout).strip()}
    except Exception as exc:
        return {"ok": False, "message": f"Ingestion execution failed: {exc}"}
