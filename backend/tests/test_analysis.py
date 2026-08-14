from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models.configuration import AIProviderConfig
from app.models.content import ContentItem, ContentMetricSnapshot
from app.models.research_task import ResearchTask
from app.model_gateway import ModelGateway, UnsupportedCapability
from app.schemas.analysis import TextAnalysis, VisualAnalysis
from app.providers.vision import MockVisionProvider
from app.providers.openai_compatible import _endpoint_for, _headers_for, _payload_for, _response_text, _sse_response, OpenAICompatibleProvider, _routes_to_try
from app.services.analysis import AnalysisService
from app.services.ranking import RankingService
from app.analysis_tools import TaskAnalysisToolRegistry
from app.services.task_analysis_agent import TaskAnalysisAgent


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
    assert _routes_to_try("https://router.example", "gpt-5.6-terra") == ["openai_responses", "openai_chat", "anthropic_messages"]
    assert _endpoint_for("https://router.example", "anthropic_messages") == "https://router.example/v1/messages"
    assert _routes_to_try("https://router.example", "any-model", "anthropic_messages") == ["anthropic_messages"]


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


def test_responses_route_accepts_a_chat_completion_envelope_from_a_gateway() -> None:
    assert _response_text({"choices": [{"message": {"content": '{"ok":true}'}}]}, "openai_responses") == '{"ok":true}'


def test_responses_failure_reports_the_provider_reason() -> None:
    with pytest.raises(RuntimeError, match="vision input is unsupported"):
        _response_text({"status": "failed", "error": {"message": "vision input is unsupported"}}, "openai_responses")
    payload = _payload_for("openai_responses", "model", "system", "user", None, None)
    assert payload["max_output_tokens"] == 2048


def test_responses_vision_payload_uses_top_level_instructions_and_image_detail() -> None:
    payload = _payload_for("openai_responses", "model", "system", "user", "aW1hZ2U=", "image/png")
    assert payload["instructions"] == "system"
    image = payload["input"][0]["content"][1]
    assert image["type"] == "input_image"
    assert image["detail"] == "auto"
    assert payload["stream"] is True


@pytest.mark.anyio
async def test_vision_provider_detects_png_bytes_in_legacy_bin_file(tmp_path) -> None:
    config = AIProviderConfig(name="vision", provider_type="vision", base_url="https://provider.example/v1/responses", model_name="model", api_key="test-key", enabled=True)
    provider = OpenAICompatibleProvider(config)
    image = tmp_path / "legacy-download.bin"
    image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"fixture")
    captured: dict[str, object] = {}

    def post(endpoint, payload, headers):
        captured["payload"] = payload
        return {"output_text": '{"ok":true}'}

    provider._post = post  # type: ignore[method-assign]
    assert await provider.analyze_image(image_path=image, prompt="test", context={}) == {"ok": True}
    image_url = captured["payload"]["input"][0]["content"][1]["image_url"]  # type: ignore[index]
    assert str(image_url).startswith("data:image/png;base64,")


@pytest.mark.anyio
async def test_vision_provider_rejects_unknown_binary_before_network_call(tmp_path) -> None:
    config = AIProviderConfig(name="vision", provider_type="vision", base_url="https://provider.example/v1/responses", model_name="model", api_key="test-key", enabled=True)
    provider = OpenAICompatibleProvider(config)
    unknown = tmp_path / "download.bin"
    unknown.write_bytes(b"<html>blocked</html>")
    with pytest.raises(ValueError, match="not a supported"):
        await provider.analyze_image(image_path=unknown, prompt="test", context={})


def test_responses_sse_deltas_are_assembled_into_output_text() -> None:
    raw = 'event: response.output_text.delta\ndata: {"type":"response.output_text.delta","delta":"{\\"ok"}\n\nevent: response.output_text.delta\ndata: {"type":"response.output_text.delta","delta":"\\":true}"}\n'
    assert _sse_response(raw) == {"output_text": '{"ok":true}'}


def test_completed_response_with_empty_output_allows_route_fallback() -> None:
    with pytest.raises(RuntimeError, match="API route did not produce"):
        _response_text({"status": "completed", "output": []}, "openai_responses")


@pytest.mark.anyio
async def test_plain_base_url_falls_back_to_messages_for_empty_vision_response() -> None:
    config = AIProviderConfig(name="router", provider_type="vision", base_url="https://router.example", model_name="gpt-5.6-terra", api_key="test-key", max_retries=0, enabled=True)
    provider = OpenAICompatibleProvider(config)
    calls: list[str] = []

    def post(endpoint, payload, headers):
        calls.append(endpoint)
        if endpoint.endswith("/responses"):
            return {"status": "completed", "output": []}
        if endpoint.endswith("/chat/completions"):
            raise RuntimeError("HTTP 400: protocol_not_supported")
        return {"content": [{"type": "text", "text": '{"ok":true}'}]}

    provider._post = post  # type: ignore[method-assign]
    assert await provider.analyze_image_bytes(image_bytes=b"image", mime_type="image/png", prompt="test", context={}) == {"ok": True}
    assert calls == [
        "https://router.example/v1/responses",
        "https://router.example/v1/chat/completions",
        "https://router.example/v1/messages",
    ]


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


def test_task_analysis_api_reads_persisted_summary_and_only_post_runs_model(client) -> None:
    from app.core.database import get_db
    session: Session = next(client.app.dependency_overrides[get_db]())
    task, _ = _add_task_and_item(session)

    initial = client.get(f"/api/v1/research/tasks/{task.id}/analysis")
    assert initial.status_code == 200
    assert initial.json()["copywriting_summary"] is None

    generated = client.post(f"/api/v1/research/tasks/{task.id}/analysis/run")
    assert generated.status_code == 200
    assert generated.json()["copywriting_summary"]
    persisted = client.get(f"/api/v1/research/tasks/{task.id}/analysis")
    assert persisted.status_code == 200
    assert persisted.json()["copywriting_summary"] == generated.json()["copywriting_summary"]


