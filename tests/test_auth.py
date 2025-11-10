import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from src.main import app
from src.core.database import get_db
from tests.conftest import override_get_db
import redis
from src.core.config import settings

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def test_register_user(db_session: Session):
    """Test user registration"""
    # Clear Redis if needed for testing
    try:
        redis_client = redis.from_url(settings.REDIS_URL)
        redis_client.flushdb()
    except:
        pass

    response = client.post(
        "/auth/register",
        json={"username": "newuser", "email": "new@example.com", "password": "newpass"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newuser"
    assert data["email"] == "new@example.com"


def test_register_duplicate_username(db_session: Session):
    """Test registering with duplicate username fails"""
    # First registration
    client.post(
        "/auth/register",
        json={"username": "dupuser", "email": "dup1@example.com", "password": "pass"},
    )

    # Second registration with same username
    response = client.post(
        "/auth/register",
        json={"username": "dupuser", "email": "dup2@example.com", "password": "pass"},
    )
    assert response.status_code == 400
    assert "Username already registered" in response.json()["detail"]


def test_register_duplicate_email(db_session: Session):
    """Test registering with duplicate email fails"""
    # First registration
    client.post(
        "/auth/register",
        json={"username": "user1", "email": "dup@example.com", "password": "pass"},
    )

    # Second registration with same email
    response = client.post(
        "/auth/register",
        json={"username": "user2", "email": "dup@example.com", "password": "pass"},
    )
    assert response.status_code == 400
    assert "Email already registered" in response.json()["detail"]


def test_login(test_user):
    """Test user login"""
    response = client.post(
        "/auth/login",
        data={"username": "testuser", "password": "testpass"},
    )
    assert response.status_code == 200
    tokens = response.json()
    assert "access_token" in tokens
    assert tokens["token_type"] == "bearer"


def test_login_invalid_credentials():
    """Test login with invalid credentials"""
    response = client.post(
        "/auth/login",
        data={"username": "nonexistent", "password": "wrongpass"},
    )
    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]
