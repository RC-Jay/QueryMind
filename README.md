# QueryMind Analytics

An AI-powered analytics platform that lets executive teams query their live business database in plain English and receive instant answers as charts, tables, and metrics.

Built as a standalone application — completely separate from the business's main platform. First deployed for **ChangePay**, an eCommerce platform running across college campuses in India.

---

## Architecture

```
┌─────────────────────────────────────────────┐
│  Next.js Frontend (port 3000)               │
│  Chat UI · KPI Panel · Admin · Auth         │
└────────────────┬────────────────────────────┘
                 │ HTTP / SSE
┌────────────────▼────────────────────────────┐
│  FastAPI Backend (port 8000)                │
│  AI Agent · Tool Loop · JWT Auth            │
│  SQLite (analytics metadata)                │
└────────────────┬────────────────────────────┘
                 │ read-only
┌────────────────▼────────────────────────────┐
│  Business PostgreSQL DB (live)              │
│  Connection URL stored encrypted in SQLite  │
└─────────────────────────────────────────────┘
```

**Key design principle:** Everything business-specific (DB URL, domain model, KPI queries, starter questions) lives in a `business_config` table — not in application code. The same codebase can serve any business by configuring a new deployment.

---

## Project Structure

```
DataAnalysis/
├── backend/          # FastAPI Python backend
├── frontend/         # Next.js TypeScript frontend
├── data/             # SQLite analytics DB (created on first run)
└── .env              # Secrets — never commit this
```

---

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+
- PostgreSQL running with the target business database accessible

### 1. Set up secrets

The `.env` file at the project root is already populated if you ran the setup scripts. Verify it exists:

```bash
cat .env
```

Required variables:
```
ANALYTICS_DB_URL=            # postgresql+asyncpg://user@host:5432/querymind_analytics
                             # (omit to fall back to a local SQLite file — dev only)
CONFIG_ENCRYPTION_KEY=       # Fernet key — python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
JWT_SECRET_KEY=              # openssl rand -hex 32
REDIS_URL=                   # redis://localhost:6379/0 (empty → in-process confirmation broker)

# Optional — only used to bootstrap the LLM config on first run if none exists.
# After first run, the LLM provider/credentials live in the DB (Admin → AI Model).
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_DEPLOYMENT=
AZURE_OPENAI_API_VERSION=
```

> Two secrets are **not** env vars — they're entered via the admin UI and stored
> Fernet-encrypted in the analytics DB:
> - the **business database URL** (Admin → Business Setup)
> - the **LLM provider + API key** (Admin → AI Model — supports Azure OpenAI & Claude)

### 2. Start the backend

```bash
cd backend
source .venv/bin/activate
uvicorn main:app --port 8000 --reload
```

### 3. Start the frontend

```bash
cd frontend
npm run dev
```

### 4. Open the app

Navigate to **http://localhost:3000**

---

## First-Time Setup (new deployment)

```bash
cd backend
source .venv/bin/activate

# 1. Create the analytics database (one-time) and run migrations
createdb querymind_analytics                 # or your managed Postgres
alembic upgrade head                          # builds the schema (Alembic-owned)

# 2. Create the superuser (run once)
python scripts/create_superuser.py

# 3a. ChangePay deployment — seed domain config automatically
python scripts/seed_changepay_config.py

# 3b. Any other business — log in as superuser and configure via
#     Admin → Business Setup in the UI
```

> **Schema changes** are managed by Alembic. After pulling changes that alter
> the schema, run `alembic upgrade head`. (The SQLite dev fallback auto-creates
> tables; Postgres always uses migrations.)

---

## Default Credentials (ChangePay deployment)

| Field | Value |
|-------|-------|
| Email | `admin@changepay.in` |
| Password | `Admin@12345` |

> Change this password immediately after first login in a production environment.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| AI | Pluggable LLM provider (Strategy pattern) — Azure OpenAI & Claude, chosen in Admin → AI Model |
| Backend | Python 3.12, FastAPI (async), asyncpg, SQLAlchemy (aiosqlite) |
| Frontend | Next.js 16, TypeScript, Tailwind CSS, Zustand |
| Charts | Plotly.js |
| Auth | Custom JWT (access + refresh token, httpOnly cookie) |
| Analytics DB | SQLite (users, conversations, business config) |
| Business DB | PostgreSQL (read-only, connection stored encrypted) |
| Tests | pytest + pytest-asyncio (no external deps — fakes for LLM & Postgres) |

Run the backend tests with `cd backend && pytest`. See [`backend/README.md`](backend/README.md)
for architecture (LLM Strategy, dependency injection, central exception handling)
and [`frontend/README.md`](frontend/README.md) for the UI.
