import json
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from db.analytics import get_session
from services.business_config_service import get_config_or_raise
from api.deps import get_current_user, get_business_pool
from tools.kpi_tool import _format_value
from api.schemas.kpi import KPIItem, KPISnapshotOut

router = APIRouter(prefix="/api/kpi", tags=["kpi"])


@router.get("/snapshot", response_model=KPISnapshotOut)
async def kpi_snapshot(
    _=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    pool=Depends(get_business_pool),
):
    config = await get_config_or_raise(session)
    kpi_defs = json.loads(config.kpi_definitions) if isinstance(config.kpi_definitions, str) else config.kpi_definitions
    results = []
    async with pool.acquire() as conn:
        for kpi in kpi_defs:
            try:
                value = await conn.fetchval(kpi["sql"])
                formatted = _format_value(value, kpi.get("format", "number"))
            except Exception:
                formatted = "N/A"
            results.append(KPIItem(
                label=kpi["name"],
                value=formatted,
                icon=kpi.get("icon", ""),
            ))
    return KPISnapshotOut(kpis=results)
