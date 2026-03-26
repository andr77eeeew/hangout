from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from app.api import health, auth, profile
import logging

from app.core.config import settings
from app.core.redis_client import redis_client
from app.core.storage import ensure_bucket_exists

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await ensure_bucket_exists()
    await redis_client.ping()
    try:
        yield
    finally:
        await redis_client.aclose()


app = FastAPI(
    swagger_ui_parameters={"persistAuthorization": True},
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(profile.router)


@app.get("/")
async def root():
    return {"project": "Hangout", "version": "0.1.0"}