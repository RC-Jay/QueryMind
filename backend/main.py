from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text
from db.analytics import init_db, AsyncSessionLocal
import db.business_db as business_db
from db.business_db import close_pool
from db.redis_client import close_redis
from services.business_config_service import ensure_pool_from_config
from services.llm_config_service import ensure_llm_config_from_env
from api.routes import auth, admin, chat, kpi
from config import get_settings
from exceptions import AppError
from observability import configure_logging, request_logging_middleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    configure_logging()
    await init_db()
    async with AsyncSessionLocal() as session:
        await ensure_llm_config_from_env(session)  # bootstrap LLM config from env if unset
        await ensure_pool_from_config(session)
    yield
    # Shutdown
    await close_pool()
    await close_redis()


async def _readiness_checks() -> tuple[bool, dict]:
    """Probe dependencies. Analytics DB is required; others are reported but
    don't pull the instance out of rotation (per-request errors handle them)."""
    checks: dict[str, str] = {}
    ready = True

    # Analytics DB — hard requirement
    try:
        async with AsyncSessionLocal() as s:
            await s.execute(text("SELECT 1"))
        checks["analytics_db"] = "ok"
    except Exception as exc:
        checks["analytics_db"] = f"error: {exc}"
        ready = False

    # Business DB — informational (may be intentionally unconfigured)
    if business_db._pool is not None:
        try:
            async with business_db._pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            checks["business_db"] = "ok"
        except Exception as exc:
            checks["business_db"] = f"error: {exc}"
    else:
        checks["business_db"] = "not_configured"

    # Redis — required only when configured
    settings = get_settings()
    if settings.redis_url:
        try:
            from db.redis_client import get_redis
            await get_redis().ping()
            checks["redis"] = "ok"
        except Exception as exc:
            checks["redis"] = f"error: {exc}"
            ready = False
    else:
        checks["redis"] = "in_process_fallback"

    return ready, checks


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="QueryMind Analytics API",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Structured access logging + request-id correlation.
    app.middleware("http")(request_logging_middleware)

    # Central translation of domain errors → HTTP responses.
    # Lets the service layer stay free of any FastAPI/HTTP knowledge.
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(chat.router)
    app.include_router(kpi.router)

    @app.get("/api/health")
    async def health():
        """Liveness — the process is up."""
        return {"status": "ok", "service": "QueryMind Analytics"}

    @app.get("/api/readyz")
    async def readyz():
        """Readiness — dependencies are reachable. 503 if a required one is down."""
        ready, checks = await _readiness_checks()
        return JSONResponse(
            status_code=200 if ready else 503,
            content={"ready": ready, "checks": checks},
        )

    return app


app = create_app()
