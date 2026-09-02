from fastapi import FastAPI

from app.routers import admin_docs, admin_users, health, webhook

app = FastAPI(title="Matcha Bot Backend")

app.include_router(health.router)
app.include_router(webhook.router)
app.include_router(admin_docs.router)
app.include_router(admin_users.router)
