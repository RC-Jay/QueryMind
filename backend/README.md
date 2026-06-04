# QueryMind Analytics — Backend

FastAPI application that runs the AI agent loop, serves the SSE chat endpoint, manages auth, and connects to both the analytics SQLite database and the live business PostgreSQL database.

---

## Structure

```
backend/
├── main.py                     # FastAPI app factory + lifespan
├── config.py                   # Pydantic Settings (reads from .env)
├── requirements.txt
│
├── api/
│   ├── deps.py                 # Shared FastAPI dependencies (lazy pool init)
│   └── routes/
│       ├── auth.py             # /api/auth/* — login, refresh, logout, change-password, me
│       ├── admin.py            # /api/admin/* — user CRUD + business config (superuser only)
│       ├── chat.py             # /api/chat/* — SSE streaming chat + confirm expensive queries
│       └── kpi.py              # /api/kpi/snapshot — live KPI panel data
│
├── agent/
│   ├── orchestrator.py         # AgentOrchestrator — tool-use loop, streams tokens via SSE
│   ├── prompt.py               # build_system_prompt(config) — assembled from business_config
│   └── schemas.py              # Pydantic models: ChatRequest, SSEEvent, ConfirmRequest
│
├── tools/
│   ├── base.py                 # BaseTool ABC
│   ├── registry.py             # ToolRegistry — dispatches Azure OpenAI tool calls
│   ├── schema_tool.py          # get_schema — queries information_schema
│   ├── query_tool.py           # execute_query — SELECT only, EXPLAIN gate, asyncio pause
│   ├── chart_tool.py           # generate_chart — Plotly figure JSON
│   └── kpi_tool.py             # get_kpi_snapshot — runs KPI SQL from business_config
│
├── db/
│   ├── analytics.py            # SQLAlchemy async engine + ORM models (SQLite via aiosqlite)
│   ├── business_db.py          # asyncpg pool — built from decrypted business_config.db_url
│   └── safety.py               # SQLSafetyValidator — sqlglot AST + keyword blocklist
│
├── services/
│   ├── auth_service.py         # bcrypt hashing, JWT creation/validation, FastAPI deps
│   ├── user_service.py         # User CRUD (create, deactivate, reset password)
│   ├── business_config_service.py  # Config CRUD, Fernet encrypt/decrypt for DB URL
│   └── conversation_service.py # Conversation + message persistence
│
└── scripts/
    ├── create_superuser.py     # Bootstrap the first superuser (run once)
    ├── create_user.py          # CLI fallback to add users without the UI
    └── seed_changepay_config.py # Seed full ChangePay domain config (reference impl)
```

---

## Running

```bash
source .venv/bin/activate
uvicorn main:app --port 8000 --reload
```

Health check: `curl http://localhost:8000/api/health`

## Tests

```bash
source .venv/bin/activate
pytest
```

Tests use **no external dependencies** — PostgreSQL is replaced by an in-memory
fake pool, the LLM by a fake provider (scripted responses), and the analytics
DB by in-memory SQLite. This is possible because every collaborator is injected:

- **LLM** — `AgentOrchestrator` depends on the `LLMProvider` protocol
  (`agent/llm/base.py`), not a vendor SDK. Tests pass a `FakeLLMProvider`.
- **DB pool** — tools receive the asyncpg pool via their constructor, so tests
  pass a `FakePool`. The orchestrator is wired via `AgentOrchestrator.build(config, llm, pool)`.

## Swapping the LLM provider

The LLM backend is a Strategy. To add Gemini (or any model):

1. Create `agent/llm/gemini_provider.py` implementing the `LLMProvider` protocol
   (`complete()` + `stream()`, returning the normalized `LLMResponse`/`ToolCall` types)
2. Add an `elif provider == "gemini"` branch in `agent/llm/factory.py`
3. Set `LLM_PROVIDER=gemini` in `.env`

No changes to the orchestrator, tools, or routes.

---

## Key Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/auth/login` | — | Returns access token + sets refresh cookie |
| `POST` | `/api/auth/refresh` | cookie | Rotates access token |
| `POST` | `/api/auth/logout` | — | Clears refresh cookie |
| `GET`  | `/api/auth/me` | Bearer | Current user profile |
| `POST` | `/api/auth/change-password` | Bearer | Change own password |
| `GET`  | `/api/kpi/snapshot` | Bearer | Live KPI panel data |
| `POST` | `/api/chat/` | Bearer | SSE streaming chat (text/event-stream) |
| `POST` | `/api/chat/confirm/{id}` | Bearer | Approve/deny an expensive query |
| `GET`  | `/api/chat/conversations` | Bearer | List user's conversations |
| `GET`  | `/api/admin/users` | Superuser | List all users |
| `POST` | `/api/admin/users` | Superuser | Create a user |
| `POST` | `/api/admin/users/{id}/deactivate` | Superuser | Deactivate a user |
| `POST` | `/api/admin/users/{id}/reset-password` | Superuser | Reset user password |
| `GET`  | `/api/admin/business-config` | Superuser | Get business config (DB URL masked) |
| `PUT`  | `/api/admin/business-config` | Superuser | Update business config |
| `POST` | `/api/admin/business-config/test-connection` | Superuser | Test DB URL before saving |

---

## SSE Event Types

The `/api/chat/` endpoint streams Server-Sent Events. Each event has `event:` and `data:` fields:

| Event | Data | When |
|-------|------|------|
| `conversation_id` | `{id}` | First event — conversation ID for this session |
| `text_delta` | `{delta}` | Each token of the LLM's text response |
| `chart` | `{plotly_json, title}` | When a chart is generated |
| `table` | `{columns, rows, total, source}` | When a query returns tabular data |
| `metrics` | `{items: [{label, value, icon}]}` | When KPI snapshot runs |
| `confirmation_required` | `{query_id, estimated_cost, warning}` | Expensive query — execution paused |
| `confirmation_cancelled` | `{query_id}` | Query timed out or cancelled |
| `done` | `{}` | Stream complete |
| `error` | `{message}` | On any failure |

---

## Security

- **Read-only DB access** — all queries validated by `SQLSafetyValidator` (sqlglot AST + keyword blocklist). Only `SELECT` statements pass.
- **Expensive query gate** — `EXPLAIN` runs before every query. If cost exceeds `explain_cost_threshold` (configurable per business), execution pauses and waits for user confirmation via `POST /api/chat/confirm/{query_id}`.
- **DB URL encrypted at rest** — stored using Fernet symmetric encryption. Key lives in `CONFIG_ENCRYPTION_KEY` env var, never in the database.
- **JWT auth** — 15-minute access tokens in memory, 7-day refresh tokens in httpOnly cookies.
- **Audit log** — every query executed is recorded in the `audit_log` table with user ID, question, SQL, row count, and duration.

---

## Adding a New Business

1. Deploy this backend with a fresh `.env` (new `CONFIG_ENCRYPTION_KEY` and `JWT_SECRET_KEY`)
2. Run `python scripts/create_superuser.py`
3. Log in and go to **Admin → Business Setup** in the UI
4. Enter the DB URL, domain context, KPI definitions, and starter questions
5. Click **Test Connection** then **Save**

No code changes required.
