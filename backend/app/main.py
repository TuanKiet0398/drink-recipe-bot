from fastapi import FastAPI

from app.routers import admin_docs, health, webhook

app = FastAPI(title="Matcha Bot Backend")

app.include_router(health.router)
app.include_router(webhook.router)
app.include_router(admin_docs.router)
