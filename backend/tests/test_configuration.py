import pytest
from fastapi.testclient import TestClient

from app.browser.mock import MockBrowserAdapter
from app.models.configuration import AIProviderConfig
from app.services.provider_configuration_test import ProviderConfigurationTestService


def test_setting_defaults_are_persisted_and_updatable(client: TestClient) -> None:
    response = client.get("/api/v1/config/settings")
    assert response.status_code == 200
    keys = {item["key"] for item in response.json()}
    assert {"collection_defaults", "browser_defaults"} <= keys
    browser_defaults = next(item for item in response.json() if item["key"] == "browser_defaults")
    assert browser_defaults["value"]["headers"] == {}
    platforms = client.get("/api/v1/config/platforms").json()
    xiaohongshu = next(item for item in platforms if item["name"] == "xiaohongshu")
    assert xiaohongshu["selectors"]["search"]["result_container"] == "section.note-item"
    updated = client.put("/api/v1/config/settings/collection_defaults", json={"value": {"max_items": 80}, "description": "Test"})
    assert updated.status_code == 200
    assert updated.json()["value"] == {"max_items": 80}


def test_browser_headers_are_persisted_and_reject_injection(client: TestClient) -> None:
    payload = {"headless": True, "timeout_seconds": 30, "download_images": False, "headers": {"Cookie": "session=example", "Authorization": "Bearer example"}}
    saved = client.put("/api/v1/config/settings/browser_defaults", json={"value": payload, "description": "Browser headers"})
    assert saved.status_code == 200
    assert saved.json()["value"]["headers"]["Cookie"].endswith("mple")
    assert saved.json()["value"]["headers"]["Cookie"] != payload["headers"]["Cookie"]
    preserved = client.put("/api/v1/config/settings/browser_defaults", json={"value": saved.json()["value"], "description": "Browser headers"})
    assert preserved.status_code == 200
    assert preserved.json()["value"]["headers"] == saved.json()["value"]["headers"]

    invalid = client.put("/api/v1/config/settings/browser_defaults", json={"value": {"headers": {"Cookie\nInjected": "value"}}})
    assert invalid.status_code == 422


def test_system_browser_configuration_requires_a_local_cdp_endpoint(client: TestClient) -> None:
    remote = client.put("/api/v1/config/settings/browser_defaults", json={"value": {"mode": "system_cdp", "cdp_endpoint": "http://192.0.2.1:9222", "headers": {}}})
    assert remote.status_code == 422
    local = client.put("/api/v1/config/settings/browser_defaults", json={"value": {"mode": "system_cdp", "cdp_endpoint": "http://127.0.0.1:9222", "headers": {}}})
    assert local.status_code == 200


def test_system_browser_connection_test_uses_a_temporary_blank_tab(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.collection import ContentCollectionService

    browser = MockBrowserAdapter()
    monkeypatch.setattr(ContentCollectionService, "_create_browser", staticmethod(lambda _: browser))
    client.put("/api/v1/config/settings/browser_defaults", json={"value": {"mode": "system_cdp", "cdp_endpoint": "http://127.0.0.1:9222", "headers": {}}})

    response = client.post("/api/v1/config/browser/test-connection")

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert browser.current_url == "about:blank"


@pytest.mark.anyio
async def test_ai_provider_configuration_test_uses_synthetic_input() -> None:
    class FakeProvider:
        last_endpoint = "https://provider.example/v1/responses"
        last_request_preview = '{"route":"openai_responses"}'

        async def generate_structured(self, *, prompt, context):
            assert "llm" in prompt
            return {"ok": True}

        async def analyze_image_bytes(self, *, image_bytes, mime_type, prompt, context):
            assert mime_type == "image/png"
            assert image_bytes
            return {"ok": True}

    config = AIProviderConfig(name="test", provider_type="vision", base_url="https://provider.example", model_name="model", api_key="key", enabled=True)
    result = await ProviderConfigurationTestService(provider_factory=lambda _: FakeProvider()).run(config)  # type: ignore[arg-type]

    assert result.success is True
    assert result.endpoint == "https://provider.example/v1/responses"
    assert result.request_preview == '{"route":"openai_responses"}'
    assert result.response_preview == '{"ok": true}'


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
    provider = client.post("/api/v1/config/ai-providers", json={"name": "local", "provider_type": "llm", "api_key": "secret-token", "protocol": "openai_responses", "capabilities": {"text": True, "structured_output": True}, "priority": 10})
    assert provider.status_code == 201
    assert provider.json()["api_key"] == "********oken"
    assert provider.json()["protocol"] == "openai_responses"
    assert provider.json()["priority"] == 10
    assert client.get("/api/v1/config/platforms").json()[0]["enabled"] is True


def test_platform_configuration_accepts_nested_selector_groups_and_reports_validation(client: TestClient) -> None:
    nested = client.post("/api/v1/config/platforms", json={
        "name": "nested-platform", "selectors": {"search": {"result_container": ".card", "content_link": "a"}, "detail": {"content": ".body"}}, "parser_rules": {},
    })
    assert nested.status_code == 201
    assert nested.json()["selectors"]["detail"]["content"] == ".body"
    malformed = client.post("/api/v1/config/platforms", json={"name": "bad-platform", "selectors": {"search": {"nested": {"too": "deep"}}}, "parser_rules": {}})
    assert malformed.status_code == 422
