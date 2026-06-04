"""
Audit logging for the SQL the agent runs against the business database.

Best-effort: a failure to write the audit log must never break the user's chat,
so callers wrap this and swallow errors. Each entry records who ran what, the
generated SQL, the outcome (executed/blocked/cancelled/failed), row count and
duration.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from db.analytics import AuditLog

logger = logging.getLogger(__name__)


async def record_queries(
    session: AsyncSession,
    user_id: int,
    conversation_id: str,
    question: str,
    entries: list,  # list[AuditEntry]
) -> None:
    """Persist one audit row per executed/attempted query. Never raises."""
    if not entries:
        return
    try:
        for e in entries:
            session.add(AuditLog(
                user_id=user_id,
                conversation_id=conversation_id,
                question=question,
                sql_executed=e.sql,
                outcome=e.outcome,
                rows_returned=e.rows_returned,
                duration_ms=e.duration_ms,
            ))
        await session.commit()
    except Exception as exc:  # audit must not break the request
        logger.warning("Failed to write audit log: %s", exc)
        await session.rollback()
