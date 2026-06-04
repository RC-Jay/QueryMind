from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from db.analytics import get_session
from services.business_config_service import get_config_or_raise
from services.kpi_service import compute_kpis
from api.deps import get_current_user, get_business_pool
from api.schemas.kpi import KPIItem, KPISnapshotOut

router = APIRouter(prefix="/api/kpi", tags=["kpi"])


@router.get("/snapshot", response_model=KPISnapshotOut)
async def kpi_snapshot(
    _=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    pool=Depends(get_business_pool),
):
    config = await get_config_or_raise(session)
    items = await compute_kpis(pool, config.kpi_definitions)
    return KPISnapshotOut(kpis=[KPIItem(**item) for item in items])
