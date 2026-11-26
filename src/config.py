"""Centralized configuration, SOP profiles, and corridor reference metadata."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

SRC_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SRC_DIR.parent
ASSETS_DIR = SRC_DIR / "assets"
APP_PAGES_DIR = SRC_DIR / "app_pages"
PROMPTS_DIR = SRC_DIR / "prompts"
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_PATH = DATA_DIR / "raw" / "dynamic_supply_chain_logistics_dataset.csv"
POLICY_DIR = DATA_DIR / "policy"
CACHE_DIR = DATA_DIR / "cache"
AUDIT_DB_PATH = CACHE_DIR / "fde_audit.db"
HASH_CACHE_FILE = CACHE_DIR / "ingestion_hash_cache.json"

APP_NAME = "FDE Intelligence"
APP_SUBTITLE = "Enterprise Cold Chain Command Center"
APP_VERSION = "2.0.0"

# Load project .env once at startup
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class ColdChainProfile:
    """Temperature compliance profile with source attribution."""

    key: str
    label: str
    min_temp_c: float
    warning_temp_c: float
    critical_temp_c: float
    source: str
    sop_verified: bool


COLD_CHAIN_PROFILES: dict[str, ColdChainProfile] = {
    "fresh_perishables": ColdChainProfile(
        key="fresh_perishables",
        label="Fresh Perishables (SOP v2.4)",
        min_temp_c=0.0,
        warning_temp_c=3.2,
        critical_temp_c=4.0,
        source="Cold_Chain_Incident_SOP_v2.md §1 (0.0°C–4.0°C, >4.0°C Critical Breach)",
        sop_verified=True,
    ),
    "vaccines_pharma": ColdChainProfile(
        key="vaccines_pharma",
        label="Vaccines & Biologics (2–8°C Profile)",
        min_temp_c=2.0,
        warning_temp_c=7.0,
        critical_temp_c=8.0,
        source="Configurable WHO/GDP 2.0°C–8.0°C guideline (not in SOP v2.4)",
        sop_verified=False,
    ),
    "dairy": ColdChainProfile(
        key="dairy",
        label="Dairy & Chilled Beverages (1–4°C Profile)",
        min_temp_c=1.0,
        warning_temp_c=3.5,
        critical_temp_c=4.0,
        source="Configurable chilled dairy 1.0°C–4.0°C profile (not in SOP v2.4)",
        sop_verified=False,
    ),
    "seafood": ColdChainProfile(
        key="seafood",
        label="Fresh Seafood (-1–2°C Profile)",
        min_temp_c=-1.0,
        warning_temp_c=1.5,
        critical_temp_c=2.0,
        source="Configurable fresh seafood -1.0°C–2.0°C profile (not in SOP v2.4)",
        sop_verified=False,
    ),
    "frozen": ColdChainProfile(
        key="frozen",
        label="Deep Frozen (-25 to -18°C Profile)",
        min_temp_c=-25.0,
        warning_temp_c=-19.5,
        critical_temp_c=-18.0,
        source="Configurable frozen -25.0°C to -18.0°C profile (not in SOP v2.4)",
        sop_verified=False,
    ),
}

# SOP v2.4 numeric operational rules
SOP_PORT_CONGESTION_CRITICAL = 7.0  # §2: divert to Inland Empire Overflow Depot (San Bernardino)
SOP_DELAY_ESCALATION_THRESHOLD = 0.65  # §3: High Risk + delay_probability > 0.65 -> Tier 2 escalation
SOP_ETA_DIVERSION_HOURS = 1.0  # §1: temp > 4.0C and ETA delay > 1 hr -> emergency cold-storage


@dataclass(frozen=True)
class CorridorHub:
    """Reference logistics corridor coordinates within dataset bounds (Lat 30-50, Lon -120 to -70)."""

    code: str
    name: str
    region: str
    latitude: float
    longitude: float
    notes: str


CORRIDOR_HUBS: list[CorridorHub] = [
    CorridorHub(
        code="SOCAL-LA",
        name="Port of Los Angeles / Long Beach",
        region="West Coast",
        latitude=33.77,
        longitude=-118.19,
        notes="Primary SOP v2.4 maritime gateway; overflow diversion to San Bernardino",
    ),
    CorridorHub(
        code="IE-SB",
        name="Inland Empire Overflow Depot (San Bernardino)",
        region="West Coast",
        latitude=34.11,
        longitude=-117.29,
        notes="SOP v2.4 designated cross-dock diversion hub",
    ),
    CorridorHub(
        code="NORCAL-OAK",
        name="Oakland / Bay Area Corridor",
        region="West Coast",
        latitude=37.80,
        longitude=-122.27,
        notes="Northern California cold-storage & port interchange",
    ),
    CorridorHub(
        code="PNW-SEA",
        name="Seattle / Tacoma Corridor",
        region="Pacific Northwest",
        latitude=47.25,
        longitude=-122.44,
        notes="Pacific Northwest northern cold-chain corridor",
    ),
    CorridorHub(
        code="MW-CHI",
        name="Chicago Intermodal Hub",
        region="Midwest",
        latitude=41.88,
        longitude=-87.63,
        notes="Central rail/trucking cold-chain consolidation hub",
    ),
    CorridorHub(
        code="EC-NYNJ",
        name="Port of NY / NJ Corridor",
        region="East Coast",
        latitude=40.67,
        longitude=-74.15,
        notes="East Coast maritime & perishable distribution corridor",
    ),
    CorridorHub(
        code="SE-SAV",
        name="Savannah / Southeast Corridor",
        region="Southeast",
        latitude=32.08,
        longitude=-81.09,
        notes="Southeast Atlantic port & refrigerated freight corridor",
    ),
]


def assign_corridor_zone(lat: float, lon: float) -> str:
    """Assign an honest geographic corridor bucket based on coordinates."""
    if lon <= -114.0:
        if lat < 36.0:
            return "Southern California / Southwest"
        if lat < 42.0:
            return "Northern California / Pacific"
        return "Pacific Northwest"
    if lon <= -95.0:
        if lat < 37.0:
            return "South Central / Mountain"
        return "North Central / Plains"
    if lon <= -82.0:
        if lat < 37.0:
            return "Gulf / Southeast Inland"
        return "Midwest / Great Lakes"
    if lat < 37.0:
        return "Southeast Atlantic"
    return "Northeast / Mid-Atlantic"


def get_safe_runtime_summary() -> dict[str, str]:
    """Return non-secret configuration values for UI status displays."""
    return {
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "agent_llm": os.getenv("Agent_llm", "OLLAMA").strip().upper(),
        "groq_model": os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip(),
        "gemini_model": os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip(),
        "embeddings_mode": os.getenv("Embeddings_model", "LOCAL").strip().upper(),
        "local_embedding_model": os.getenv("Local_Embedding_Model", "BAAI/bge-m3").strip(),
        "sql_host": os.getenv("SQL_SERVER_HOST", "localhost").strip(),
        "sql_port": os.getenv("SQL_SERVER_PORT", "1433").strip(),
        "sql_agent_user": os.getenv("SQL_AGENT_USER", "USR_FDE_RO").strip(),
        "sql_admin_user": os.getenv("SQL_ADMIN_USER", "sa").strip(),
        "pinecone_configured": "Configured" if bool(os.getenv("PINECONE_API_KEY", "").strip()) else "Missing",
        "groq_configured": "Configured" if bool(os.getenv("GROQ_API_KEY", "").strip()) else "Missing",
        "gemini_configured": "Configured" if bool(os.getenv("GEMINI_API_KEY", "").strip()) else "Missing",
        "openai_configured": "Configured" if bool(os.getenv("OPENAI_API_KEY", "").strip()) else "Missing",
        "deepseek_configured": "Configured" if bool(os.getenv("DEEPSEEK_API_KEY", "").strip()) else "Missing",
    }
