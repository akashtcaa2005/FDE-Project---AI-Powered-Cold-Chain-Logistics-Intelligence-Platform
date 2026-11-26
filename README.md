<div align="center">

# 🧊 FDE Intelligence
### Enterprise Cold Chain Command Center

**An agentic AI operations platform for cold-chain logistics** — a live Streamlit control tower fused with a LangGraph tool-calling AI Dispatcher, enterprise telemetry, vectorized SOP retrieval, and real-time corridor weather in one zero-config, cloud-or-offline system.

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-Multipage%20App-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agentic%20Orchestration-1C3C3C)](https://www.langchain.com/langgraph)
[![SQL Server](https://img.shields.io/badge/SQL%20Server-ODBC%2018-CC2927?logo=microsoftsqlserver&logoColor=white)](https://www.microsoft.com/sql-server)
[![Pinecone](https://img.shields.io/badge/Pinecone-Vector%20Retrieval-000000)](https://www.pinecone.io/)
[![Status](https://img.shields.io/badge/status-active--development-brightgreen)]()
[![License](https://img.shields.io/badge/license-unspecified-lightgrey)]()

</div>

---

## 📖 Table of Contents

1. [Why This Exists](#-why-this-exists)
2. [Traditional Way vs. FDE Agentic Way](#️-traditional-way-vs-fde-agentic-way)
3. [Key Capabilities](#-key-capabilities)
4. [System Architecture](#️-system-architecture)
5. [Technology Stack](#️-technology-stack)
6. [Installation](#-installation-local)
7. [Configuration](#️-configuration)
8. [Database & Data Setup](#️-data-and-database-setup-optional)
9. [Running the Platform](#️-running-the-platform)
10. [Deployment — Streamlit Community Cloud](#️-deployment--streamlit-community-cloud)
11. [Security Model](#-security-model)
12. [Project Structure Reference](#-project-structure-reference)
13. [Roadmap](#️-roadmap)
14. [Disclaimer](#-disclaimer)
15. [License](#-license)

---

## 🎯 Why This Exists

Cold chain failures don't announce themselves — they surface three days later as spoiled pharmaceuticals, rejected produce, or a compliance officer asking why a six-hour excursion above the SOP ceiling went unnoticed. Traditional operations stitch this picture together *after the fact*, across spreadsheets, carrier portals, and phone calls.

**FDE Intelligence** closes that gap. Every shipment, every corridor, every thermal reading streams into a single command center — where a human dispatcher, or an autonomous AI agent using the exact same governed tools, can see risk **before** it becomes loss.

---

## ⚔️ Traditional Way vs. FDE Agentic Way

This is the core shift the platform makes. It is not "a dashboard" — it is a dashboard **plus** an agent that reasons over the same live data a human would, using the same tools, under the same guardrails, with every action logged.

| Dimension | 🐢 Traditional Cold Chain Ops | 🤖 FDE Agentic Intelligence |
|---|---|---|
| **Monitoring** | Manual spreadsheet pulls, periodic SCADA checks, siloed per-carrier dashboards | Unified 11-page live command center polling `VW_ACTIVE_FLEET` continuously |
| **Excursion detection** | Discovered retroactively — often after delivery, via paperwork or customer complaint | Continuous SOP v2.4 (`0.0°C–4.0°C`) compliance tracking with live excursion logging |
| **SOP lookup** | Dispatcher searches PDFs/binders or calls compliance — minutes to hours | Pinecone semantic search over indexed SOP documents — sub-second, cited, with local markdown fallback |
| **Root-cause analysis** | Analyst manually joins fleet logs, weather reports, and route data across disconnected tools | Agent autonomously chains `query_telemetry_db` → `fetch_corridor_conditions` → `search_compliance_sop` in a single reasoning pass |
| **Weather & corridor risk** | Checked ad hoc, often after a delay is already reported | Live Open-Meteo current conditions + 24h forecast fused into corridor risk scores in real time |
| **Decision support** | Experience-based judgment from senior dispatchers; tribal knowledge walks out the door when they do | Structured, SQL-grounded executive briefings and downloadable Markdown dispatch reports, on demand |
| **Audit trail** | Scattered emails, call logs, and manual incident write-ups | Immutable, admin-gated `AgentAuditLog` (SQL Server) with a local SQLite mirror — every query and action recorded |
| **Escalation speed** | Hours — detect, investigate, decide, act, in sequence | Minutes — risk, SOP context, and corridor conditions surface together in one dispatch inquiry |
| **Scalability** | Adding fleets or lanes means adding headcount | Adding fleets or lanes means adding rows to the same view — agent logic is unchanged |
| **Resilience** | Single point of failure if the one person who "knows the system" is unavailable | Multi-provider LLM fallback chain (Groq → Gemini → OpenAI → DeepSeek → local Ollama) plus CSV/offline data fallback — degrades gracefully, never goes dark |
| **Human role** | Full-time manual triage and lookup | Shifts to **decision-maker and authorizer** — the agent proposes, a human authorizes every operational action |

> **Design principle, not just a pitch line:** the AI Dispatcher never bypasses human authority or touches data outside its read-only scope. It uses the *same* governed telemetry, SOP corpus, and weather feeds a human dispatcher would — just faster, more consistently, and with a permanent audit record.

---

## 🧩 Key Capabilities

| Page | Module | What It Does |
|---|---|---|
| **Overview Command Center** | `src/app_pages/overview.py` | 8 KPI cards with period deltas and sparklines, temperature vs. SOP threshold trends, risk/delay/corridor visualizations, live alert feed, data-grounded executive briefings |
| **Live Fleet Intelligence** | `src/app_pages/live_fleet.py` | Interactive PyDeck geospatial map, multi-criteria filtering, record detail inspector with live GPS weather lookup, sortable/paginated telemetry ledger |
| **Shipment Intelligence** | `src/app_pages/shipment_intel.py` | Movement filtering, delay probability analytics, extended dataset inspection, CSV exports |
| **Cold Chain Monitoring** | `src/app_pages/cold_chain.py` | SOP v2.4 Fresh Perishables (`0.0°C–4.0°C`) compliance tracking, selectable cargo temperature profiles, excursion logging |
| **Route & Weather Intelligence** | `route_intel.py`, `weather_intel.py` | Corridor risk comparisons, SOP §2 port-congestion diversion monitoring (`>7.0` → San Bernardino), live Open-Meteo current + 24h forecasts kept visually distinct from derived risk scores |
| **FDE AI Dispatcher** | `src/app_pages/ai_dispatcher.py` | Multi-session LangGraph copilot (`src/orchestrator.py`) enforcing `src/prompts/system_prompt.txt`, clickable Suggested Dispatch Inquiries, tool execution trace inspection, SQL table parsing, Markdown report downloads, automatic `429`-quota fallback to Groq |
| **Analytics & SOP Knowledge Base** | `analytics.py`, `sop_kb.py` | Multi-dimensional filtering, CSV/Markdown report generation, Pinecone semantic search (local markdown fallback), policy indexing via `scripts/ingest_sop_pinecone.py` |
| **Audit Center & Settings** | `audit_center.py`, `settings.py` | Separated-privilege SQL Server admin gate (`FDE_VIEWS.AgentAuditLog`), local SQLite audit persistence, live subsystem health checks, runtime model/provider selection |

---

## 🏗️ System Architecture

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
scripts/ingest_legacy_data.py      CSV → dbo.TBL_SC_FLEET_HIST_RAW
scripts/setup_security_and_view.sql  FDE_VIEWS.VW_ACTIVE_FLEET & USR_FDE_RO RBAC
scripts/ingest_sop_pinecone.py     Policy documents → Pinecone index
```

### 🔄 Agent Reasoning Flow

```text
 Dispatcher asks a question in the AI Dispatcher
                  │
                  ▼
   ai_dispatcher.py  ──►  orchestrator.py  (LangGraph fde_agent)
                                  │
                                  │   system_prompt.txt enforces a
                                  │   structured operational response
                                  │
            ┌─────────────────────┼─────────────────────┐
            ▼                     ▼                      ▼
  query_telemetry_db()  fetch_corridor_conditions()  search_compliance_sop()
  (SQL Server /          (Open-Meteo live +           (Pinecone vector search /
   CSV mirror,            24h forecast)                 local SOP markdown)
   read-only)
            │                     │                      │
            └─────────────────────┼─────────────────────┘
                                  ▼
         Structured dispatch response + tool trace + Markdown report
                                  │
                                  ▼
          AgentAuditLog (SQL Server, admin-gated) + local SQLite mirror
```

---

## 🛠️ Technology Stack

| Layer | Technologies |
|---|---|
| **Runtime** | Python 3.12+ |
| **Frontend** | Streamlit (`st.navigation`, `st.Page`, `st.metric`, `st.pydeck_chart`, `st.altair_chart`) |
| **Agent Orchestration** | LangGraph & LangChain (`langchain-openai`, `langchain-huggingface`, `langchain-pinecone`, `langchain-community`, `langchain-ollama`) |
| **LLM Backends** | Groq (`openai/gpt-oss-120b`) · Google Gemini (`gemini-3.8-flash`) · OpenAI (`gpt-4o`) · DeepSeek (`deepseek-v4-flash`) · local Ollama (`qwen2.5:7b`) |
| **Telemetry & Storage** | Microsoft SQL Server (`SQLAlchemy`, `pyodbc`, ODBC Driver 18) with automatic read-only SQLite CSV mirror fallback and local audit cache (`data/cache/fde_audit.db`) |
| **Vector Retrieval** | Pinecone + Hugging Face `BAAI/bge-m3` (or OpenAI embeddings), with local markdown fallback (`data/policy/Cold_Chain_Incident_SOP_v2.md`) |
| **Weather** | Open-Meteo REST API (no API key required) |

---

## 🚀 Installation (Local)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Optional** — Microsoft ODBC Driver 18 for SQL Server (Ubuntu; only needed for a live SQL Server connection):

```bash
sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18 unixodbc-dev
```

---

## ⚙️ Configuration

```bash
cp .env.example .env
```

Populate `.env` with your credentials. **Never commit `.env` or expose secrets in source code.**

| Variable | Default / Options | Description |
|---|---|---|
| `Agent_llm` | `GROQ` (if `GROQ_API_KEY` set) else `OLLAMA` | Active LLM provider (`GROQ`, `GEMINI`, `OPENAI`, `DEEPSEEK`, `OLLAMA`) |
| `GROQ_API_KEY` / `GROQ_MODEL` | `openai/gpt-oss-120b` | Groq API key & model (also the automatic `429`-quota fallback) |
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

---

## 🗄️ Data and Database Setup (Optional)

The app runs **zero-config out of the box** — without a live SQL Server or Pinecone index, it automatically falls back to the bundled CSV dataset and local SOP markdown. To enable the full enterprise stack:

1. Start Microsoft SQL Server (or a Docker container) and update `.env`.
2. Ingest the fleet dataset:
   ```bash
   python scripts/ingest_legacy_data.py
   ```
3. Apply `scripts/setup_security_and_view.sql` to create `FDE_VIEWS.VW_ACTIVE_FLEET` and `USR_FDE_RO`.
4. Provision and index the Pinecone SOP knowledge base:
   ```bash
   python scripts/ingest_sop_pinecone.py
   ```

---

## ▶️ Running the Platform

```bash
streamlit run src/ui.py
```

Open the printed URL — normally `http://localhost:8501`.

For direct tool or orchestrator verification from the CLI:

```bash
python src/agent_tools.py
python src/orchestrator.py
```

---

## ☁️ Deployment — Streamlit Community Cloud

1. Push this repository to GitHub and open [share.streamlit.io/deploy](https://share.streamlit.io/deploy).
2. Configure the deployment:
   - **Repository**: `akashtcaa2005/FDE-Project---AI-Powered-Cold-Chain-Logistics-Intelligence-Platform`
   - **Branch**: `main`
   - **Main file path**: `src/ui.py`
3. Open **Advanced settings → Secrets** (or **Manage app → Settings → Secrets**) and add credentials in TOML format:
   ```toml
   Agent_llm = "GROQ"
   GROQ_API_KEY = "your-groq-key"
   GROQ_MODEL = "openai/gpt-oss-120b"

   PINECONE_API_KEY = "your-pinecone-key"
   Embeddings_model = "LOCAL"
   Local_Embedding_Model = "BAAI/bge-m3"
   ```
4. Click **Deploy!**

---

## 🔐 Security Model

- Credentials live exclusively in `.env` (or Streamlit Cloud Secrets) and are never rendered in the frontend.
- `query_telemetry_db` enforces single-statement, read-only `SELECT` validation and authenticates as `USR_FDE_RO`.
- Reading `FDE_VIEWS.AgentAuditLog` in the Audit Center requires administrative credentials (`SQL_ADMIN_USER` / `SQL_ADMIN_PASSWORD`).
- AI Dispatcher outputs are **decision-support only** — every operational action still requires human authorization.
- A layered fallback design (SQL → CSV, Pinecone → local markdown, Groq → Gemini → OpenAI → DeepSeek → Ollama) means no single credential, vendor, or outage can take the platform fully offline.

---

## 📂 Project Structure Reference

```text
.
├── data/
│   ├── raw/                       Bundled CSV fleet dataset (offline fallback)
│   ├── policy/                    Local SOP markdown (Pinecone fallback)
│   └── cache/                     Local SQLite audit mirror
├── scripts/
│   ├── ingest_legacy_data.py
│   ├── setup_security_and_view.sql
│   └── ingest_sop_pinecone.py
├── src/
│   ├── app_pages/                 11 Streamlit command-center pages
│   ├── components/                Shared UI shell
│   ├── prompts/                   Agent system prompt
│   ├── config.py
│   ├── data_access.py
│   ├── analytics.py
│   ├── charts.py
│   ├── orchestrator.py
│   ├── agent_tools.py
│   └── ui.py                      Entry point
├── .env.example
└── requirements.txt
```

---

## 🗺️ Roadmap

- [ ] Role-based access control for dispatcher, admin, and read-only viewer personas
- [ ] Automated SOP-excursion → incident-ticket creation (webhook to Jira/ServiceNow)
- [ ] Predictive ETA/delay model trained on historical `VW_ACTIVE_FLEET` telemetry
- [ ] Multi-tenant support for managing several fleets/clients from one deployment
- [ ] Slack/Teams alert bridge for real-time excursion notifications

---

## ⚠️ Disclaimer

FDE Intelligence is an operational decision-support tool. The AI Dispatcher's outputs — risk scores, briefings, and recommendations — are advisory and must be reviewed by a qualified human dispatcher before any action is taken. The platform does not replace regulatory compliance processes, cold-chain certification requirements, or professional logistics judgment.

---

## 📄 License

Add your preferred license (MIT, Apache-2.0, etc.) here before public release.

<div align="center">

**Built solo — architected to run enterprise-grade cold chain operations from a single repository.**

</div>
