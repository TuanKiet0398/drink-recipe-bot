import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main_module
from app.db.base import Base, get_db
from app.main import app


async def _noop_poller() -> None:
    # The real poller makes live Telegram API calls in a long-running loop —
    # replaced with a no-op that just waits to be cancelled on app shutdown,
    # so tests never hit the network or block on a real long-poll.
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        raise


@pytest.fixture(autouse=True)
def _disable_telegram_poller(monkeypatch):
    monkeypatch.setattr(main_module, "run_poller", _noop_poller)

TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(bind=TEST_ENGINE, autoflush=False, autocommit=False)


@pytest.fixture()
def db_session():
    Base.metadata.create_all(bind=TEST_ENGINE)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture()
def channel_id(db_session) -> int:
    from app.db.models import Channel

    channel = Channel(
        key="test-channel",
        display_name="Test Channel",
        channel_type="telegram",
        encrypted_credentials="test-encrypted-credentials",
        is_active=True,
    )
    db_session.add(channel)
    db_session.commit()
    db_session.refresh(channel)
    return channel.id


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
