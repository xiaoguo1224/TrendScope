from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_create_list_and_get_research_task(client: TestClient) -> None:
    payload = {"platform": "generic-web", "topic": "portable coffee", "keywords": ["portable coffee"], "time_range": "7d", "max_items": 20, "research_goals": "Find recurring themes"}
    created = client.post("/api/v1/research/tasks", json=payload)
    assert created.status_code == 201
    task = created.json()
    assert task["status"] == "PENDING"
    assert client.get("/api/v1/research/tasks").json()[0]["id"] == task["id"]
    assert client.get(f"/api/v1/research/tasks/{task['id']}").json()["topic"] == "portable coffee"
    assert client.get("/api/v1/research/tasks/999").status_code == 404
