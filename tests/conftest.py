import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.main import app
from src.core.security.passwords import get_password_hash
from src.core.config import settings
from src.infrastructure.db import models
from src.infrastructure.db.session import get_db

# Disable auth rate limiting in tests
settings.AUTH_RATE_LIMIT_PER_MINUTE = 0
# Do not spawn WHIP normalize probe threads against a real MediaMTX
settings.LIVE_NORMALIZE_ENABLED = False
settings.LIVE_ARCHIVE_ENABLED = False

SQLALCHEMY_DATABASE_URL = "sqlite:///./tests/test.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# App no longer calls create_all at import; tests own their schema.
models.Base.metadata.drop_all(bind=engine)
models.Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="function")
def client():
    return TestClient(app)


@pytest.fixture(scope="session")
def test_db():
    models.Base.metadata.create_all(bind=engine)
    yield
    models.Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(test_db):
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def test_user(db_session):
    hashed_password = get_password_hash("testpass")
    user = models.User(
        username="testuser",
        email="testuser@example.com",
        hashed_password=hashed_password,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    yield user
    db_session.delete(user)
    db_session.commit()
