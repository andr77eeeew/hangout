from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.api import health, auth

app = FastAPI(swagger_ui_parameters={"persistAuthorization": True})

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)

@app.get("/")
async def root():
    return {"project": "Hangout", "version": "0.1.0"}