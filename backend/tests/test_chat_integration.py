"""
Integration tests for the chat route — the wiring between HTTP layer, orchestrator,
persistence, and audit. Hermetic: fake LLM, fake pool, in-memory analytics DB.
"""
import json
from fastapi.testclient import TestClient
from sqlalchemy import select, func

from main import app
from db.analytics import User, Message, AuditLog, get_session
from api.deps import get_current_user, get_business_pool
from services.chat_service import run_turn
from agent.llm.base import LLMResponse, ToolCall
from services import business_config_service as bcs
from services import llm_config_service as lcs
from tests.conftest import FakeConn, FakePool, FakeLLMProvider


async def _seed_config(session):
    await bcs.update_config(
        session,
        data={
            "business_name": "Test Co", "business_description": "d", "domain_context": "c",
            "business_rules": [{"rule": "r"}], "table_descriptions": {"order_order": "orders"},
            "kpi_definitions": [{"name": "GMV", "sql": "SELECT 1", "format": "number", "icon": "x"}],
            "starter_questions": ["q"], "explain_cost_threshold": 50000,
        },
        new_db_url="postgres://u:p@host:5432/db",
    )
    await lcs.update_llm_config(session, provider="azure", model="gpt-4o-mini",
                               api_key="k", endpoint="https://x/", api_version="v")


# ── full happy path through chat_service.run_turn ─────────────────────────────

async def test_run_turn_streams_persists_and_audits(analytics_session, monkeypatch):
    await _seed_config(analytics_session)
    user = User(email="e@x.com", name="E", password_hash="x",
                is_active=True, is_superuser=False, force_password_change=False)
    analytics_session.add(user)
    await analytics_session.commit()
    await analytics_session.refresh(user)

    # Fake LLM: round 1 runs execute_query, round 2 answers.
    fake_llm = FakeLLMProvider(
        [
            LLMResponse(finish_reason="tool_calls", tool_calls=[
                ToolCall(id="t1", name="execute_query",
                         arguments=json.dumps({"sql": "SELECT campus FROM order_order", "description": "campuses"})),
            ]),
            LLMResponse(finish_reason="stop"),
        ],
        stream_text="Here are the campuses",
    )
    monkeypatch.setattr("services.chat_service.create_llm_provider", lambda cfg: fake_llm)

    # Health check hits the module-level pool (None in tests) — stub it out.
    async def _healthy(): return True
    monkeypatch.setattr("services.chat_service.check_pool_health", _healthy)

    pool = FakePool(FakeConn(rows=[{"campus": "IIT"}], explain_cost=10.0))
    gen = await run_turn(analytics_session, pool, user_id=user.id,
                         message="which campuses?", conversation_id=None)
    events = [e async for e in gen]

    kinds = [e["event"] for e in events]
    assert kinds[0] == "conversation_id"
    assert "table" in kinds            # execute_query produced a table
    assert "text_delta" in kinds       # final answer streamed
    assert kinds[-1] == "done"

    # user + assistant messages persisted
    msg_count = (await analytics_session.execute(select(func.count()).select_from(Message))).scalar()
    assert msg_count >= 2

    # audit row recorded for the executed query
    audits = (await analytics_session.execute(select(AuditLog))).scalars().all()
    assert any(a.outcome == "executed" and a.sql_executed == "SELECT campus FROM order_order" for a in audits)


# ── HTTP guard paths via TestClient ───────────────────────────────────────────

def _override_user(force_password_change: bool) -> User:
    user = User(id=1, email="e@x.com", name="E", password_hash="x",
                is_active=True, is_superuser=False, force_password_change=force_password_change)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_business_pool] = lambda: object()
    app.dependency_overrides[get_session] = lambda: None
    return user


def test_chat_403_when_password_change_required():
    _override_user(force_password_change=True)
    try:
        r = TestClient(app).post("/api/chat/", json={"message": "hi"})
        assert r.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_chat_429_when_at_capacity(monkeypatch):
    _override_user(force_password_change=False)

    async def _no_slot():
        return False
    monkeypatch.setattr("api.routes.chat._acquire_chat_slot", _no_slot)
    try:
        r = TestClient(app).post("/api/chat/", json={"message": "hi"})
        assert r.status_code == 429
    finally:
        app.dependency_overrides.clear()
