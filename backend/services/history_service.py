"""
Conversation history building for the LLM context window.

## Extensibility hooks

ContentExtractor — controls what is pulled from each stored message.
  TextOnlyExtractor (default): text field only.
  RichContentExtractor (Phase 2): also includes table row-counts and chart
    titles, letting the LLM reference prior visualisations in follow-up turns.

HistoryStrategy — controls how the window is assembled.
  RecentOnlyStrategy: last N messages, no summarisation. Zero overhead.
  SummarizedStrategy: LLM-generated summary of older messages prepended
    to the last N turns. Summary is cached on the Conversation row and
    reused until new messages fall outside the window.

HistoryResult.cache_breakpoint — index before which prompt caching can be
  applied. SummarizedStrategy sets this to 1 (the stable summary system
  message), enabling future Claude / Azure prompt caching with no code
  changes to the strategies themselves — run_turn just reads the field.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from agent.llm.base import LLMProvider
from services.conversation_service import (
    get_message_count,
    get_recent_messages,
    get_older_messages,
    get_conversation_internal,
    update_conversation_summary,
)

log = logging.getLogger(__name__)


# ── Content extraction ────────────────────────────────────────────────────────

class ContentExtractor(Protocol):
    """Controls what text is extracted from a stored message content dict.

    Swap implementations without touching any strategy code:
      TextOnlyExtractor   — Phase 1 default, text only.
      RichContentExtractor — Phase 2, adds table/chart metadata.
    """

    def extract(self, role: str, content: dict) -> str: ...


class TextOnlyExtractor:
    """Extracts only the text field. Current default."""

    def extract(self, role: str, content: dict) -> str:
        return content.get("text", "")


class RichContentExtractor:
    """Phase 2: also includes table row-counts and chart titles so the LLM
    can refer back to earlier visualisations in follow-up questions."""

    def extract(self, role: str, content: dict) -> str:
        parts = [content.get("text", "")]
        if "table" in content:
            t = content["table"]
            cols = ", ".join(t.get("columns", []))
            parts.append(f"[Table: {t.get('total', '?')} rows, columns: {cols}]")
        if "chart" in content:
            c = content["chart"]
            parts.append(f"[Chart: {c.get('title', 'untitled')}]")
        return "\n".join(filter(None, parts))


# ── Result type ───────────────────────────────────────────────────────────────

@dataclass
class HistoryResult:
    """Assembled message list plus metadata for the caller."""

    messages: list[dict]
    """LLM-ready message dicts, ready to pass to orchestrator.run()."""

    summary_used: bool
    """Whether a summary system message was prepended."""

    cache_breakpoint: int | None
    """Index before which prompt caching applies (None = not applicable).

    When SummarizedStrategy prepends a summary, cache_breakpoint=1 so
    run_turn can mark messages[:1] as a stable cached prefix once Claude
    or Azure prompt caching is wired up — no strategy changes needed.
    """


# ── Strategies ────────────────────────────────────────────────────────────────

class HistoryStrategy(Protocol):
    async def build(
        self,
        session: AsyncSession,
        conv_id: str,
        max_turns: int,
        extractor: ContentExtractor,
        llm: LLMProvider | None = None,
    ) -> HistoryResult: ...


class RecentOnlyStrategy:
    """Last N messages only — no summarisation, no LLM overhead.

    Default when ``history_summarize=False`` (the safe default). Switch to
    SummarizedStrategy when you want to preserve context past the window.
    """

    async def build(
        self,
        session: AsyncSession,
        conv_id: str,
        max_turns: int,
        extractor: ContentExtractor,
        llm: LLMProvider | None = None,
    ) -> HistoryResult:
        messages = await get_recent_messages(session, conv_id, max_turns)
        return HistoryResult(
            messages=_to_llm_messages(messages, extractor),
            summary_used=False,
            cache_breakpoint=None,
        )


class SummarizedStrategy:
    """Summary of pre-window messages + last N turns.

    Flow per turn:
      1. Count total messages. If ≤ max_turns → behave like RecentOnlyStrategy.
      2. Load the window (last N) and the pre-window set (everything before).
      3. Compare the conversation's stored ``summary_checkpoint`` against the
         id of the last pre-window message.
         - Match  → cached summary is fresh, reuse it (zero LLM calls).
         - Stale/missing → call the LLM to (re)summarise, persist to the
           Conversation row for future turns.
      4. Prepend ``{role: system, content: "Conversation summary: ..."}``
         before the window messages. cache_breakpoint=1 marks the summary
         as the stable cacheable prefix.

    Fallback: if the conversation needs summarisation but no LLM is provided,
    falls back to recent-only with a warning log — never raises.
    """

    _SUMMARIZE_PROMPT = (
        "Summarise the following conversation between a user and an AI analytics assistant. "
        "Focus on: what data was explored, key findings, and any important context or "
        "constraints the user established. Be concise but preserve all analytical context "
        "needed to understand follow-up questions. Respond with the summary only.\n\n"
        "{history}"
    )

    async def build(
        self,
        session: AsyncSession,
        conv_id: str,
        max_turns: int,
        extractor: ContentExtractor,
        llm: LLMProvider | None = None,
    ) -> HistoryResult:
        total = await get_message_count(session, conv_id)

        if total <= max_turns:
            # Short conversation — no summary needed yet.
            messages = await get_recent_messages(session, conv_id, max_turns)
            return HistoryResult(
                messages=_to_llm_messages(messages, extractor),
                summary_used=False,
                cache_breakpoint=None,
            )

        # Load the live window and the pre-window set.
        window = await get_recent_messages(session, conv_id, max_turns)
        pre_window_count = total - max_turns
        pre_window = await get_older_messages(session, conv_id, pre_window_count)

        # The summary must cover up to (and including) the last pre-window message.
        expected_checkpoint = pre_window[-1].id if pre_window else None

        conv = await get_conversation_internal(session, conv_id)
        summary_text = conv.summary if conv else None
        checkpoint_matches = (
            conv is not None
            and conv.summary_checkpoint == expected_checkpoint
            and summary_text
        )

        if not checkpoint_matches:
            if llm is None:
                # Safe degradation: return recent window without summary.
                log.warning(
                    "history_service: conv %s needs summarisation but no LLM provided "
                    "— falling back to recent-only (%d of %d messages)",
                    conv_id, max_turns, total,
                )
                return HistoryResult(
                    messages=_to_llm_messages(window, extractor),
                    summary_used=False,
                    cache_breakpoint=None,
                )

            log.info(
                "history_service: generating summary for conv %s "
                "(%d pre-window messages)", conv_id, len(pre_window),
            )
            summary_text = await _summarize(pre_window, extractor, llm)
            if expected_checkpoint:
                await update_conversation_summary(
                    session, conv_id, summary_text, expected_checkpoint
                )

        llm_messages = [
            {
                "role": "system",
                "content": f"Conversation summary (earlier context):\n{summary_text}",
            }
        ] + _to_llm_messages(window, extractor)

        return HistoryResult(
            messages=llm_messages,
            summary_used=True,
            cache_breakpoint=1,  # summary message is the stable cacheable prefix
        )


# ── Internal helpers ──────────────────────────────────────────────────────────

def _to_llm_messages(messages, extractor: ContentExtractor) -> list[dict]:
    """Convert ORM Message rows to the {role, content} dicts the LLM expects."""
    result = []
    for m in messages:
        try:
            content = json.loads(m.content)
        except (json.JSONDecodeError, TypeError):
            content = {"text": str(m.content)}
        text = extractor.extract(m.role, content)
        if text:
            result.append({"role": m.role, "content": text})
    return result


async def _summarize(messages, extractor: ContentExtractor, llm: LLMProvider) -> str:
    """Call the LLM to summarise a list of pre-window messages."""
    history_text = "\n".join(
        f"{m.role.upper()}: {extractor.extract(m.role, _parse_content(m.content))}"
        for m in messages
    )
    prompt = SummarizedStrategy._SUMMARIZE_PROMPT.format(history=history_text)
    response = await llm.complete(
        messages=[{"role": "user", "content": prompt}],
        tools=[],
    )
    return response.text or ""


def _parse_content(raw: str) -> dict:
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {"text": str(raw)}


# ── Factory ───────────────────────────────────────────────────────────────────

def get_history_strategy(summarize: bool) -> HistoryStrategy:
    """Select the history strategy from config. Called once per turn in run_turn."""
    return SummarizedStrategy() if summarize else RecentOnlyStrategy()
