from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_register_user(test_client, db_session):
    response = test_client.post(
        "/auth/register",
        json={"username": "newuser", "email": "new@example.com", "password": "newpass"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newuser"


def test_login(test_user, test_client):
    response = test_client.post(
        "/auth/login",
        data={"username": "testuser", "password": "testpass"},
    )
    assert response.status_code == 200
    tokens = response.json()
    assert "access_token" in tokens
    assert tokens["token_type"] == "bearer"
