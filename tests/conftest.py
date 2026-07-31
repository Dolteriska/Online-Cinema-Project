"""
Shared pytest fixtures for the whole test-suite.

IMPORTANT — import order matters here.
`src.config.settings.Settings()` is instantiated at *import time* and
requires several mandatory environment variables (Postgres/JWT/MinIO).
`src.services.storage` instantiates a real `S3StorageService()` (which talks
to boto3/MinIO) at *import time* as well, because it is imported transitively
by `src.main` -> `src.routes` -> `user_profile_router`.

To be able to import the application at all in a test environment (no real
MinIO/Redis running), we must:
  1. Set the required env vars *before* anything under `src` is imported.
  2. Patch `boto3.client` *before* `src.services.storage` is imported, so the
     module-level `S3StorageService()` singleton doesn't try to reach a real
     MinIO endpoint.

Both of these MUST happen at the top of this file, before any `from src...`
or `import src...` statement (including ones nested in fixtures that run at
collection time).

DATABASE STRATEGY
------------------
We use `testcontainers` to spin up a *real* Postgres instance for the whole
test session (one container, reused by every test — much faster than
starting a fresh container per test). Each test then runs inside its own
transaction that's rolled back at the end, so tests stay isolated from each
other without needing to recreate the schema every time.

Since prod/dev only ever run against Postgres, testing against Postgres too
(instead of SQLite) avoids an entire class of dialect-specific surprises:
timezone-aware datetimes, JSON columns, array types, case-sensitive LIKE,
constraint behavior, etc.

Requires Docker running locally / in CI.
"""
import os
import sys
import asyncio
from unittest.mock import MagicMock

# --- 0. Windows only: asyncpg does not play well with the default
# ProactorEventLoop (spurious "Event loop is closed" / "attached to a
# different loop" errors once a connection outlives a single test). Switch
# to the Selector-based loop for the whole test process before anything
# else touches asyncio.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# --- 1. Environment variables required by src.config.settings.Settings ---
# NOTE: POSTGRES_* values here are placeholders; the real ones (host/port/
# user/password/db) get overridden once the testcontainers Postgres instance
# is up, via the `postgres_container` fixture monkeypatching settings/env.
os.environ.setdefault("POSTGRES_USER", "test_user")
os.environ.setdefault("POSTGRES_PASSWORD", "test_password")
os.environ.setdefault("POSTGRES_DB", "test_db")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")

os.environ.setdefault("SECRET_KEY_ACCESS", "unit-test-access-secret-key")
os.environ.setdefault("SECRET_KEY_REFRESH", "unit-test-refresh-secret-key")
os.environ.setdefault("JWT_SIGNING_ALGORITHM", "HS256")

os.environ.setdefault("MINIO_ENDPOINT_INTERNAL", "http://localhost:9000")
os.environ.setdefault("MINIO_ENDPOINT_PUBLIC", "http://localhost:9000")
os.environ.setdefault("MINIO_ACCESS_KEY", "test-access-key")
os.environ.setdefault("MINIO_SECRET_KEY", "test-secret-key")
os.environ.setdefault("MINIO_BUCKET_NAME", "test-bucket")

# Patch REDIS_URL to use in-memory limiter storage in tests —
# no real Redis is spun up for the test suite.
from src.config.settings import Settings  # noqa: E402
Settings.REDIS_URL = property(lambda self: "memory://") # type: ignore[method-assign, assignment] # noqa

os.environ.setdefault("REDIS_URL", "memory://")  # can leave or remove, no longer load-bearing

# --- 2. Patch boto3.client BEFORE src.services.storage is ever imported ---
import boto3  # noqa: E402

_fake_s3_client = MagicMock()
_fake_s3_client.head_bucket.return_value = {}
boto3.client = MagicMock(return_value=_fake_s3_client)

# --- Now it is safe to import anything from the application ---


import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
import httpx  # noqa: E402
from httpx import ASGITransport  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession  # noqa: E402
from testcontainers.community.postgres import PostgresContainer  # noqa: E402

from src.database.base import Base  # noqa: E402
import src.database.models  # noqa: E402,F401  (registers all mapped classes on Base.metadata)
from src.database.models.users import UserGroupModel, UserGroupEnum  # noqa: E402
from src.database.session import get_db  # noqa: E402
from src.config.dependencies import get_jwt_auth_manager  # noqa: E402


# ---------------------------------------------------------------------------
# Celery test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def mock_celery_delay(monkeypatch):
    from celery.app.task import Task

    def _fake_delay(self, *args, **kwargs):
        return MagicMock(id="fake-task-id")

    monkeypatch.setattr(Task, "delay", _fake_delay)
    monkeypatch.setattr(Task, "apply_async", lambda self, *a, **k: MagicMock(id="fake-task-id"))


# ---------------------------------------------------------------------------
# Database: Postgres
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def postgres_container():
    """
    Spins up a single Postgres container for the whole test session.
    Reused across all tests to keep the suite fast.
    """
    with PostgresContainer("postgres:16-alpine", driver="asyncpg") as pg:
        yield pg


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def db_engine(postgres_container):
    """
    Session-scoped async engine + one-time schema creation against the
    real Postgres container.
    """
    url = postgres_container.get_connection_url()  # uses +asyncpg driver
    engine = create_async_engine(url, pool_pre_ping=True)

    # noinspection PyTypeChecker
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # noinspection PyTypeChecker
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    """
    Function-scoped session wrapped in an outer transaction that's rolled
    back after every test, so tests never see each other's data even
    though they share the same container/schema.
    """
    connection = await db_engine.connect()
    trans = await connection.begin()

    session_factory = async_sessionmaker(
        bind=connection, class_=AsyncSession, expire_on_commit=False
    )
    session = session_factory()

    yield session

    await session.close()
    await trans.rollback()
    await connection.close()


@pytest_asyncio.fixture(autouse=True)
async def seed_user_groups(db_session):
    """Registration requires basic seeding to work"""
    for group in UserGroupEnum:
        db_session.add(UserGroupModel(name=group))
    await db_session.commit()


# ---------------------------------------------------------------------------
# FastAPI app + HTTP client
# ---------------------------------------------------------------------------
@pytest.fixture
def app(db_session):
    from src.main import app as fastapi_app

    async def _override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    yield fastapi_app
    fastapi_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
@pytest.fixture
def jwt_manager():
    return get_jwt_auth_manager()


def auth_headers_for_user(user_id: int) -> dict:
    manager = get_jwt_auth_manager()
    token = manager.create_access_token({"user_id": user_id})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def make_auth_headers():
    """Returns a callable: make_auth_headers(user_id) -> {"Authorization": ...}"""
    return auth_headers_for_user
