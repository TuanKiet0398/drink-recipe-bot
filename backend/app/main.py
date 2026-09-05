import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.channel_manager import channel_manager
from app.config import get_settings
from app.db.base import SessionLocal
from app.routers import admin_docs, admin_logs, admin_usage, admin_users, health

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _warn_on_unsafe_defaults()
    db = SessionLocal()
    try:
        await channel_manager.sync(db)
    finally:
        db.close()
    try:
        yield
    finally:
        await channel_manager.stop_all()


def _warn_on_unsafe_defaults() -> None:
    settings = get_settings()
    if settings.admin_password == "admin" or settings.openai_api_key == "":
        logger.warning("Using default/empty admin or API credentials — do not deploy like this")


app = FastAPI(title="Matcha Bot Backend", lifespan=lifespan)

app.include_router(health.router)
app.include_router(admin_docs.router)
app.include_router(admin_users.router)
app.include_router(admin_users.login_router)
app.include_router(admin_logs.router)
app.include_router(admin_usage.router)