def test_task_analysis_tools_are_read_only_and_task_scoped(client) -> None:
    from app.core.database import get_db
    session: Session = next(client.app.dependency_overrides[get_db]())
    task, item = _add_task_and_item(session, external_id="in-task")
    _, outside = _add_task_and_item(session, external_id="outside")
    registry = TaskAnalysisToolRegistry(session, task)

    assert registry.execute("get_content_detail", {"content_item_id": item.id})["content_item_id"] == item.id
    with pytest.raises(ValueError, match="not part of this research task"):
        registry.execute("get_content_detail", {"content_item_id": outside.id})


@pytest.mark.anyio
async def test_task_analysis_agent_returns_one_summary_from_tool_evidence(client) -> None:
    from app.core.database import get_db
    session: Session = next(client.app.dependency_overrides[get_db]())
    task, _ = _add_task_and_item(session)

    class SummaryProvider:
        async def generate_structured(self, *, prompt, context):
            if context["analysis_type"] == "tool_plan":
                return {"calls": [{"name": "get_ranked_contents", "arguments": {"board": "Hot", "limit": 1}}]}
            assert context["analysis_type"] == "task_summary"
            return {
                "copywriting_summary": "A task-level copywriting conclusion.", "visual_summary": "No visual evidence.",
                "audience_summary": "A task-level audience conclusion.", "popularity_summary": "A task-level popularity conclusion.",
                "reusable_patterns": ["clear opening"], "trend_tags": ["coffee"], "evidence": ["Observed ranked content."], "limitations": [],
            }

    class NoVision:
        async def analyze_image(self, **kwargs):
            raise AssertionError("No image should be analyzed when the task has no local images")

    result = await TaskAnalysisAgent(TaskAnalysisToolRegistry(session, task), llm_provider=SummaryProvider(), vision_provider=NoVision()).run()
    assert result.copywriting_summary == "A task-level copywriting conclusion."
    assert result.reusable_patterns == ["clear opening"]


def test_complete_provider_configuration_selects_the_model_gateway(client) -> None:
    from app.core.database import get_db
    session: Session = next(client.app.dependency_overrides[get_db]())
    session.add(AIProviderConfig(name="compatible", provider_type="llm", base_url="https://provider.example/v1", model_name="model", api_key="test-key", enabled=True))
    session.commit()

    assert isinstance(AnalysisService(session).model_gateway, ModelGateway)
    assert not isinstance(AnalysisService(session).llm_provider, OpenAICompatibleProvider)


@pytest.mark.anyio
async def test_model_gateway_uses_priority_and_only_falls_back_for_retryable_errors() -> None:
    primary = AIProviderConfig(
        name="primary", provider_type="llm", base_url="https://primary.example/v1", model_name="one",
        api_key="key", protocol="openai_chat", capabilities={"text": True}, priority=10, enabled=True,
    )
    fallback = AIProviderConfig(
        name="fallback", provider_type="llm", base_url="https://fallback.example/v1", model_name="two",
        api_key="key", protocol="anthropic_messages", capabilities={"text": True}, priority=20, enabled=True,
    )
    calls: list[str] = []

    class FakeProvider:
        def __init__(self, config):
            self.config = config
            self.last_endpoint = config.base_url
            self.last_request_preview = config.protocol

        async def generate_structured(self, *, prompt, context):
            calls.append(self.config.name)
            if self.config.name == "primary":
                raise RuntimeError("HTTP 503: temporarily unavailable")
            return {"ok": True}

        async def analyze_image(self, *, image_path, prompt, context):
            raise AssertionError("not used")

    gateway = ModelGateway(configurations=[primary, fallback], provider_factory=FakeProvider)  # type: ignore[arg-type]
    assert await gateway.generate_structured(purpose="llm", prompt="test", context={}) == {"ok": True}
    assert calls == ["primary", "fallback"]
    assert gateway.last_endpoint == "https://fallback.example/v1"


@pytest.mark.anyio
async def test_model_gateway_does_not_mask_non_retryable_or_missing_capability_errors() -> None:
    invalid = AIProviderConfig(
        name="invalid", provider_type="vision", base_url="https://invalid.example/v1", model_name="one",
        api_key="key", protocol="openai_chat", capabilities={"vision": False}, priority=10, enabled=True,
    )
    gateway = ModelGateway(configurations=[invalid])
    with pytest.raises(UnsupportedCapability, match="vision"):
        await gateway.generate_structured(purpose="vision", prompt="test", context={}, image_path=Path("image.png"))

    primary = AIProviderConfig(name="primary", provider_type="llm", base_url="https://primary.example/v1", model_name="one", api_key="key", priority=10, enabled=True)
    fallback = AIProviderConfig(name="fallback", provider_type="llm", base_url="https://fallback.example/v1", model_name="two", api_key="key", priority=20, enabled=True)
    calls: list[str] = []

    class InvalidRequestProvider:
        def __init__(self, config):
            self.config = config
            self.last_endpoint = config.base_url
            self.last_request_preview = None

        async def generate_structured(self, *, prompt, context):
            calls.append(self.config.name)
            raise RuntimeError("HTTP 400: invalid request")

        async def analyze_image(self, *, image_path, prompt, context):
            raise AssertionError("not used")

    with pytest.raises(RuntimeError, match="HTTP 400"):
        await ModelGateway(configurations=[primary, fallback], provider_factory=InvalidRequestProvider).generate_structured(purpose="llm", prompt="test", context={})  # type: ignore[arg-type]
    assert calls == ["primary"]
