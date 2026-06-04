# QueryMind Analytics — Backend

FastAPI application that runs the AI agent loop, serves the SSE chat endpoint, manages auth, and connects to both the analytics SQLite database and the live business PostgreSQL database.

---

## Structure

```
backend/
├── main.py                     # FastAPI app factory, lifespan, central exception handler
├── config.py                   # Pydantic Settings (reads from .env) incl. LLM_PROVIDER
├── exceptions.py               # Domain error hierarchy (AppError + subclasses)
├── requirements.txt
├── pytest.ini
│
├── api/                        # HTTP transport layer
│   ├── deps.py                 # FastAPI dependencies: get_current_user, require_superuser,
│   │                           #   get_business_pool (lazy init), get_session — one import surface
│   ├── routes/
│   │   ├── auth.py             # /api/auth/* — login, refresh, logout, change-password, me
│   │   ├── admin.py            # /api/admin/* — user CRUD + business config (superuser only)
│   │   ├── chat.py             # /api/chat/* — SSE streaming chat + confirm expensive queries
│   │   └── kpi.py              # /api/kpi/snapshot — live KPI panel data
│   └── schemas/                # Request/response DTOs (Pydantic), per route group
│       ├── common.py           # DetailResponse
│       ├── auth.py             # LoginRequest, UserOut, LoginResponse, TokenResponse, ...
│       ├── admin.py            # CreateUserRequest, BusinessConfigRequest/Out, AdminUserOut, ...
│       ├── chat.py             # ChatRequest, ConfirmRequest, SSEEvent, Conversation*/MessageOut
│       └── kpi.py              # KPIItem, KPISnapshotOut
│
├── agent/
│   ├── orchestrator.py         # AgentOrchestrator — tool-use loop, provider+tools injected
│   ├── prompt.py               # build_system_prompt(config) — assembled from business_config
│   └── llm/                    # LLM Strategy — provider-agnostic
│       ├── base.py             # LLMProvider protocol + normalized LLMResponse/ToolCall types
│       ├── azure_provider.py   # Azure OpenAI implementation
│       ├── claude_provider.py  # Anthropic Claude impl (OpenAI↔Anthropic translation)
│       └── factory.py          # create_llm_provider(llm_config) — selects by config.provider
│
├── tools/
│   ├── base.py                 # BaseTool ABC + ToolResult
│   ├── registry.py             # ToolRegistry — dispatches normalized ToolCalls
│   ├── schema_tool.py          # get_schema — queries information_schema (pool injected)
│   ├── query_tool.py           # execute_query — SELECT only, EXPLAIN gate, connection-safe wait
│   ├── chart_tool.py           # generate_chart — Plotly figure JSON
│   └── kpi_tool.py             # get_kpi_snapshot — runs KPI SQL from business_config
│
├── db/
│   ├── analytics.py            # SQLAlchemy async engine + ORM models (SQLite via aiosqlite)
│   ├── business_db.py          # asyncpg pool — built from decrypted business_config.db_url
│   └── safety.py               # SQLSafetyValidator — sqlglot AST + keyword blocklist
│
├── services/                   # Pure business logic — ZERO FastAPI imports
│   ├── auth_service.py         # bcrypt hashing + JWT create/decode (raises InvalidTokenError)
│   ├── user_service.py         # User CRUD — raises domain exceptions
│   ├── crypto.py               # Fernet encrypt/decrypt/mask for secrets at rest
│   ├── business_config_service.py  # Business/domain config CRUD (DB URL encrypted)
│   ├── llm_config_service.py   # LLM provider + credentials CRUD (API key encrypted)
│   └── conversation_service.py # Conversation + message persistence
│
├── scripts/
│   ├── create_superuser.py     # Bootstrap the first superuser (run once)
│   ├── create_user.py          # CLI fallback to add users without the UI
│   ├── seed_example.py         # Template seed for a new business (safe to commit)
│   └── seed_changepay_config.py # ChangePay domain config (gitignored — has live DB URL)
│
└── tests/                      # pytest — no external deps (fakes for LLM + Postgres)
    ├── conftest.py             # FakePool, FakeConn, FakeLLMProvider, in-memory SQLite fixture
    ├── test_safety.py          ├── test_auth_service.py    ├── test_user_service.py
    ├── test_business_config_service.py   ├── test_tools.py  ├── test_orchestrator.py
    ├── test_llm_factory.py     ├── test_kpi_format.py      └── test_exceptions.py
```

