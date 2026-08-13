from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.browser.mock import MockBrowserAdapter
from app.models.configuration import PlatformConfig, PromptTemplate
from app.models.content import ContentItem, ContentMetricSnapshot
from app.models.research_task import ResearchTask, ResearchTaskStatus
from app.providers.llm import LLMProvider
from app.services.collection import ContentCollectionService
from app.services.query_expansion import QueryExpansionService


class FixedProvider:
    async def generate_structured(self, *, prompt: str, context: dict[str, object]) -> dict[str, list[str]]:
        return {"core_keywords": ["must stay as supplement"], "long_tail_keywords": ["portable coffee guide"], "trend_keywords": [], "audience_keywords": [], "scenario_keywords": [], "style_keywords": []}


def test_collection_defaults_include_enabled_generic_public_adapter(client) -> None:
    assert client.get("/api/v1/config/settings").status_code == 200
    platform = next(item for item in client.get("/api/v1/config/platforms").json() if item["name"] == "generic-web")
    assert platform["enabled"] is True
    assert platform["search_url_template"].startswith("https://")


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
