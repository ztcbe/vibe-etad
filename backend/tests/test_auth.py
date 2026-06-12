import pytest


@pytest.mark.asyncio
async def test_register(client):
    resp = await client.post("/api/auth/register", json={
        "username": "new",
        "password": "securepass1",
        "confirm_password": "securepass1",
        "date_of_birth": "1998-06-15",
    })
    data = resp.json()
    assert data["success"] is True
    assert "access_token" in data["data"]
    assert "refresh_token" in data["data"]


@pytest.mark.asyncio
async def test_register_underage(client):
    resp = await client.post("/api/auth/register", json={
        "username": "young",
        "password": "securepass1",
        "confirm_password": "securepass1",
        "date_of_birth": "2015-01-01",
    })
    data = resp.json()
    assert data["success"] is False


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    await client.post("/api/auth/register", json={
        "username": "dup",
        "password": "securepass1",
        "confirm_password": "securepass1",
        "date_of_birth": "1998-01-01",
    })
    resp = await client.post("/api/auth/register", json={
        "username": "dup",
        "password": "securepass1",
        "confirm_password": "securepass1",
        "date_of_birth": "1998-01-01",
    })
    data = resp.json()
    assert data["success"] is False
    assert data["error"]["code"] == "USERNAME_EXISTS"


@pytest.mark.asyncio
async def test_login(client, registered_user):
    resp = await client.post("/api/auth/login", json={
        "username": "testuser",
        "password": "testpass123",
    })
    data = resp.json()
    assert data["success"] is True
    assert "access_token" in data["data"]


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    resp = await client.post("/api/auth/login", json={
        "username": "testuser",
        "password": "wrongpassword",
    })
    data = resp.json()
    assert data["success"] is False


@pytest.mark.asyncio
async def test_me(client, auth_headers):
    resp = await client.get("/api/auth/me", headers=auth_headers)
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["username"] == "testuser"
    assert data["data"]["completeness_score"] == 0


@pytest.mark.asyncio
async def test_refresh(client, registered_user):
    resp = await client.post("/api/auth/refresh", json={
        "refresh_token": registered_user["refresh_token"],
    })
    data = resp.json()
    assert data["success"] is True
    assert "access_token" in data["data"]
