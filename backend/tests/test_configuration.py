from fastapi.testclient import TestClient


def test_setting_defaults_are_persisted_and_updatable(client: TestClient) -> None:
    response = client.get("/api/v1/config/settings")
    assert response.status_code == 200
    keys = {item["key"] for item in response.json()}
    assert {"collection_defaults", "browser_defaults"} <= keys
    updated = client.put("/api/v1/config/settings/collection_defaults", json={"value": {"max_items": 80}, "description": "Test"})
    assert updated.status_code == 200
    assert updated.json()["value"] == {"max_items": 80}


def test_ranking_config_crud(client: TestClient) -> None:
    payload = {"name": "research-default", "like_weight": 1.0, "favorite_weight": 1.2, "comment_weight": 1.5, "share_weight": 1.5, "view_weight": 0.1, "freshness_half_life_hours": 72, "growth_window_hours": 24}
    created = client.post("/api/v1/config/ranking-configs", json=payload)
    assert created.status_code == 201
    assert client.get("/api/v1/config/ranking-configs").json()[0]["name"] == "research-default"


def test_platform_prompt_and_masked_provider_configuration(client: TestClient) -> None:
    platform = client.post("/api/v1/config/platforms", json={"name": "generic-web", "selectors": {}, "parser_rules": {}})
    assert platform.status_code == 201
    template = client.post("/api/v1/config/prompt-templates", json={"name": "text-analysis", "purpose": "text_analysis", "template": "Analyze safely"})
    assert template.status_code == 201
    provider = client.post("/api/v1/config/ai-providers", json={"name": "local", "provider_type": "llm", "api_key": "secret-token"})
    assert provider.status_code == 201
    assert provider.json()["api_key"] == "********oken"
    assert client.get("/api/v1/config/platforms").json()[0]["enabled"] is True
