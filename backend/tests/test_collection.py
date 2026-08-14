from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.browser.mock import MockBrowserAdapter
from app.models.configuration import PlatformConfig, PromptTemplate
from app.models.content import ContentItem, ContentMetricSnapshot
from app.models.research_task import ResearchTask, ResearchTaskStatus
from app.providers.llm import LLMProvider
from app.services.collection import ContentCollectionService
from app.services.platform_configuration_test import PlatformConfigurationTestService
from app.services.query_expansion import QueryExpansionService


class FixedProvider:
    async def generate_structured(self, *, prompt: str, context: dict[str, object]) -> dict[str, list[str]]:
        return {"core_keywords": ["must stay as supplement"], "long_tail_keywords": ["portable coffee guide"], "trend_keywords": [], "audience_keywords": [], "scenario_keywords": [], "style_keywords": []}


def test_collection_defaults_include_enabled_generic_public_adapter(client) -> None:
    assert client.get("/api/v1/config/settings").status_code == 200
    platform = next(item for item in client.get("/api/v1/config/platforms").json() if item["name"] == "generic-web")
    assert platform["enabled"] is True
    assert platform["search_url_template"].startswith("https://")


def test_collection_passes_configured_headers_to_browser() -> None:
    browser = ContentCollectionService._create_browser({"headless": True, "timeout_seconds": 15, "headers": {"Cookie": "session=example", "Authorization": "Bearer example"}})
    assert browser.headers == {"Cookie": "session=example", "Authorization": "Bearer example"}


def test_collection_can_connect_to_a_local_system_browser_only() -> None:
    browser = ContentCollectionService._create_browser({"mode": "system_cdp", "cdp_endpoint": "http://127.0.0.1:9222", "timeout_seconds": 15})
    assert browser.cdp_endpoint == "http://127.0.0.1:9222"
    with pytest.raises(ValueError, match="localhost"):
        ContentCollectionService._create_browser({"mode": "system_cdp", "cdp_endpoint": "http://192.0.2.1:9222"})


@pytest.mark.anyio
async def test_platform_configuration_test_uses_nested_selectors_and_returns_first_content(client) -> None:
    from app.core.database import get_db
    session: Session = next(client.app.dependency_overrides[get_db]())
    config = PlatformConfig(
        name="nested-test", search_url_template="https://example.test/search?q={query}",
        selectors={"search": {"result_container": ".card", "content_link": "a", "cover": "img", "title": ".title", "author": ".author", "like_count": ".likes"}, "detail": {"content": ".body", "image": "img", "collect_count": ".collect", "comment_count": ".comment"}},
        parser_rules={"content_id": {"source": "url", "pattern": "/explore/([^/?]+)"}, "url": {"source": "content_link", "type": "href"}, "cover_url": {"source": "cover", "type": "src"}, "text": {"source": "content", "type": "text"}, "images": {"source": "image", "type": "src_list"}, "collect_count": {"source": "collect_count", "type": "compact_number"}},
    )
    session.add(config)
    session.commit()
    browser = MockBrowserAdapter([{"content_link": "https://example.test/explore/abc", "cover": "https://example.test/cover.jpg", "title": "First post", "author": "Creator", "like_count": "1.2k", "content": "Visible detail", "image": ["https://example.test/one.jpg", "https://example.test/two.jpg"], "collect_count": "3821", "comment_count": "216"}])

    result = await PlatformConfigurationTestService(session, browser_factory=lambda _: browser).run(config, query="coffee", limit=50)

    assert result.success is True
    assert result.search_result_count == 1
    assert result.first_result and result.first_result["external_id"] == "abc"
    assert result.first_result["like_count"] == 1200
    assert result.detail_result and result.detail_result["text"] == "Visible detail"
    assert result.detail_result["favorite_count"] == 3821
    assert result.detail_result["image_urls"] == ["https://example.test/one.jpg", "https://example.test/two.jpg"]


@pytest.mark.anyio
async def test_collection_expands_persists_media_and_snapshots(client, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    # Use the API-created database session by taking its dependency override iterator.
    from app.core.database import get_db
    from app.core.config import Settings
    from app.services import collection

    monkeypatch.setattr(collection, "get_settings", lambda: Settings(data_dir=tmp_path / "runtime-data"))
    session: Session = next(client.app.dependency_overrides[get_db]())
    session.add_all([
        PlatformConfig(name="generic-web", search_url_template="https://example.test/search?q={query}", selectors={}, parser_rules={}),
        PromptTemplate(name="query", purpose="query_expansion", template="Query {topic}", enabled=True),
    ])
    task = ResearchTask(platform="generic-web", topic="portable coffee", keywords=["travel coffee"], time_range="7d", max_items=5, research_goals=None)
    session.add(task)
    session.commit()
    browser = MockBrowserAdapter([{
        "external_id": "abc", "url": "https://example.test/coffee", "title": "Coffee kit", "text": "A public post",
        "like_count": "1.2k", "image_urls": ["https://example.test/image.jpg"],
    }])
    service = ContentCollectionService(
        session, browser_factory=lambda _: browser,
        query_expansion=QueryExpansionService(session, provider=FixedProvider()),
    )
    result = await service.run(task)
    assert result.status == ResearchTaskStatus.COMPLETED
    assert result.expanded_keywords is not None
    assert result.expanded_keywords["core_keywords"][0] == "travel coffee"
    item = session.query(ContentItem).one()
    assert item.like_count == 1200
    assert item.local_image_paths and item.local_image_paths[0].endswith("image-1.jpg")
    assert session.query(ContentMetricSnapshot).count() == 3  # each query observation records a fresh snapshot


@pytest.mark.anyio
async def test_collection_marks_partial_after_per_item_failure(client) -> None:
    from app.core.database import get_db
    session: Session = next(client.app.dependency_overrides[get_db]())
    session.add(PlatformConfig(name="generic-web", search_url_template="https://example.test/?q={query}", selectors={}, parser_rules={}))
    task = ResearchTask(platform="generic-web", topic="topic", keywords=["one"], time_range="7d", max_items=3, research_goals=None)
    session.add(task)
    session.commit()
    browser = MockBrowserAdapter([{}])
    result = await ContentCollectionService(session, browser_factory=lambda _: browser).run(task)
    assert result.status == ResearchTaskStatus.PARTIAL
    assert result.error_message


def test_run_and_contents_endpoints_report_progress(client, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api import research_tasks
    from app.models.configuration import PlatformConfig
    from app.models.content import ContentItem

    created = client.post("/api/v1/research/tasks", json={"platform": "generic-web", "topic": "coffee", "keywords": ["coffee"], "time_range": "7d"}).json()
    assert created["current_stage"] == "PENDING"
    assert created["collected_count"] == 0
    # The endpoint's asynchronous collector is separately unit-tested above; only route integration is mocked here.
    async def fake_run(self, task):
        task.status = ResearchTaskStatus.COMPLETED
        self.database.add(ContentItem(research_task_id=task.id, platform=task.platform, external_id="endpoint", url="https://example.test/x", image_urls=[], local_image_paths=[], video_urls=[]))
        self.database.commit()
        return task
    monkeypatch.setattr(research_tasks.ContentCollectionService, "run", fake_run)
    response = client.post(f"/api/v1/research/tasks/{created['id']}/run")
    assert response.status_code == 200
    assert response.json()["progress"] == 100
    contents = client.get(f"/api/v1/research/tasks/{created['id']}/contents")
    assert contents.status_code == 200
    assert contents.json()[0]["external_id"] == "endpoint"
