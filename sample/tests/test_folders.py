import pytest
from fastapi.testclient import TestClient

from sample.src.auth import get_current_user
from sample.src.main import app
from sample.src.models import NoteFolder, Organization


@pytest.fixture
def client():
    # Using TestClient as a context manager runs the lifespan handler.
    with TestClient(app) as test_client:
        yield test_client


def test_create_folder_unauthenticated(client):
    resp = client.post(
        "/sample/v1/folders/",
        json={"name": "Root", "organization_id": "org1"},
    )
    assert resp.status_code == 401


def test_create_folder_authenticated(client, monkeypatch):
    def fake_user():
        from sample.src.models import User
        return User(name="admin", email="admin@test", roles=["admin"])

    def fake_find_one(query):
        class Org:
            id = "org1"
            name = "Org1"

        return Org()

    def fake_insert(self):
        return self

    # Override the exact dependency object used by the route.
    monkeypatch.setitem(app.dependency_overrides, get_current_user, fake_user)
    monkeypatch.setattr(Organization, "find_one", fake_find_one)
    monkeypatch.setattr(NoteFolder, "insert", fake_insert)

    resp = client.post(
        "/sample/v1/folders/",
        json={"name": "Root", "organization_id": "org1"},
    )
    assert resp.status_code == 201
    assert "location" in resp.json()
