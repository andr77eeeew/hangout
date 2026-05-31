import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.internal_auth import verify_internal_api_key

dummy_app = FastAPI()


@dummy_app.get("/test-internal", dependencies=[Depends(verify_internal_api_key)])
async def dummy_endpoint() -> dict[str, str]:
    return {"status": "success"}


@pytest.mark.asyncio
async def test_internal_auth_missing_header() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=dummy_app), base_url="http://test"
    ) as client:
        response = await client.get("/test-internal")
        assert response.status_code == 403
        assert response.json()["detail"] == "Invalid internal API key"


@pytest.mark.asyncio
async def test_internal_auth_invalid_key() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=dummy_app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/test-internal", headers={"X-Internal-Key": "wrong-key"}
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Invalid internal API key"


@pytest.mark.asyncio
async def test_internal_auth_valid_key() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=dummy_app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/test-internal", headers={"X-Internal-Key": "test_internal_key"}
        )
        assert response.status_code == 200
        assert response.json() == {"status": "success"}
