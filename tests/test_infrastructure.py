import pytest
import httpx

@pytest.mark.asyncio
async def test_health_check_returns_200(client: httpx.AsyncClient):
    """Verify /health returns 200 and a healthy database status."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"

@pytest.mark.asyncio
async def test_root_endpoint(client: httpx.AsyncClient):
    """Verify root endpoint returns welcome message."""
    resp = await client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert "message" in data
    assert "docs_url" in data

@pytest.mark.asyncio
async def test_security_headers_present(client: httpx.AsyncClient):
    """Verify security headers are set on responses."""
    resp = await client.get("/")
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"
    assert resp.headers.get("x-xss-protection") == "1; mode=block"
    assert "x-request-id" in resp.headers
