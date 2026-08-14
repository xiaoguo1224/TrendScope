from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from app.models.analysis import CreativeConceptRecord, ImagePromptRecord, ReportRecord
from app.models.configuration import PromptTemplate
from app.models.content import ContentItem
from app.models.research_task import ResearchTask
from app.schemas.analysis import TrendAnalysisRead
from app.services.reporting import ReportingService


def _task_with_evidence(session: Session) -> ResearchTask:
    task = ResearchTask(platform="generic-web", topic="portable coffee", keywords=["coffee", "travel"], time_range="7d", max_items=10)
    session.add(task)
    session.flush()
    session.add_all([
        ContentItem(research_task_id=task.id, platform=task.platform, external_id="first", url="https://example.test/first", title="Coffee kit", text="A useful travel coffee kit.", like_count=120, favorite_count=30, image_urls=[], local_image_paths=[], video_urls=[], collected_at=datetime.now(UTC)),
        ContentItem(research_task_id=task.id, platform=task.platform, external_id="second", url="https://example.test/second", title="Coffee guide", text="A compact guide for travelers.", like_count=90, comment_count=12, image_urls=[], local_image_paths=[], video_urls=[], collected_at=datetime.now(UTC)),
    ])
    session.commit()
    return task


@pytest.mark.anyio
async def test_report_exports_are_persistent_and_text_only(client, tmp_path: Path) -> None:
    from app.core.database import get_db
    session: Session = next(client.app.dependency_overrides[get_db]())
    task = _task_with_evidence(session)
    service = ReportingService(session, reports_dir=tmp_path / "reports")

    report = await service.report_for_task(task)

    export_dir = tmp_path / "reports" / str(task.id)
    assert (export_dir / "report.md").is_file()
    assert (export_dir / "report.json").is_file()
    assert (export_dir / "prompts.md").is_file()
    assert report.report_path == (export_dir / "report.md").as_posix()
    markdown = (export_dir / "report.md").read_text(encoding="utf-8")
    for heading in ("研究任务", "数据概览", "搜索关键词", "Hot", "Rising", "热门文章", "热门图片", "文案结构分析", "视觉结构分析", "爆款原因分析", "当前热门趋势", "近期上升趋势", "用户偏好", "可复用规律", "推荐创作方向", "Creative Concepts", "AI 图片 Prompt", "下一轮推荐关键词", "数据限制"):
        assert f"## {heading}" in markdown
    prompt_markdown = (export_dir / "prompts.md").read_text(encoding="utf-8")
    assert set(line[3:] for line in prompt_markdown.splitlines() if line.startswith("## ")) <= {"Concept", "Trend Basis", "Hero Prompt", "Detail Prompt", "Lifestyle Prompt", "Cover Prompt", "Negative Prompt"}
    assert session.query(CreativeConceptRecord).filter_by(research_task_id=task.id).count() == 10
    assert session.query(ImagePromptRecord).count() == 10
    assert session.query(ReportRecord).filter_by(research_task_id=task.id).one().content["research_task"]["topic"] == "portable coffee"
    assert not list(export_dir.rglob("*.png"))
    assert not list(export_dir.rglob("*.jpg"))
    assert "image generation" not in report.markdown.lower()
    assert {path.name for path in export_dir.iterdir()} == {"report.md", "report.json", "prompts.md"}


def test_reporting_apis_return_persisted_outputs_and_honor_sqlite_defaults(client, tmp_path: Path, monkeypatch) -> None:
    from app.core.database import get_db
    import app.services.reporting as reporting_module
    import app.api.research_tasks as research_tasks_module

    monkeypatch.setattr(reporting_module, "get_settings", lambda: SimpleNamespace(reports_dir=tmp_path / "reports"))
    monkeypatch.setattr(research_tasks_module, "get_settings", lambda: SimpleNamespace(data_dir=tmp_path / "data"))
    session: Session = next(client.app.dependency_overrides[get_db]())
    task = _task_with_evidence(session)
    setting = client.put("/api/v1/config/settings/report_defaults", json={
        "value": {"concept_count": 2, "prompt_language": "English", "prompt_style": "documentary", "include_markdown": True},
        "description": "test report defaults",
    })
    assert setting.status_code == 200

    concepts = client.get(f"/api/v1/research/tasks/{task.id}/concepts")
    prompts = client.get(f"/api/v1/research/tasks/{task.id}/prompts")
    report = client.get(f"/api/v1/research/tasks/{task.id}/report")

    assert concepts.status_code == prompts.status_code == report.status_code == 200
    assert len(concepts.json()) == len(prompts.json()) == 2
    assert prompts.json()[0]["output_style"] == "documentary"
    assert prompts.json()[0]["trend_basis"]
    assert report.json()["content"]["data_limitations"]
    assert (tmp_path / "reports" / str(task.id) / "report.json").is_file()
    markdown_download = client.get(f"/api/v1/research/tasks/{task.id}/report/download?file_format=markdown")
    json_download = client.get(f"/api/v1/research/tasks/{task.id}/report/download?file_format=json")
    prompts_download = client.get(f"/api/v1/research/tasks/{task.id}/report/download?file_format=prompts")
    assert markdown_download.status_code == json_download.status_code == prompts_download.status_code == 200
    assert markdown_download.headers["content-disposition"].endswith(f'"research-task-{task.id}-report.md"')
    assert json_download.json()["research_task"]["topic"] == "portable coffee"
    first_item = session.query(ContentItem).filter_by(research_task_id=task.id).first()
    assert first_item is not None
    media_path = tmp_path / "data" / "tasks" / str(task.id) / "media" / str(first_item.id) / "image-1.jpg"
    media_path.parent.mkdir(parents=True)
    media_path.write_bytes(b"public-image")
    media = client.get(f"/api/v1/research/tasks/{task.id}/contents/{first_item.id}/media/image-1.jpg")
    assert media.status_code == 200
    assert media.content == b"public-image"


def test_prompt_composition_uses_templates_and_visual_domain_evidence(client, tmp_path: Path) -> None:
    from app.core.database import get_db

    session: Session = next(client.app.dependency_overrides[get_db]())
    task = _task_with_evidence(session)
    session.add_all([
        PromptTemplate(name="custom-concept", purpose="creative_concept", template="CONCEPT_GUIDANCE {topic} {trend_basis}", enabled=True),
        PromptTemplate(name="custom-prompt", purpose="image_prompt", template="PROMPT_GUIDANCE {concept_name} {visual_context} {domain_attributes}", enabled=True),
    ])
    session.commit()
    service = ReportingService(session, reports_dir=tmp_path / "reports")
    trends = TrendAnalysisRead(
        task_id=task.id, insufficient_data=False, analyzed_content_count=2, hot_topics=["travel coffee"],
        visual_patterns=["warm close-up"], domain_patterns=["brew_method=pour-over"],
    )
    concept = service._create_concepts(task, trends)[0]
    evidence = service._visual_evidence([], trends)
    prompt = service._create_prompt(task, concept, {"prompt_language": "English", "prompt_style": "editorial"}, evidence)

    assert "CONCEPT_GUIDANCE portable coffee" in concept.concept
    assert "PROMPT_GUIDANCE" in prompt.hero_prompt
    assert "warm close-up" in prompt.hero_prompt
    assert "brew_method=pour-over" in prompt.hero_prompt
