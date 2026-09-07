import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base, get_db
from app.main import app


@pytest.fixture(autouse=True)
def _disable_channel_manager(monkeypatch):
    # The real ChannelManager.sync() decrypts real channel credentials and
    # starts real long-poll tasks against the live Telegram API using
    # backend/local.db (the lifespan's SessionLocal() is bound to the real
    # DB, not the test's in-memory db_session) — replaced with no-ops so
    # TestClient(app)'s startup/shutdown never touches the network or a
    # real channel's bot token during tests.
    from app.channel_manager import channel_manager

    async def _noop_sync(db):
        return None

    async def _noop_stop_all():
        return None

    monkeypatch.setattr(channel_manager, "sync", _noop_sync)
    monkeypatch.setattr(channel_manager, "stop_all", _noop_stop_all)


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
