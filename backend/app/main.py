from fastapi import FastAPI

from app.routers import health, webhook

app = FastAPI(title="Matcha Bot Backend")

app.include_router(health.router)
app.include_router(webhook.router)
