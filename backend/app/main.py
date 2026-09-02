import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.routers import admin_docs, admin_logs, admin_users, health, webhook

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _warn_on_unsafe_defaults()
    yield


def _warn_on_unsafe_defaults() -> None:
    settings = get_settings()
    if settings.admin_password == "admin" or settings.openai_api_key == "" or settings.qdrant_url == "":
        logger.warning("Using default/empty admin or API credentials — do not deploy like this")


app = FastAPI(title="Matcha Bot Backend", lifespan=lifespan)

app.include_router(health.router)
app.include_router(webhook.router)
app.include_router(admin_docs.router)
app.include_router(admin_users.router)
app.include_router(admin_users.login_router)
app.include_router(admin_logs.router)
