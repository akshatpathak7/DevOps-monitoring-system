import os
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

os.environ.setdefault("ADMIN_PASSWORD_HASH", "pbkdf2_sha256$600000$test$unused")
os.environ.setdefault("SESSION_SECRET", "s" * 32)
os.environ.setdefault("INGEST_TOKEN", "i" * 32)
os.environ.setdefault("DEMO_CONTROL_TOKEN", "d" * 32)
os.environ["ENABLE_DETECTION"] = "false"
os.environ["OPENAI_API_KEY"] = ""
os.environ["PUBLIC_ORIGIN"] = "http://localhost:8080"
os.environ["COOKIE_SECURE"] = "false"
if os.getenv("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]

from app.config import get_settings
from app.models import Base, Incident
from app.security import hash_password, login_attempts


@pytest.fixture
def settings():
    return get_settings().model_copy()


@pytest.fixture(autouse=True)
def reset_login_throttling():
    login_attempts.clear()


@pytest.fixture
async def sessions():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a disposable PostgreSQL database for integration tests")
    if "test" not in url.rsplit("/", 1)[-1]:
        raise RuntimeError("Integration database name must contain 'test'; tables are reset")
    engine = create_async_engine(url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
async def db(sessions):
    async with sessions() as session:
        yield session


@pytest.fixture
async def incident(db):
    now = datetime.now(timezone.utc)
    row = Incident(
        title="Elevated HTTP errors",
        severity="warning",
        incident_type="http_errors",
        service_name="demo-service",
        description="Errors exceeded threshold",
        detected_at=now,
        last_seen_at=now,
        status="open",
        metric_name="error_rate",
        metric_value=50,
        threshold=10,
        window_seconds=60,
        metric_evidence={"error_rate": 50, "up": 1},
        log_excerpt=[
            {
                "timestamp": now.isoformat(),
                "level": "ERROR",
                "service_name": "demo-service",
                "message": "Synthetic dependency error",
            }
        ],
    )
    db.add(row)
    await db.commit()
    return row


@pytest.fixture
async def client(sessions):
    from app.database import get_db
    from app.main import app

    async def override():
        async with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = override
    get_settings().admin_password_hash = hash_password("TestPassword123!")
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:8080") as http:
            yield http
    app.dependency_overrides.clear()


@pytest.fixture
async def admin(client):
    response = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "TestPassword123!"},
        headers={"Origin": "http://localhost:8080"},
    )
    assert response.status_code == 200
    return {"Origin": "http://localhost:8080", "X-CSRF-Token": response.json()["csrf"]}
