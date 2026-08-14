from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models.configuration import AIProviderConfig
from app.models.content import ContentItem, ContentMetricSnapshot
from app.models.research_task import ResearchTask
from app.schemas.analysis import TextAnalysis, VisualAnalysis
from app.providers.vision import MockVisionProvider
from app.providers.openai_compatible import _headers_for, _payload_for, _response_text, OpenAICompatibleProvider, _routes_to_try
from app.services.analysis import AnalysisService
from app.services.ranking import RankingService


def _add_task_and_item(session: Session, *, external_id: str = "one", title: str = "Compact coffee kit") -> tuple[ResearchTask, ContentItem]:
    task = ResearchTask(platform="generic-web", topic="portable coffee", keywords=["coffee"], time_range="7d", max_items=10, research_goals=None)
    session.add(task)
    session.flush()
    item = ContentItem(
        research_task_id=task.id, platform=task.platform, external_id=external_id, url=f"https://example.test/{external_id}",
        title=title, text="Bring a compact coffee kit on every trip.", like_count=100, favorite_count=20,
        image_urls=[], local_image_paths=[], video_urls=[], collected_at=datetime.now(UTC),
    )
    session.add(item)
    session.commit()
    return task, item


def test_ranking_uses_dynamic_metrics_and_null_growth_without_history(client) -> None:
    from app.core.database import get_db
    session: Session = next(client.app.dependency_overrides[get_db]())
    task, _ = _add_task_and_item(session)
    result = RankingService(session).rank_task(task.id)
    hot = result.boards[0].items[0]
    assert hot.metrics == {"like_count": 100, "favorite_count": 20}
    assert hot.engagement_score > 0
    assert hot.growth_score is None
    assert all(board.name != "Rising" for board in result.boards)
    assert any(board.name == "Most Saved" for board in result.boards)
    assert all(board.name != "Most Shared" for board in result.boards)


def test_ranking_calculates_velocity_from_two_snapshots(client) -> None:
    from app.core.database import get_db
    session: Session = next(client.app.dependency_overrides[get_db]())
    task, item = _add_task_and_item(session)
    now = datetime.now(UTC)
    session.add_all([
        ContentMetricSnapshot(content_item_id=item.id, like_count=10, captured_at=now - timedelta(hours=2)),
        ContentMetricSnapshot(content_item_id=item.id, like_count=30, captured_at=now),
    ])
    session.commit()
    result = RankingService(session).rank_task(task.id)
    hot = result.boards[0].items[0]
    assert hot.metric_velocities["like_count"].value_per_hour == pytest.approx(10)
    assert hot.growth_score is not None
    assert any(board.name == "Rising" for board in result.boards)


def test_structured_analysis_validation() -> None:
    response = {
        "hook_type": "informational", "title_structure": "descriptive", "opening_hook": "Hello", "writing_style": "concise",
        "emotion": "neutral", "pain_points": [], "benefits": [], "target_audience": [], "scenario": [], "cta": None,
        "hashtags": [], "topic_tags": [], "reusable_patterns": [],
    }
    assert TextAnalysis.model_validate(response).hook_type == "informational"
    with pytest.raises(ValidationError):
        TextAnalysis.model_validate({"hook_type": "missing fields"})
    visual = {"subject": "x", "main_colors": [], "secondary_colors": [], "style": "x", "composition": "x", "camera_angle": "x", "lighting": "x", "background": "x", "visual_focus": "x", "scene": "x", "mood": "x", "target_audience": [], "notable_elements": [], "reusable_visual_patterns": [], "domain_attributes": {}, "confidence": 0}
    assert VisualAnalysis.model_validate(visual).confidence == 0


@pytest.mark.anyio
async def test_mock_vision_analyzes_a_local_image_path(tmp_path) -> None:
    image = tmp_path / "public-image.jpg"
    image.write_bytes(b"not-decoded-by-mock")
    response = await MockVisionProvider().analyze_image(image_path=image, prompt="configured prompt", context={"topic": "coffee"})
    result = VisualAnalysis.model_validate(response)
    assert result.subject == "coffee"
    assert result.notable_elements == ["public-image.jpg"]


