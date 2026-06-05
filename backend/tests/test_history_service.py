"""
Unit tests for history_service — RecentOnlyStrategy, SummarizedStrategy,
ContentExtractor implementations, and the factory.

All hermetic: in-memory SQLite via the analytics_session fixture, FakeLLMProvider
from conftest. No external services touched.
"""
import json
import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import select

from db.analytics import Conversation, Message
from services.history_service import (
    RecentOnlyStrategy,
    SummarizedStrategy,
    TextOnlyExtractor,
    RichContentExtractor,
    HistoryResult,
    get_history_strategy,
)
from agent.llm.base import LLMResponse
from tests.conftest import FakeLLMProvider


# ── Seed helper ───────────────────────────────────────────────────────────────

_BASE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)


async def _seed(session, msg_count: int, conv_id: str = "conv-1") -> str:
    """Create a conversation with `msg_count` alternating user/assistant messages.

    Each message gets an explicit, strictly-increasing created_at so ordering
    tests are deterministic even when all rows land in the same transaction.
    IDs are zero-padded to two digits so they sort lexicographically correctly
    up to 99 messages (sufficient for our tests).
    """
    conv = Conversation(id=conv_id, user_id=1, title="t")
    session.add(conv)
    await session.flush()
    for i in range(msg_count):
        role = "user" if i % 2 == 0 else "assistant"
        msg = Message(
            id=f"msg-{i:02d}",
            conversation_id=conv_id,
            role=role,
            content=json.dumps({"text": f"message {i}"}),
            created_at=_BASE_TIME + timedelta(seconds=i),
        )
        session.add(msg)
    await session.commit()
    return conv_id


# ── RecentOnlyStrategy ─────────────────────────────────────────────────────────

async def test_recent_only_returns_last_n(analytics_session):
    conv_id = await _seed(analytics_session, msg_count=25)
    result = await RecentOnlyStrategy().build(
        analytics_session, conv_id, max_turns=10, extractor=TextOnlyExtractor()
    )
    assert isinstance(result, HistoryResult)
    assert len(result.messages) == 10
    assert result.summary_used is False
    assert result.cache_breakpoint is None
    # Last message in the window should be message 24 (0-indexed)
    assert result.messages[-1]["content"] == "message 24"
    # First in window should be message 15
    assert result.messages[0]["content"] == "message 15"


async def test_recent_only_short_conversation_returns_all(analytics_session):
    """Fewer messages than max_turns — return all of them."""
    conv_id = await _seed(analytics_session, msg_count=5)
    result = await RecentOnlyStrategy().build(
        analytics_session, conv_id, max_turns=20, extractor=TextOnlyExtractor()
    )
    assert len(result.messages) == 5


async def test_recent_only_empty_conversation(analytics_session):
    conv = Conversation(id="empty-conv", user_id=1)
    analytics_session.add(conv)
    await analytics_session.commit()
    result = await RecentOnlyStrategy().build(
        analytics_session, "empty-conv", max_turns=10, extractor=TextOnlyExtractor()
    )
    assert result.messages == []
    assert result.summary_used is False


async def test_recent_only_message_order_is_chronological(analytics_session):
    """Messages must arrive oldest-first so the LLM reads them in order."""
    conv_id = await _seed(analytics_session, msg_count=15)
    result = await RecentOnlyStrategy().build(
        analytics_session, conv_id, max_turns=5, extractor=TextOnlyExtractor()
    )
    contents = [m["content"] for m in result.messages]
    # messages 10-14 in ascending order
    assert contents == ["message 10", "message 11", "message 12", "message 13", "message 14"]


# ── SummarizedStrategy ─────────────────────────────────────────────────────────

async def test_summarized_short_conversation_no_llm_call(analytics_session):
    """Short conversation (count ≤ max_turns): no summary, LLM must not be called."""
    conv_id = await _seed(analytics_session, msg_count=5)
    fake_llm = FakeLLMProvider([], stream_text="")
    result = await SummarizedStrategy().build(
        analytics_session, conv_id, max_turns=20,
        extractor=TextOnlyExtractor(), llm=fake_llm,
    )
    assert result.summary_used is False
    assert result.cache_breakpoint is None
    assert fake_llm.complete_calls == 0
    assert len(result.messages) == 5


async def test_summarized_long_conversation_generates_summary(analytics_session):
    """Long conversation: LLM called once, summary prepended with cache_breakpoint=1."""
    conv_id = await _seed(analytics_session, msg_count=25)
    fake_llm = FakeLLMProvider(
        [LLMResponse(finish_reason="stop", text="Earlier context: user asked about GMV.")],
    )
    result = await SummarizedStrategy().build(
        analytics_session, conv_id, max_turns=10,
        extractor=TextOnlyExtractor(), llm=fake_llm,
    )
    assert result.summary_used is True
    assert result.cache_breakpoint == 1
    assert fake_llm.complete_calls == 1

    # First message is the summary system message.
    assert result.messages[0]["role"] == "system"
    assert "Earlier context" in result.messages[0]["content"]

    # Remaining 10 messages are the live window.
    assert len(result.messages) == 11  # 1 summary + 10 window


