# FDE Intelligence — Enterprise Cold Chain Command Center

An enterprise cold-chain logistics intelligence platform combining a multi-page Streamlit control tower, a LangGraph tool-calling AI Dispatcher (`fde_agent`), Microsoft SQL Server semantic telemetry (`FDE_VIEWS.VW_ACTIVE_FLEET`), Pinecone SOP vector retrieval, live Open-Meteo corridor weather, and structured audit logging.

## Key Capabilities

- **Overview Command Center**: 8 KPI cards with period deltas and sparklines, temperature vs. SOP threshold trends, risk/delay/corridor visualizations, operational alert feed, and data-grounded executive briefings.
- **Live Fleet Intelligence**: Interactive PyDeck geospatial map, multi-criteria filtering, record detail inspector with live GPS weather lookup, and sortable/paginated telemetry ledger.
- **Shipment Intelligence**: Movement filtering, delay probability analytics, extended dataset inspection, and CSV exports.
- **Cold Chain Monitoring**: SOP v2.4 Fresh Perishables (`0.0°C–4.0°C`) compliance tracking plus selectable cargo temperature profiles and excursion logging.
- **Route & Weather Intelligence**: Corridor risk comparisons, SOP §2 port congestion diversion monitoring (`>7.0` to San Bernardino), and live Open-Meteo current conditions + 24-hour forecasts clearly separated from derived risk scores.
- **FDE AI Dispatcher**: Multi-session LangGraph copilot (`src/orchestrator.py`) enforcing `src/prompts/system_prompt.txt`, tool execution trace inspection, SQL table parsing, and report downloads using `query_telemetry_db`, `fetch_corridor_conditions`, and `search_compliance_sop`.
- **Analytics & SOP Knowledge Base**: Multi-dimensional filtering, CSV/Markdown report generation, Pinecone semantic search, and safe policy document indexing (`scripts/ingest_sop_pinecone.py`).
- **Audit Center & Settings**: Separated-privilege SQL Server admin gate (`FDE_VIEWS.AgentAuditLog`), local SQLite audit trail persistence (`data/cache/fde_audit.db`), live subsystem health checks, and safe runtime model selection.

## Architecture

```text
src/ui.py                          Streamlit multipage shell (st.navigation)
src/app_pages/                     11 command-center pages
src/components/shell.py            Shared session state, top bar, sidebar footer
src/config.py                      Paths, SOP profiles, corridor hubs, safe metadata
src/data_access.py                 SQL Server / CSV fallback, weather, Pinecone, audit
src/analytics.py                   KPIs, SOP alerts, executive briefings, reports
src/charts.py                      Altair charts and PyDeck geospatial visualization
src/orchestrator.py                LangGraph fde_agent with enforced system prompt
src/agent_tools.py                 query_telemetry_db, fetch_corridor_conditions, search_compliance_sop
src/prompts/system_prompt.txt      Structured operational response format
scripts/ingest_legacy_data.py      CSV -> dbo.TBL_SC_FLEET_HIST_RAW
scripts/setup_security_and_view.sql  FDE_VIEWS.VW_ACTIVE_FLEET & USR_FDE_RO RBAC
scripts/ingest_sop_pinecone.py     Policy documents -> Pinecone index
```

## Technology Stack

- Python 3.12+
- Streamlit (`st.navigation`, `st.Page`, `st.metric`, `st.pydeck_chart`, `st.altair_chart`)
- LangGraph and LangChain (`langchain-openai`, `langchain-huggingface`, `langchain-pinecone`, `langchain-community`)
- Microsoft SQL Server (`SQLAlchemy`, `pyodbc`, ODBC Driver 18) with read-only SQLite CSV mirror fallback when offline
- Pinecone Vector Database + Hugging Face `BAAI/bge-m3` / OpenAI embeddings
- Gemini / OpenAI / DeepSeek / Ollama LLM backends
- Open-Meteo REST API

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Microsoft ODBC Driver 18 for SQL Server (Ubuntu):

```bash
sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18 unixodbc-dev
```

## Configuration

```bash
cp .env.example .env
```

Configure `.env` with your local credentials (`PINECONE_API_KEY`, `GEMINI_API_KEY` / `OPENAI_API_KEY` / `DEEPSEEK_API_KEY`, `SQL_*`, `Agent_llm`, `Embeddings_model`). Never commit `.env` or expose credentials in source code.

## Data and Database Setup

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

## Run the Application

```bash
streamlit run src/ui.py
```

Open the printed URL (normally `http://localhost:8501`).

For direct tool or CLI orchestrator verification:

```bash
python src/agent_tools.py
python src/orchestrator.py
```

## Security

- Credentials reside exclusively in `.env` and are never rendered in the frontend.
- `query_telemetry_db` enforces single-statement read-only `SELECT` validation and uses `USR_FDE_RO`.
- Reading `FDE_VIEWS.AgentAuditLog` in the Audit Center requires administrative credentials (`SQL_ADMIN_USER` / `SQL_ADMIN_PASSWORD`).
- AI Dispatcher outputs are decision-support only; human authorization is required for operational actions.
