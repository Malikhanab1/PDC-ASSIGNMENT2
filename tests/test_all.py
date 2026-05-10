import os
import pytest

from fastapi.testclient import TestClient

os.environ.setdefault(
    "DATABASE_URL",
    "sqlite:///./test_studysync.db"
)

import app.database as db_module

db_module.SQLALCHEMY_DATABASE_URL = "sqlite:///./test_studysync.db"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

test_engine = create_engine(
    "sqlite:///./test_studysync.db",
    connect_args={"check_same_thread": False}
)

db_module.engine = test_engine

db_module.SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine
)

from app.database import Base, get_db
from app.models import Document, WebhookEvent
from app.main import app, llm_circuit_breaker

Base.metadata.create_all(bind=test_engine)

TestingSession = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine
)


def override_get_db():

    db = TestingSession()

    try:
        yield db

    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session")
def client():

    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_everything():

    db = TestingSession()

    db.query(WebhookEvent).delete()
    db.query(Document).delete()

    db.commit()
    db.close()

    llm_circuit_breaker.reset()

    yield


# middleware tests


def test_student_header_exists(client):

    response = client.get("/health")

    assert response.status_code == 200
    assert "X-Student-ID" in response.headers

    print("\nstudent header detected")


# optimistic locking tests


class TestDocumentUpdates:

    def create_sample_document(self, client):

        response = client.post(
            "/documents/",
            params={
                "title": "sample",
                "content": "initial"
            }
        )

        assert response.status_code == 201

        return response.json()

    def test_document_update_success(self, client):

        document = self.create_sample_document(client)

        response = client.put(
            f"/documents/{document['id']}",
            params={
                "content": "updated",
                "expected_version": document["version"]
            }
        )

        data = response.json()

        assert response.status_code == 200
        assert data["version"] == 2

        print("\ndocument updated correctly")

    def test_outdated_version_is_rejected(self, client):

        document = self.create_sample_document(client)

        version = document["version"]

        first = client.put(
            f"/documents/{document['id']}",
            params={
                "content": "alice update",
                "expected_version": version
            }
        )

        assert first.status_code == 200

        second = client.put(
            f"/documents/{document['id']}",
            params={
                "content": "bob update",
                "expected_version": version
            }
        )

        assert second.status_code == 409

        print("\noutdated write prevented")

    def test_multiple_updates(self, client):

        document = self.create_sample_document(client)

        for i in range(3):

            current = client.get(
                f"/documents/{document['id']}"
            ).json()

            response = client.put(
                f"/documents/{document['id']}",
                params={
                    "content": f"update-{i}",
                    "expected_version": current["version"]
                }
            )

            assert response.status_code == 200

        print("\nmultiple sequential updates succeeded")


# webhook tests


class TestWebhookHandling:

    payload = {
        "type": "subscription.cancelled",
        "data": {
            "id": "user_1"
        }
    }

    def test_new_webhook_processed(self, client):

        response = client.post(
            "/webhooks/clerk",
            json=self.payload,
            headers={"svix-id": "event_1"}
        )

        assert response.status_code == 200
        assert response.json()["status"] == "processed"

        print("\nwebhook processed")

    def test_duplicate_webhook_ignored(self, client):

        key = "duplicate_1"

        first = client.post(
            "/webhooks/clerk",
            json=self.payload,
            headers={"svix-id": key}
        )

        second = client.post(
            "/webhooks/clerk",
            json=self.payload,
            headers={"svix-id": key}
        )

        assert first.json()["status"] == "processed"
        assert second.json()["status"] == "duplicate"

        print("\nduplicate webhook ignored")

    def test_multiple_unique_events(self, client):

        for key in ["a1", "a2"]:

            response = client.post(
                "/webhooks/clerk",
                json=self.payload,
                headers={"svix-id": key}
            )

            assert response.json()["status"] == "processed"

        events = client.get("/webhooks/events").json()

        assert len(events) == 2

        print("\nmultiple webhook events stored")


# circuit breaker tests


class TestCircuitBreaker:

    def test_ai_service_operates_normally(self, client):

        response = client.post(
            "/ai/summarise",
            params={"prompt": "hello"}
        )

        body = response.json()

        assert response.status_code == 200
        assert body["status"] == "success"

        print("\nnormal AI request completed")

    def test_breaker_blocks_requests_after_repeated_failures(self, client):

        for _ in range(3):

            client.post(
                "/ai/summarise",
                params={
                    "prompt": "trigger",
                    "simulate_failure": True
                }
            )

        breaker = client.get("/ai/circuit-status").json()

        assert breaker["breaker_state"] == "OPEN"

        blocked = client.post(
            "/ai/summarise",
            params={"prompt": "new request"}
        )

        body = blocked.json()

        assert blocked.status_code == 503
        assert body["status"] == "degraded"

        print("\nbreaker correctly rejected requests")

    def test_breaker_recovers_after_timeout(self, client):

        import time

        for _ in range(3):

            client.post(
                "/ai/summarise",
                params={
                    "prompt": "fail",
                    "simulate_failure": True
                }
            )

        llm_circuit_breaker.last_error_time = (
            time.monotonic() - 100
        )

        restored = client.post(
            "/ai/summarise",
            params={"prompt": "recovery"}
        )

        data = restored.json()

        assert restored.status_code == 200
        assert data["status"] == "success"

        print("\nservice recovered successfully")