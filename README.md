# 🏯 Shogun — AI Agent Framework

A GUI-first AI agent framework with structured memory, governed autonomy, and OpenClaw compatibility.

Built with Python, FastAPI, Gradio, and SQLAlchemy. Ships with [OpenClaw College](https://github.com/AlphaHorizon-AI/OpenClawCollege.com) as the default skill learning source.

---

## Install from GitHub

```bash
# Clone
git clone https://github.com/YOUR_ORG/Shogun.git
cd Shogun

# Create virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux / Mac
# .venv\Scripts\activate         # Windows

# Install (all dependencies included — no Docker needed)
pip install -e ".[dev]"

# Copy environment config
cp .env.example .env

# Create database + seed defaults
python -m shogun.bootstrap

# Launch
python main.py
```

- **Tenshu UI**: http://localhost:8000/
- **API Docs**: http://localhost:8000/docs

That's it. **No Docker, no external services.** SQLite + Qdrant embedded handles everything locally.

---

## One-Liner Install (pip from GitHub)

```bash
pip install git+https://github.com/YOUR_ORG/Shogun.git
```

Then in your code:

```python
from shogun.app import create_app
from shogun.bootstrap import bootstrap

import asyncio
asyncio.run(bootstrap())  # Creates DB + seeds
app = create_app()        # FastAPI app ready to serve
```

---

## Architecture

```
shogun/
├── api/             # 13 FastAPI REST routers (/api/v1/*)
├── db/              # SQLAlchemy ORM models (SQLite or PostgreSQL)
├── engine/          # Agent runtime + memory salience engine
├── integrations/    # OpenClaw College client
├── schemas/         # Pydantic request/response contracts
├── services/        # Business logic layer
└── ui/              # Gradio "Tenshu" mission control UI

main.py              # Entrypoint — mounts Gradio on FastAPI
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| API | FastAPI |
| Validation | Pydantic v2 |
| Database | SQLite (default) / PostgreSQL (optional) |
| ORM | SQLAlchemy 2.0 (async) |
| Vector Memory | Qdrant (embedded) |
| UI | Gradio |
| HTTP Client | httpx |
| Scheduling | APScheduler |
| Skill Source | [OpenClawCollege.com](https://www.openclawcollege.com) |

## Key Concepts

| Name | Purpose |
|------|---------|
| **Shogun** | Primary orchestrator agent |
| **Samurai** | Specialized subagents |
| **The Tenshu** | Mission control UI |
| **Archives** | Structured long-term memory |
| **Kaizen** | Constitutional governance layer |
| **Bushido** | Reflection & self-improvement engine |
| **The Katana** | Tools, APIs, model routing |
| **The Torii** | Security & permissions gateway |
| **The Dojo** | Skills system — powered by OpenClaw College |

## Optional: PostgreSQL Mode

For production, switch to PostgreSQL:

```bash
# Install the postgres driver
pip install -e ".[postgres]"

# Update .env
DATABASE_URL=postgresql+asyncpg://shogun:pass@localhost:5432/shogun

# Use docker-compose for PostgreSQL + standalone Qdrant
docker compose up -d
```

## License

Proprietary