### Layering

```
api/ (routes, schemas, deps)   ← HTTP transport. Only this layer knows FastAPI.
   │
   ├── agent/ (orchestrator, llm/)   ← reasoning loop, provider-agnostic
   ├── tools/                        ← agent capabilities (DB pool injected)
   ├── services/                     ← pure business logic, raises domain exceptions
   └── db/                           ← persistence + SQL safety
```

Domain errors raised by `services/` flow up to the single `@app.exception_handler(AppError)`
in `main.py`, which maps them to HTTP responses — so the service layer never imports FastAPI.

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

## Choosing / swapping the LLM provider

The provider and its credentials are **stored in the DB** (`llm_config` table,
API key Fernet-encrypted) and configured by a superuser at **Admin → AI Model**.
Two providers ship today: **Azure OpenAI** and **Claude (Anthropic)**.

On first startup, if `llm_config` is empty, it is seeded from the Azure env vars
(`ensure_llm_config_from_env`) so existing deployments keep working; after that
the DB is the source of truth.

The backend is a Strategy. To add another model (e.g. Gemini):

1. Create `agent/llm/gemini_provider.py` implementing the `LLMProvider` protocol
   (`complete()` + `stream()`, returning the normalized `LLMResponse`/`ToolCall`
   types — translate the vendor's message/tool format here, as `claude_provider.py` does)
2. Add a branch in `agent/llm/factory.py` keyed on `config.provider`
3. Add it to `SUPPORTED_PROVIDERS` in `services/llm_config_service.py` and to the
   provider dropdown in `components/admin/LLMSettings.tsx`

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
| `GET`  | `/api/admin/llm-config` | Superuser | Get LLM provider config (API key masked) |
| `PUT`  | `/api/admin/llm-config` | Superuser | Set provider (azure/claude), model, credentials |

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

- **Read-only DB access** — all queries validated by `SQLSafetyValidator` (sqlglot AST + keyword blocklist). Only `SELECT` statements pass; `_event` audit tables are blocked.
- **Expensive query gate** — `EXPLAIN` runs before every query. If cost exceeds `explain_cost_threshold` (configurable per business), execution pauses and waits for user confirmation via `POST /api/chat/confirm/{query_id}`. No DB connection is held during the wait (see `query_tool._await_confirmation`).
- **Statement timeout** — every query runs with a 10s server-side `statement_timeout`.
- **DB URL encrypted at rest** — Fernet symmetric encryption. Key lives in `CONFIG_ENCRYPTION_KEY` env var, never in the database. Masked (last 10 chars) whenever returned to the UI.
- **JWT auth** — 15-minute access tokens in memory, 7-day refresh tokens in httpOnly cookies.

> **Not yet wired:** the `audit_log` table exists in the schema but query logging
> to it is not implemented yet — a planned enhancement.

---

## Known limitations (for scale)

Fine for the current single-instance, few-executives deployment; address before scaling:

- **In-memory confirmation state** — the pending-confirmation registry (`tools/query_tool._pending`) lives in process memory, so `POST /api/chat/confirm/{id}` must hit the same worker that paused the query. Running multiple workers/instances needs shared state (e.g. Redis). Likewise SSE streams are pinned to one worker.
- **SQLite analytics DB** — single-writer; serializes conversation/message writes. Move to PostgreSQL for higher write concurrency.
- **One pool per worker** — total Postgres connections = `workers × pool max_size`; tune against the server's `max_connections`.

---

## Adding a New Business

Either configure via the UI:

1. Deploy with a fresh `.env` (new `CONFIG_ENCRYPTION_KEY` and `JWT_SECRET_KEY`)
2. `python scripts/create_superuser.py`
3. Log in → **Admin → Business Setup** → enter DB URL, domain context, KPIs, starter questions → **Test Connection** → **Save**

…or script it: copy `scripts/seed_example.py`, fill in your values, and run it. (The renamed copy is gitignored since it holds a real DB URL.)

No code changes required either way.
