# FDE Intelligence — Enterprise Cold Chain Command Center

An enterprise cold-chain logistics intelligence platform combining an 11-page Streamlit control tower, a LangGraph tool-calling AI Dispatcher (`fde_agent`), Microsoft SQL Server semantic telemetry (`FDE_VIEWS.VW_ACTIVE_FLEET`), Pinecone SOP vector retrieval, live Open-Meteo corridor weather, and structured audit logging — with full offline/cloud fallbacks for zero-config deployment.

## Key Capabilities

- **Overview Command Center** (`src/app_pages/overview.py`): 8 KPI cards with period deltas and sparklines, temperature vs. SOP threshold trends, risk/delay/corridor visualizations, operational alert feed, and data-grounded executive briefings.
- **Live Fleet Intelligence** (`src/app_pages/live_fleet.py`): Interactive PyDeck geospatial map, multi-criteria filtering, record detail inspector with live GPS weather lookup, and sortable/paginated telemetry ledger.
- **Shipment Intelligence** (`src/app_pages/shipment_intel.py`): Movement filtering, delay probability analytics, extended dataset inspection, and CSV exports.
- **Cold Chain Monitoring** (`src/app_pages/cold_chain.py`): SOP v2.4 Fresh Perishables (`0.0°C–4.0°C`) compliance tracking, selectable cargo temperature profiles, and excursion logging.
- **Route & Weather Intelligence** (`src/app_pages/route_intel.py`, `src/app_pages/weather_intel.py`): Corridor risk comparisons, SOP §2 port congestion diversion monitoring (`>7.0` to San Bernardino), and live Open-Meteo current conditions + 24-hour forecasts clearly separated from derived risk scores.
- **FDE AI Dispatcher** (`src/app_pages/ai_dispatcher.py`): Multi-session LangGraph copilot (`src/orchestrator.py`) enforcing `src/prompts/system_prompt.txt`, clickable Suggested Dispatch Inquiries that auto-fill the chat input, tool execution trace inspection, SQL table parsing, Markdown report downloads, and automatic `429` quota fallback to Groq when `GROQ_API_KEY` is configured.
- **Analytics & SOP Knowledge Base** (`src/app_pages/analytics.py`, `src/app_pages/sop_kb.py`): Multi-dimensional filtering, CSV/Markdown report generation, Pinecone semantic search (with local markdown fallback on `data/policy/`), and policy document indexing (`scripts/ingest_sop_pinecone.py`).
- **Audit Center & Settings** (`src/app_pages/audit_center.py`, `src/app_pages/settings.py`): Separated-privilege SQL Server admin gate (`FDE_VIEWS.AgentAuditLog`), local SQLite audit trail persistence (`data/cache/fde_audit.db`), live subsystem health checks, and runtime model/provider selection.

## Architecture

```text
src/ui.py                          Streamlit multipage shell (st.navigation)
src/app_pages/                     11 command-center pages
  ├── overview.py                  Executive KPIs, trends & alert feed
  ├── live_fleet.py                PyDeck fleet map & telemetry inspector
  ├── shipment_intel.py            Delay analytics & shipment ledger
  ├── cold_chain.py                SOP v2.4 thermal excursion monitoring
  ├── route_intel.py               Corridor risk & port diversion tracking
  ├── weather_intel.py             Open-Meteo live & 24h corridor weather
  ├── ai_dispatcher.py             LangGraph AI Dispatcher & trace viewer
  ├── analytics.py                 Custom filters & CSV/Markdown exports
  ├── sop_kb.py                    Pinecone / local SOP semantic search
  ├── audit_center.py              Admin-gated audit logs & SQLite trail
  └── settings.py                  Runtime provider/model & health checks
src/components/shell.py            Shared session state, top bar, sidebar footer
src/config.py                      Paths, SOP profiles, corridor hubs, safe metadata
src/data_access.py                 SQL Server / CSV fallback, weather, Pinecone, audit
src/analytics.py                   KPIs, SOP alerts, executive briefings, reports
src/charts.py                      Altair charts and PyDeck geospatial visualization
src/orchestrator.py                LangGraph fde_agent with multi-provider factory
src/agent_tools.py                 query_telemetry_db, fetch_corridor_conditions, search_compliance_sop
src/prompts/system_prompt.txt      Structured operational response format
scripts/ingest_legacy_data.py      CSV -> dbo.TBL_SC_FLEET_HIST_RAW
scripts/setup_security_and_view.sql  FDE_VIEWS.VW_ACTIVE_FLEET & USR_FDE_RO RBAC
scripts/ingest_sop_pinecone.py     Policy documents -> Pinecone index
```

## Technology Stack

