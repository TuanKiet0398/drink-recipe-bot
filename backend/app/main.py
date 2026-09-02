from fastapi import FastAPI

from app.routers import health

app = FastAPI(title="Matcha Bot Backend")

app.include_router(health.router)
