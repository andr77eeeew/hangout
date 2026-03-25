from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from app.api import health, auth, profile
import logging

from app.core.storage import ensure_bucket_exists

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_bucket_exists()
    yield


app = FastAPI(swagger_ui_parameters={"persistAuthorization": True}, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
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