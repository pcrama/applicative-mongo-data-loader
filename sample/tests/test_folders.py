from bson import ObjectId
import pytest
from fastapi.testclient import TestClient

from sample.src import auth
from sample.src.main import app
from sample.src.models import NoteFolder, Organization, User


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


def test_create_folder_authenticated_as_admin(client: TestClient, monkeypatch) -> None:
    def fake_find_one_user(_query):
        class Query:
            def run(self):
                return User(name="admin", email="admin@test", roles=["admin"])

        return Query()

    def fake_find_one(_query):
        class Query:
            def run(self):
                return Organization(
                    name="Org1", _id=ObjectId("0123456789abcdef01234567")
                )

        return Query()

    def fake_insert(self):
        self.id = ObjectId("1234567890abcdef12345678")
        return self

    monkeypatch.setattr(Organization, "find_one", fake_find_one)
    monkeypatch.setattr(NoteFolder, "insert", fake_insert)
    monkeypatch.setattr(User, "find_one", fake_find_one_user)

    resp = client.post(
        "/sample/v1/folders/",
        json={"name": "Root", "organization_id": "0123456789abcdef01234567"},
        headers={"X-User": "admin"},
    )
    assert resp.status_code == 201
    assert resp.headers["location"] == "/sample/v1/folders/1234567890abcdef12345678"
