import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.channel_manager import channel_manager
from app.config import get_settings
from app.db.base import SessionLocal
from app.retention import run_retention_loop
from app.routers import (
    admin_channels,
    admin_docs,
    admin_llm_settings,
    admin_logs,
    admin_soul,
    admin_usage,
    admin_users,
    health,
    metrics,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _warn_on_unsafe_defaults()
    db = SessionLocal()
    try:
        await channel_manager.sync(db)
    finally:
        db.close()
    retention_task = asyncio.create_task(run_retention_loop())
    try:
        yield
    finally:
        retention_task.cancel()
        try:
            await retention_task
        except asyncio.CancelledError:
            pass
        await channel_manager.stop_all()


def _warn_on_unsafe_defaults() -> None:
    settings = get_settings()
    if settings.admin_password == "admin" or settings.openai_api_key == "":
        logger.warning("Using default/empty admin or API credentials — do not deploy like this")


app = FastAPI(title="Matcha Bot Backend", lifespan=lifespan)

app.include_router(health.router)
app.include_router(admin_channels.router)
app.include_router(admin_docs.router)
app.include_router(admin_users.router)
app.include_router(admin_users.login_router)
app.include_router(admin_logs.router)
app.include_router(admin_llm_settings.router)
app.include_router(admin_soul.router)
app.include_router(admin_usage.router)
app.include_router(metrics.router)

# HTTP-level latency/status metrics. `expose()` is not called — the /metrics
# route above already renders the default registry, which this writes into.
Instrumentator().instrument(app)
