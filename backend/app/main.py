from fastapi import FastAPI
from app.api import health, auth

app = FastAPI()

app.include_router(health.router)
app.include_router(auth.router)

@app.get("/")
async def root():
    return {"project": "Hangout", "version": "0.1.0"}