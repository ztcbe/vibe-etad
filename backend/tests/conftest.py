import os

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from db.base import Base
from db.session import get_session
from app.main import app

TEST_DB_URL = os.getenv("TEST_DATABASE_URL", "postgresql+asyncpg://zvibe:zvibe@localhost:5432/zvibe_test")

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(TEST_DB_URL, echo=False, poolclass=NullPool)
    return _engine


async def _ensure_tables():
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)


async def _truncate_all(engine):
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(text(f'TRUNCATE TABLE "{table.name}" CASCADE'))


@pytest_asyncio.fixture
async def client():
    engine = _get_engine()
    await _ensure_tables()
    await _truncate_all(engine)

    # Initialize shared session service with test database
    from modules.assistant.session import init_session_service, shutdown_session_service
    await init_session_service(TEST_DB_URL)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.pop(get_session, None)
    await shutdown_session_service()


@pytest_asyncio.fixture
async def registered_user(client):
    """Register a test user and return the tokens."""
    resp = await client.post("/api/auth/register", json={
        "username": "testuser",
        "password": "testpass123",
        "confirm_password": "testpass123",
        "date_of_birth": "2000-01-01",
    })
    data = resp.json()
    if not data["success"]:
        raise RuntimeError(f"Failed to register test user: {data.get('error')}")
    return data["data"]


@pytest_asyncio.fixture
async def auth_headers(registered_user):
    """Return auth headers with valid access token."""
    return {"Authorization": f"Bearer {registered_user['access_token']}"}
