from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from db.analytics import init_db, AsyncSessionLocal
from db.business_db import close_pool
from services.business_config_service import ensure_pool_from_config
from services.llm_config_service import ensure_llm_config_from_env
from api.routes import auth, admin, chat, kpi
from config import get_settings
from exceptions import AppError


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    async with AsyncSessionLocal() as session:
        await ensure_llm_config_from_env(session)  # bootstrap LLM config from env if unset
        await ensure_pool_from_config(session)
    yield
    # Shutdown
    await close_pool()


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
        return {"status": "ok", "service": "QueryMind Analytics"}

    return app


app = create_app()