@pytest.mark.anyio
async def test_enabled_openai_compatible_provider_returns_structured_json() -> None:
    config = AIProviderConfig(name="compatible", provider_type="llm", base_url="https://provider.example", model_name="model", api_key="test-key", enabled=True)
    provider = OpenAICompatibleProvider(config)
    provider._post = lambda endpoint, payload, headers: {"choices": [{"message": {"content": '{"hook_type":"informational"}'}}]}  # type: ignore[method-assign]

    response = await provider.generate_structured(prompt="Return analysis", context={})

    assert response == {"hook_type": "informational"}
    assert provider.base_url == "https://provider.example"
    assert _routes_to_try("https://provider.example", "gpt-5.6-terra")[0] == "openai_responses"


def test_provider_url_routes_cover_supported_vendor_formats() -> None:
    assert _routes_to_try("https://api.anthropic.com/v1/messages", "claude-sonnet") == ["anthropic_messages"]
    assert _routes_to_try("https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent", "gemini-2.5-flash") == ["gemini"]
    assert _routes_to_try("http://127.0.0.1:11434/api/chat", "qwen3-vl") == ["ollama_chat"]


@pytest.mark.parametrize(
    ("route", "response"),
    [
        ("anthropic_messages", {"content": [{"type": "text", "text": '{"ok":true}'}]}),
        ("gemini", {"candidates": [{"content": {"parts": [{"text": '{"ok":true}'}]}}]}),
        ("ollama_generate", {"response": '{"ok":true}'}),
        ("ollama_chat", {"message": {"content": '{"ok":true}'}}),
    ],
)
def test_vendor_payloads_and_response_parsing(route, response) -> None:
    payload = _payload_for(route, "test-model", "system", "user", "aW1hZ2U=", "image/png")

    assert _response_text(response, route) == '{"ok":true}'
    assert payload
    assert _headers_for(route, "secret")["Content-Type"] == "application/json"


@pytest.mark.anyio
async def test_per_content_analysis_failure_is_isolated(client) -> None:
    from app.core.database import get_db
    session: Session = next(client.app.dependency_overrides[get_db]())
    task, _ = _add_task_and_item(session, external_id="ok")
    broken = ContentItem(research_task_id=task.id, platform=task.platform, external_id="broken", url="https://example.test/broken", title="Broken", image_urls=[], local_image_paths=[], video_urls=[])
    session.add(broken)
    session.commit()

    class FailingForOne:
        async def generate_structured(self, *, prompt, context):
            if context["title"] == "Broken":
                raise RuntimeError("bad response")
            return {"hook_type": "informational", "title_structure": "descriptive", "opening_hook": "x", "writing_style": "concise", "emotion": "neutral", "pain_points": [], "benefits": [], "target_audience": [], "scenario": [], "cta": None, "hashtags": [], "topic_tags": [], "reusable_patterns": []}

    result = await AnalysisService(session, llm_provider=FailingForOne()).analyze_task(task)
    assert len(result) == 2
    assert any(item.analysis_error for item in result)
    assert any(item.text_analysis for item in result)


def test_analysis_endpoints_and_database_provider_selection(client) -> None:
    from app.core.database import get_db
    session: Session = next(client.app.dependency_overrides[get_db]())
    task, _ = _add_task_and_item(session)
    session.add(AIProviderConfig(name="configured-but-offline", provider_type="llm", model_name="any", api_key="do-not-log", enabled=True))
    session.commit()
    assert client.get(f"/api/v1/research/tasks/{task.id}/rankings").status_code == 200
    assert client.get(f"/api/v1/research/tasks/{task.id}/analysis").status_code == 200
    trend = client.get(f"/api/v1/research/tasks/{task.id}/trends")
    assert trend.status_code == 200
    assert trend.json()["insufficient_data"] is True


def test_complete_provider_configuration_selects_the_real_adapter(client) -> None:
    from app.core.database import get_db
    session: Session = next(client.app.dependency_overrides[get_db]())
    session.add(AIProviderConfig(name="compatible", provider_type="llm", base_url="https://provider.example/v1", model_name="model", api_key="test-key", enabled=True))
    session.commit()

    assert isinstance(AnalysisService(session).llm_provider, OpenAICompatibleProvider)
