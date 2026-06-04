"""
Shared KPI computation: run each KPI's SQL against the business DB and format
the result. Used by both the /api/kpi/snapshot route and GetKPISnapshotTool.

Queries run in parallel — each on its own pooled connection — so the snapshot's
latency is the slowest single query, not the sum. (A DB connection is a serial
channel, so concurrency requires one connection per query; the pool's max_size
bounds how many run at once.)
"""
import asyncio


def _format_value(value, fmt: str) -> str:
    if value is None:
        return "N/A"
    try:
        num = float(value)
    except (TypeError, ValueError):
        return str(value)

    if fmt == "currency":
        return f"₹{num:,.0f}" if num >= 1 else f"₹{num:.2f}"
    elif fmt == "percent":
        return f"{num:.1f}%"
    elif fmt == "number":
        return f"{int(num):,}"
    elif fmt == "decimal":
        return f"{num:.2f}"
    return str(value)


async def compute_kpis(pool, kpi_definitions: list[dict]) -> list[dict]:
    """Return [{label, value, icon}] for each KPI, computed concurrently.
    A failing KPI yields 'N/A' rather than failing the whole snapshot."""

    async def _one(kpi: dict) -> dict:
        try:
            async with pool.acquire() as conn:
                value = await conn.fetchval(kpi["sql"])
            formatted = _format_value(value, kpi.get("format", "number"))
        except Exception:
            formatted = "N/A"
        return {"label": kpi["name"], "value": formatted, "icon": kpi.get("icon", "")}

    # gather preserves input order, so KPI ordering is stable.
    return list(await asyncio.gather(*(_one(k) for k in kpi_definitions)))
