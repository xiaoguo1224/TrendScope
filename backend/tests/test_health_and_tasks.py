from fastapi.testclient import TestClient
from datetime import UTC, datetime

from app.core.time import as_shanghai_time


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_naive_sqlite_timestamps_are_serialized_as_east_eight() -> None:
    assert as_shanghai_time(datetime(2026, 8, 14, 8, 0)).isoformat() == "2026-08-14T16:00:00+08:00"
    assert as_shanghai_time(datetime(2026, 8, 14, 8, 0, tzinfo=UTC)).isoformat() == "2026-08-14T16:00:00+08:00"


def test_create_list_and_get_research_task(client: TestClient) -> None:
    payload = {"platform": "generic-web", "topic": "portable coffee", "keywords": ["portable coffee"], "time_range": "7d", "max_items": 20, "research_goals": "Find recurring themes"}
    created = client.post("/api/v1/research/tasks", json=payload)
    assert created.status_code == 201
    task = created.json()
    assert task["status"] == "PENDING"
    assert client.get("/api/v1/research/tasks").json()[0]["id"] == task["id"]
    assert client.get(f"/api/v1/research/tasks/{task['id']}").json()["topic"] == "portable coffee"
    assert client.get("/api/v1/research/tasks/999").status_code == 404


def test_research_task_rejects_unknown_or_disabled_platform(client: TestClient) -> None:
    unknown = client.post("/api/v1/research/tasks", json={"platform": "unknown", "topic": "coffee", "keywords": ["coffee"], "time_range": "7d", "max_items": 10})
    assert unknown.status_code == 422

    platform = next(item for item in client.get("/api/v1/config/platforms").json() if item["name"] == "generic-web")
    disabled = client.put(f"/api/v1/config/platforms/{platform['id']}", json={**platform, "enabled": False})
    assert disabled.status_code == 200
    unavailable = client.post("/api/v1/research/tasks", json={"platform": "generic-web", "topic": "coffee", "keywords": ["coffee"], "time_range": "7d", "max_items": 10})
    assert unavailable.status_code == 422
