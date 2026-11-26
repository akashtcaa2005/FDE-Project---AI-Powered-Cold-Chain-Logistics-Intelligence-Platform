# FDE – AI-Powered Cold Chain Logistics Intelligence Platform

A Streamlit-based cold-chain logistics dispatch assistant that combines a LangGraph agent, Microsoft SQL Server fleet telemetry, Pinecone SOP retrieval, live corridor weather, and local or cloud language models.

## Features

- Natural-language dispatcher console
- Tool-based SQL telemetry lookup through a restricted read-only view
- Live weather and corridor-risk lookup
- Pinecone semantic search over SOP and incident policy documents
- LangGraph agent orchestration with tool routing
- Streamlit audit-log interface
- Local Ollama, OpenAI, or DeepSeek reasoning modes
- Local Hugging Face or OpenAI embeddings

## Architecture

```text
Streamlit UI
    |
LangGraph orchestrator
    |-- SQL telemetry tool --> SQL Server semantic view
    |-- Corridor tool       --> Open-Meteo API
    `-- SOP tool            --> Pinecone vector index
```

## Technology Stack

- Python 3.12
- Streamlit
- LangGraph and LangChain
- SQLAlchemy and pyodbc
- Microsoft SQL Server
- Pinecone
- Hugging Face embeddings
- OpenAI / DeepSeek-compatible APIs
- Ollama for local inference

## Project Structure

```text
src/orchestrator.py          LangGraph agent graph
src/agent_tools.py           SQL, weather, and SOP tools
src/ui.py                    Streamlit application
scripts/ingest_legacy_data.py
scripts/ingest_sop_pinecone.py
scripts/setup_security_and_view.sql
data/raw/                   Source fleet dataset
data/policy/                SOP policy document
data/cache/                 Ingestion cache
```

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Microsoft ODBC Driver 18 for SQL Server must be installed on the host. On Ubuntu:

```bash
sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18 unixodbc-dev
```

## Configuration

Copy the safe template and provide local values:

```bash
cp .env.example .env
```

Never commit `.env` or place real secrets in source code or SQL scripts.

```dotenv
Agent_llm=OLLAMA
Embeddings_model=LOCAL
Local_Embedding_Model=BAAI/bge-m3
PINECONE_API_KEY=your_pinecone_key
SQL_SERVER_HOST=localhost
SQL_SERVER_PORT=1433
SQL_ADMIN_USER=your_admin_user
SQL_ADMIN_PASSWORD=your_admin_password
SQL_AGENT_USER=USR_FDE_RO
SQL_AGENT_PASSWORD=your_agent_password
SQL_ADMIN_PASSWORD=your_admin_password
```

For cloud reasoning, set `Agent_llm=OPENAI` or `Agent_llm=DEEPSEEK` and configure the corresponding API key.

## Data and Database Setup

1. Start Microsoft SQL Server, or use a Docker container.
2. Update `.env` with SQL credentials.
3. Ingest the fleet dataset:

```bash
python scripts/ingest_legacy_data.py
```

4. Apply `scripts/setup_security_and_view.sql` to create the restricted view and agent login.
5. Create the Pinecone index and ingest SOP content:

```bash
python scripts/ingest_sop_pinecone.py
```

## Run the Application

```bash
streamlit run src/ui.py
```

The application is available at the Streamlit URL printed in the terminal, normally `http://localhost:8501`.

For a direct tool test:

```bash
python src/agent_tools.py
python src/orchestrator.py
```

## Security

- Database and API credentials are loaded from `.env`.
- `.env` and common virtual-environment/cache paths are excluded by `.gitignore`.
- SQL agent access should remain limited to `FDE_VIEWS.VW_ACTIVE_FLEET` and approved audit writes.
- Rotate every password or API key that has ever been committed, even after removing it from current files.
- Review GitHub Actions secrets separately for EC2 and deployment credentials.
