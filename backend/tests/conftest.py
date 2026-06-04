"""
Shared test fixtures and fakes.

No external dependencies are touched: PostgreSQL is replaced by FakePool/FakeConn,
the LLM by FakeLLMProvider, and the analytics DB by an in-memory SQLite engine.
"""
import os

# Set required env vars BEFORE importing any app module that reads settings.
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://test.example.com/")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "test-key")
os.environ.setdefault("AZURE_OPENAI_DEPLOYMENT", "test-deployment")
os.environ.setdefault("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
os.environ.setdefault("ANALYTICS_DB_PATH", "/tmp/querymind_test_analytics.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret")
from cryptography.fernet import Fernet  # noqa: E402
os.environ.setdefault("CONFIG_ENCRYPTION_KEY", Fernet.generate_key().decode())

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession  # noqa: E402

from db.analytics import Base  # noqa: E402
from agent.llm.base import LLMResponse, ToolCall  # noqa: E402


# ── Fake PostgreSQL pool ──────────────────────────────────────────────────────

class FakeConn:
    """Stands in for an asyncpg connection."""

    def __init__(self, rows=None, fetchval_value=None, explain_cost=10.0, fetch_error=None):
        self._rows = rows if rows is not None else []
        self._fetchval_value = fetchval_value
        self._explain_cost = explain_cost
        self._fetch_error = fetch_error
        self.executed: list[str] = []

    async def fetch(self, query, *args):
        if query.strip().upper().startswith("EXPLAIN"):
            return [(f"Seq Scan on t  (cost=0.00..{self._explain_cost} rows=1 width=8)",)]
        if self._fetch_error:
            raise self._fetch_error
        return self._rows

    async def fetchval(self, query, *args):
        if isinstance(self._fetchval_value, Exception):
            raise self._fetchval_value
        return self._fetchval_value

    async def execute(self, query, *args):
        self.executed.append(query)


class FakePool:
    """Stands in for an asyncpg pool; .acquire() is an async context manager."""

    def __init__(self, conn: FakeConn):
        self._conn = conn

    def acquire(self):
        conn = self._conn

        class _Ctx:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *exc):
                return False

        return _Ctx()


# ── Fake LLM provider (Strategy) ──────────────────────────────────────────────

class FakeLLMProvider:
    """Returns scripted LLMResponses; streams a fixed final string."""

    def __init__(self, responses: list[LLMResponse], stream_text: str = "Done."):
        self._responses = list(responses)
        self._stream_text = stream_text
        self.complete_calls = 0
        self.seen_messages: list[list[dict]] = []

    async def complete(self, messages, tools) -> LLMResponse:
        self.seen_messages.append(list(messages))
        resp = self._responses[self.complete_calls]
        self.complete_calls += 1
        return resp

    async def stream(self, messages, tools):
        for token in self._stream_text.split(" "):
            yield token + " "


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def analytics_session() -> AsyncSession:
    """Fresh in-memory analytics DB per test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        yield session
    await engine.dispose()


@pytest.fixture
def fake_conn():
    return FakeConn()


@pytest.fixture
def fake_pool(fake_conn):
    return FakePool(fake_conn)


def tool_call(name: str, arguments: str = "{}", id: str = "call_1") -> ToolCall:
    return ToolCall(id=id, name=name, arguments=arguments)
