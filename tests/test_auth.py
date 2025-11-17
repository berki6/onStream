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
        json={
            "username": "testuser123",
            "email": "test@example.com",
            "password": "Password123!",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["data"]["username"] == "testuser123"
    assert data["data"]["email"] == "test@example.com"


def test_register_duplicate_username(db_session: Session):
    """Test registering with duplicate username fails"""
    # First registration
    client.post(
        "/auth/register",
        json={
            "username": "dupuser",
            "email": "dup1@example.com",
            "password": "Password123!",
        },
    )

    # Second registration with same username
    response = client.post(
        "/auth/register",
        json={
            "username": "dupuser",
            "email": "dup2@example.com",
            "password": "Password123!",
        },
    )
    assert response.status_code == 400
    assert "Username already registered" in response.json()["detail"]


def test_register_duplicate_email(db_session: Session):
    """Test registering with duplicate email fails"""
    # First registration
    client.post(
        "/auth/register",
        json={
            "username": "user1",
            "email": "dup@example.com",
            "password": "Password123!",
        },
    )

    # Second registration with same email
    response = client.post(
        "/auth/register",
        json={
            "username": "user2",
            "email": "dup@example.com",
            "password": "Password123!",
        },
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
    assert "access_token" in tokens["data"]
    assert tokens["data"]["token_type"] == "bearer"


def test_login_invalid_credentials():
    """Test login with invalid credentials"""
    response = client.post(
        "/auth/login",
        data={"username": "nonexistent", "password": "wrongpass"},
    )
    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]


def test_register_empty_fields(db_session: Session):
    """Test registration with empty required fields"""
    # Test empty username
    response = client.post(
        "/auth/register",
        json={"username": "", "email": "test1@example.com", "password": "Password123!"},
    )
    assert response.status_code == 422  # Validation error

    # Test empty email
    response = client.post(
        "/auth/register",
        json={"username": "testuser1", "email": "", "password": "Password123!"},
    )
    assert response.status_code == 422

    # Test empty password
    response = client.post(
        "/auth/register",
        json={"username": "testuser2", "email": "test2@example.com", "password": ""},
    )
    assert response.status_code == 422


def test_register_invalid_email_format(db_session: Session):
    """Test registration with invalid email format"""
    response = client.post(
        "/auth/register",
        json={
            "username": "testuser3",
            "email": "invalid-email",
            "password": "Password123!",
        },
    )
    assert response.status_code == 422  # Pydantic validation


def test_register_username_too_long(db_session: Session):
    """Test registration with username that's too long"""
    long_username = "a" * 51  # Assuming max length is 50
    response = client.post(
        "/auth/register",
        json={
            "username": long_username,
            "email": "test4@example.com",
            "password": "Password123!",
        },
    )
    assert response.status_code == 422  # Validation error


def test_register_email_too_long(db_session: Session):
    """Test registration with email that's too long"""
    long_email = "a" * 90 + "@example.com"  # Assuming max length is 100
    response = client.post(
        "/auth/register",
        json={"username": "testuser5", "email": long_email, "password": "Password123!"},
    )
    assert response.status_code == 422


def test_login_missing_fields():
    """Test login with missing fields"""
    # Missing username
    response = client.post(
        "/auth/login",
        data={"password": "testpass"},
    )
    assert response.status_code == 422

    # Missing password
    response = client.post(
        "/auth/login",
        data={"username": "testuser"},
    )
    assert response.status_code == 422


def test_login_empty_credentials():
    """Test login with empty credentials"""
    response = client.post(
        "/auth/login",
        data={"username": "", "password": ""},
    )
    assert response.status_code == 401


def test_register_special_characters_in_username(db_session: Session):
    """Test registration with special characters in username"""
    # Test valid special characters (should work)
    response = client.post(
        "/auth/register",
        json={
            "username": "test_user-123",
            "email": "special@example.com",
            "password": "Password123!",
        },
    )
    assert response.status_code == 201

    # Clean up
    # Note: In a real test, we'd clean up, but for this example we'll skip


def test_register_case_sensitive_username(db_session: Session):
    """Test that usernames are case sensitive"""
    # Register with lowercase
    client.post(
        "/auth/register",
        json={
            "username": "TestUser6",
            "email": "case1@example.com",
            "password": "Password123!",
        },
    )

    # Try to register with different case
    response = client.post(
        "/auth/register",
        json={
            "username": "testuser6",
            "email": "case2@example.com",
            "password": "Password123!",
        },
    )
    assert response.status_code == 201  # Should succeed (case sensitive)


def test_login_case_sensitive_username(test_user):
    """Test login with case sensitive username"""
    # Try login with wrong case
    response = client.post(
        "/auth/login",
        data={"username": "TestUser", "password": "testpass"},  # Wrong case
    )
    assert response.status_code == 401


def test_register_sql_injection_attempt(db_session: Session):
    """Test protection against SQL injection in registration"""
    malicious_username = "'; DROP TABLE users; --"
    response = client.post(
        "/auth/register",
        json={
            "username": malicious_username,
            "email": "sql@example.com",
            "password": "Password123!",
        },
    )
    # Should either succeed (escaped) or fail validation, but not execute SQL
    assert response.status_code in [201, 422]


def test_login_sql_injection_attempt():
    """Test protection against SQL injection in login"""
    malicious_username = "' OR '1'='1"
    response = client.post(
        "/auth/login",
        data={"username": malicious_username, "password": "anything"},
    )
    assert response.status_code == 401  # Should not bypass authentication


def test_register_xss_attempt(db_session: Session):
    """Test protection against XSS in registration fields"""
    xss_username = "<script>alert('xss')</script>"
    response = client.post(
        "/auth/register",
        json={
            "username": xss_username,
            "email": "xss@example.com",
            "password": "Password123!",
        },
    )
    # Should fail validation due to invalid username characters
    assert response.status_code == 422


def test_multiple_concurrent_registrations(db_session: Session):
    """Test handling multiple concurrent registrations"""
    import threading
    import time

    results = []

    def register_user(index):
        response = client.post(
            "/auth/register",
            json={
                "username": f"concurrent{index}",
                "email": f"concurrent{index}@example.com",
                "password": "Password123!",
            },
        )
        results.append((index, response.status_code))

    # Start multiple threads
    threads = []
    for i in range(5):
        t = threading.Thread(target=register_user, args=(i,))
        threads.append(t)
        t.start()

    # Wait for all threads
    for t in threads:
        t.join()

    # Check results - should all succeed or some fail due to unique constraints
    success_count = sum(1 for _, code in results if code == 201)
    assert success_count >= 1  # At least one should succeed


def test_password_hashing_security():
    """Test that passwords are properly hashed"""
    from src.core.auth import get_password_hash, verify_password

    password = "mySecurePassword123!"

    # Hash the password
    hashed = get_password_hash(password)

    # Verify it's hashed (not the same as original)
    assert hashed != password
    assert len(hashed) > len(password)  # Hashes are typically longer

    # Verify it can be verified
    assert verify_password(password, hashed)
    assert not verify_password("wrongpassword", hashed)


def test_jwt_token_structure(test_user):
    """Test JWT token structure and content"""
    from jose import jwt
    from src.core.config import settings

    response = client.post(
        "/auth/login",
        data={"username": "testuser", "password": "testpass"},
    )
    assert response.status_code == 200

    token = response.json()["data"]["access_token"]

    # Decode token (without verification for testing)
    decoded = jwt.decode(token, "", options={"verify_signature": False})

    # Check required claims
    assert "sub" in decoded  # Subject (username)
    assert "exp" in decoded  # Expiration
    assert decoded["sub"] == "testuser"

    # Check expiration is in the future
    import time

    assert decoded["exp"] > time.time()


def test_token_expiration():
    """Test token expiration handling"""
    import time
    from datetime import timedelta
    from src.core.auth import create_access_token
    from src.core.config import settings

    # Create a token that expires immediately
    token = create_access_token(
        {"sub": "testuser"}, expires_delta=timedelta(seconds=-1)
    )

    # Try to access protected endpoint with expired token
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/videos/", headers=headers)
    assert response.status_code == 401
    assert "Could not validate credentials" in response.json()["detail"]


def test_malformed_jwt_token():
    """Test handling of malformed JWT tokens"""
    headers = {"Authorization": "Bearer invalid.jwt.token"}
    response = client.get("/videos/", headers=headers)
    assert response.status_code == 401


def test_missing_bearer_prefix(test_user):
    """Test tokens without Bearer prefix"""
    # Create valid token first
    response = client.post(
        "/auth/login",
        data={"username": "testuser", "password": "testpass"},
    )
    assert response.status_code == 200  # Ensure login succeeds
    token = response.json()["data"]["access_token"]

    # Try without Bearer prefix
    headers = {"Authorization": token}  # Missing "Bearer "
    response = client.get("/videos/", headers=headers)
    assert response.status_code == 403