async def test_summarized_summary_persisted_to_db(analytics_session):
    """Summary and checkpoint are written to the conversations table."""
    conv_id = await _seed(analytics_session, msg_count=25)
    fake_llm = FakeLLMProvider(
        [LLMResponse(finish_reason="stop", text="Summary text.")],
    )
    await SummarizedStrategy().build(
        analytics_session, conv_id, max_turns=10,
        extractor=TextOnlyExtractor(), llm=fake_llm,
    )

    conv = (await analytics_session.execute(
        select(Conversation).where(Conversation.id == conv_id)
    )).scalar_one()
    assert conv.summary == "Summary text."
    # Checkpoint should be msg-14 (last of the 15 pre-window messages, 0-indexed)
    assert conv.summary_checkpoint == "msg-14"  # f"msg-{14:02d}" == "msg-14"


async def test_summarized_caches_summary_no_second_llm_call(analytics_session):
    """Second build on the same conversation reuses the stored summary."""
    conv_id = await _seed(analytics_session, msg_count=25)

    # First call — generates summary.
    fake_llm = FakeLLMProvider(
        [LLMResponse(finish_reason="stop", text="Cached summary.")],
    )
    await SummarizedStrategy().build(
        analytics_session, conv_id, max_turns=10,
        extractor=TextOnlyExtractor(), llm=fake_llm,
    )
    assert fake_llm.complete_calls == 1

    # Second call — same window, summary checkpoint matches → no LLM call.
    fake_llm2 = FakeLLMProvider([], stream_text="")
    result2 = await SummarizedStrategy().build(
        analytics_session, conv_id, max_turns=10,
        extractor=TextOnlyExtractor(), llm=fake_llm2,
    )
    assert fake_llm2.complete_calls == 0
    assert result2.summary_used is True
    assert "Cached summary." in result2.messages[0]["content"]


async def test_summarized_stale_summary_regenerated(analytics_session):
    """When the window shrinks (more messages added), summary is regenerated."""
    conv_id = await _seed(analytics_session, msg_count=25)
    fake_llm = FakeLLMProvider(
        [LLMResponse(finish_reason="stop", text="Old summary.")],
    )
    # First build: 25 messages, window=10, pre-window=15, checkpoint=msg-14
    await SummarizedStrategy().build(
        analytics_session, conv_id, max_turns=10,
        extractor=TextOnlyExtractor(), llm=fake_llm,
    )

    # Add 5 more messages — now 30 total, pre-window=20, checkpoint should be msg-19.
    for i in range(25, 30):
        role = "user" if i % 2 == 0 else "assistant"
        analytics_session.add(Message(
            id=f"msg-{i:02d}",
            conversation_id=conv_id,
            role=role,
            content=json.dumps({"text": f"message {i}"}),
            created_at=_BASE_TIME + timedelta(seconds=i),
        ))
    await analytics_session.commit()

    fake_llm2 = FakeLLMProvider(
        [LLMResponse(finish_reason="stop", text="Fresh summary.")],
    )
    result = await SummarizedStrategy().build(
        analytics_session, conv_id, max_turns=10,
        extractor=TextOnlyExtractor(), llm=fake_llm2,
    )
    assert fake_llm2.complete_calls == 1  # regenerated
    assert "Fresh summary." in result.messages[0]["content"]


async def test_summarized_fallback_when_no_llm(analytics_session):
    """If LLM is None and summarisation is needed, falls back to recent-only silently."""
    conv_id = await _seed(analytics_session, msg_count=25)
    result = await SummarizedStrategy().build(
        analytics_session, conv_id, max_turns=10,
        extractor=TextOnlyExtractor(), llm=None,
    )
    assert result.summary_used is False
    assert len(result.messages) == 10  # recent-only fallback, no crash


# ── ContentExtractor ───────────────────────────────────────────────────────────

def test_text_only_extractor_ignores_table_and_chart():
    ext = TextOnlyExtractor()
    content = {"text": "hello", "table": {"total": 5, "columns": ["a"]}, "chart": {"title": "x"}}
    assert ext.extract("user", content) == "hello"


def test_text_only_extractor_empty_content():
    assert TextOnlyExtractor().extract("user", {}) == ""


def test_rich_extractor_text_only():
    ext = RichContentExtractor()
    assert ext.extract("user", {"text": "hi"}) == "hi"


def test_rich_extractor_includes_table_metadata():
    ext = RichContentExtractor()
    result = ext.extract("assistant", {
        "text": "Here are the results",
        "table": {"total": 42, "columns": ["campus", "orders"]},
    })
    assert "Here are the results" in result
    assert "42 rows" in result
    assert "campus" in result
    assert "orders" in result


def test_rich_extractor_includes_chart_title():
    ext = RichContentExtractor()
    result = ext.extract("assistant", {
        "text": "Here is a chart",
        "chart": {"title": "Orders by Campus"},
    })
    assert "Here is a chart" in result
    assert "Orders by Campus" in result


def test_rich_extractor_no_text_field():
    ext = RichContentExtractor()
    result = ext.extract("assistant", {"chart": {"title": "My Chart"}})
    assert "My Chart" in result


# ── Factory ────────────────────────────────────────────────────────────────────

def test_factory_returns_recent_only():
    assert isinstance(get_history_strategy(summarize=False), RecentOnlyStrategy)


def test_factory_returns_summarized():
    assert isinstance(get_history_strategy(summarize=True), SummarizedStrategy)
