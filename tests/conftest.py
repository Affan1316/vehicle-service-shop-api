import os
# Force testing environment before importing the app/database modules
os.environ["ENVIRONMENT"] = "testing"

import pytest
import asyncio
from typing import AsyncGenerator
import httpx
from sqlalchemy import text

from app.main import app
from app.database import engine

@pytest.fixture
async def client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Async HTTP client fixture."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

@pytest.fixture
async def manager_headers(client: httpx.AsyncClient) -> dict:
    """Fixture to obtain auth headers for a Manager user."""
    username = "test_fixture_mgr"
    email = "fixture_mgr@test.com"
    password = "mgrpassword123"
    await client.post("/auth/register", json={
        "username": username,
        "email": email,
        "password": password,
        "role": "manager"
    })
    login_resp = await client.post("/auth/token", data={
        "username": username,
        "password": password
    })
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
async def advisor_headers(client: httpx.AsyncClient) -> dict:
    """Fixture to obtain auth headers for an Advisor user."""
    username = "test_fixture_adv"
    email = "fixture_adv@test.com"
    password = "advpassword123"
    await client.post("/auth/register", json={
        "username": username,
        "email": email,
        "password": password,
        "role": "advisor"
    })
    login_resp = await client.post("/auth/token", data={
        "username": username,
        "password": password
    })
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
async def technician_headers(client: httpx.AsyncClient) -> dict:
    """Fixture to obtain auth headers for a Technician user."""
    username = "test_fixture_tech"
    email = "fixture_tech@test.com"
    password = "techpassword123"
    await client.post("/auth/register", json={
        "username": username,
        "email": email,
        "password": password,
        "role": "technician"
    })
    login_resp = await client.post("/auth/token", data={
        "username": username,
        "password": password
    })
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
async def customer_headers(client: httpx.AsyncClient) -> dict:
    """Fixture to obtain auth headers for a Customer user."""
    username = "test_fixture_cust"
    email = "fixture_cust@test.com"
    password = "custpassword123"
    await client.post("/auth/register", json={
        "username": username,
        "email": email,
        "password": password,
        "role": "customer"
    })
    login_resp = await client.post("/auth/token", data={
        "username": username,
        "password": password
    })
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(autouse=True)
async def cleanup_db():
    """Clean up user_account and temporary test records before and after each test."""
    from sqlalchemy.ext.asyncio import AsyncSession
    async def _clean():
        await asyncio.sleep(0.1)  # Let any pending DB connections/sessions finish closing
        async with AsyncSession(engine) as session:
            await session.execute(text("DELETE FROM user_account WHERE username LIKE 'test_%'"))
            await session.commit()

    await _clean()
    yield
    await _clean()