- **Runtime**: Python 3.12+
- **Frontend**: Streamlit (`st.navigation`, `st.Page`, `st.metric`, `st.pydeck_chart`, `st.altair_chart`)
- **Agent Orchestration**: LangGraph & LangChain (`langchain-openai`, `langchain-huggingface`, `langchain-pinecone`, `langchain-community`, `langchain-ollama`)
- **LLM Backends**: Groq (`openai/gpt-oss-120b`), Google Gemini (`gemini-3.8-flash`), OpenAI (`gpt-4o`), DeepSeek (`deepseek-v4-flash`), and local Ollama (`qwen2.5:7b`)
- **Telemetry & Storage**: Microsoft SQL Server (`SQLAlchemy`, `pyodbc`, ODBC Driver 18) with automatic read-only SQLite CSV mirror fallback (`data/raw/dynamic_supply_chain_logistics_dataset.csv`) and local audit cache (`data/cache/fde_audit.db`)
- **Vector Retrieval**: Pinecone + Hugging Face `BAAI/bge-m3` (or OpenAI embeddings) with local markdown fallback (`data/policy/Cold_Chain_Incident_SOP_v2.md`)
- **Weather**: Open-Meteo REST API (no API key required)

## Installation (Local)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Optional — Microsoft ODBC Driver 18 for SQL Server (Ubuntu, only needed if connecting to live SQL Server):

```bash
sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18 unixodbc-dev
```

## Configuration

```bash
cp .env.example .env
```

Configure `.env` with your credentials. Never commit `.env` or expose secrets in source code.

| Variable | Default / Options | Description |
|---|---|---|
| `Agent_llm` | `GROQ` (if `GROQ_API_KEY` set) else `OLLAMA` | Active LLM provider (`GROQ`, `GEMINI`, `OPENAI`, `DEEPSEEK`, `OLLAMA`) |
| `GROQ_API_KEY` / `GROQ_MODEL` | `openai/gpt-oss-120b` | Groq API key & model (also used as automatic `429` quota fallback) |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | `gemini-3.8-flash` | Google Gemini API key & model |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | `gpt-4o` | OpenAI API key & model |
| `DEEPSEEK_API_KEY` / `DEEPSEEK_MODEL` | `deepseek-v4-flash` | DeepSeek API key & model |
| `OLLAMA_MODEL` | `qwen2.5:7b` | Local Ollama model |
| `PINECONE_API_KEY` | — | Pinecone vector DB key (falls back to `data/policy/` if unset) |
| `Embeddings_model` | `LOCAL` (`LOCAL` or `OPENAI`) | Embedding backend |
| `Local_Embedding_Model` | `BAAI/bge-m3` | Hugging Face embedding model |
| `SQL_SERVER_HOST` / `SQL_SERVER_PORT` | `localhost` / `1433` | SQL Server host & port (falls back to CSV mirror if unreachable) |
| `SQL_AGENT_USER` / `SQL_AGENT_PASSWORD` | `USR_FDE_RO` | Read-only SQL telemetry credentials |
| `SQL_ADMIN_USER` / `SQL_ADMIN_PASSWORD` | `sa` | Admin credentials for Audit Center & ingestion scripts |

## Data and Database Setup (Optional)

If running without live SQL Server or Pinecone, the app automatically falls back to the bundled CSV dataset and local SOP markdown. To enable the full enterprise stack:

1. Start Microsoft SQL Server (or Docker container) and update `.env`.
2. Ingest the fleet dataset:
   ```bash
   python scripts/ingest_legacy_data.py
   ```
3. Apply `scripts/setup_security_and_view.sql` to create `FDE_VIEWS.VW_ACTIVE_FLEET` and `USR_FDE_RO`.
4. Provision and index the Pinecone SOP knowledge base:
   ```bash
   python scripts/ingest_sop_pinecone.py
   ```

## Run Locally

```bash
streamlit run src/ui.py
```

Open the printed URL (normally `http://localhost:8501`).

For direct tool or CLI orchestrator verification:

```bash
python src/agent_tools.py
python src/orchestrator.py
```

## Deploy on Streamlit Community Cloud

1. Push this repository to GitHub and open [share.streamlit.io/deploy](https://share.streamlit.io/deploy).
2. Set:
   - **Repository**: `akashtcaa2005/FDE-Project---AI-Powered-Cold-Chain-Logistics-Intelligence-Platform`
   - **Branch**: `main`
   - **Main file path**: `src/ui.py`
3. Open **Advanced settings → Secrets** (or **Manage app → Settings → Secrets**) and add your keys in TOML format:
   ```toml
   Agent_llm = "GROQ"
   GROQ_API_KEY = "your-groq-key"
   GROQ_MODEL = "openai/gpt-oss-120b"

   PINECONE_API_KEY = "your-pinecone-key"
   Embeddings_model = "LOCAL"
   Local_Embedding_Model = "BAAI/bge-m3"
   ```
4. Click **Deploy!**.

## Security

- Credentials reside exclusively in `.env` (or Streamlit Cloud Secrets) and are never rendered in the frontend.
- `query_telemetry_db` enforces single-statement read-only `SELECT` validation and uses `USR_FDE_RO`.
- Reading `FDE_VIEWS.AgentAuditLog` in the Audit Center requires administrative credentials (`SQL_ADMIN_USER` / `SQL_ADMIN_PASSWORD`).
- AI Dispatcher outputs are decision-support only; human authorization is required for operational actions.
