from __future__ import annotations

import re
from urllib.parse import urlparse
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Response, status
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.configuration import AppSettingRepository, configuration_repositories
from app.schemas.configuration import (
    AIProviderConfigCreate, AIProviderConfigRead, AIProviderConfigTestRead, AppSettingRead, AppSettingUpsert,
    BrowserConnectionTestRead, PlatformConfigCreate, PlatformConfigRead, PlatformConfigTestRead, PlatformConfigTestRequest, PromptTemplateCreate, PromptTemplateRead,
    RankingConfigCreate, RankingConfigRead,
)

router = APIRouter(prefix="/config", tags=["configuration"])

DEFAULT_SETTINGS: dict[str, tuple[object, str]] = {
    "collection_defaults": ({"max_items": 50, "time_range": "7d", "request_interval_ms": 1200, "scroll_interval_ms": 1000}, "Default collection parameters"),
    "browser_defaults": ({"mode": "isolated", "cdp_endpoint": "http://127.0.0.1:9222", "headless": True, "timeout_seconds": 30, "download_images": True, "headers": {}}, "Default browser parameters"),
    "report_defaults": ({"concept_count": 10, "prompt_language": "English", "prompt_style": "editorial lifestyle photography", "include_markdown": True}, "Creative concept, image prompt, and report defaults"),
}
DEFAULT_GENERIC_WEB_PLATFORM = {
    "name": "generic-web",
    "search_url_template": "https://www.bing.com/search?q={query}",
    "selectors": {"item": "li.b_algo", "field_title": "h2", "field_url": "h2 a", "field_text": "p"},
    "parser_rules": {"scroll_count": 0, "access_block_indicators": ["captcha", "verify you are human", "access denied"]},
    "enabled": True,
}
DEFAULT_XIAOHONGSHU_PLATFORM = {
    "name": "xiaohongshu",
    "search_url_template": "https://www.xiaohongshu.com/search_result?keyword={query}&source=web_search_result_notes",
    "selectors": {
        "search": {
            "result_container": "section.note-item", "content_link": "a[href*='/explore/']", "cover": ".cover img",
            "title": ".title", "author": ".author .name", "publish_time": ".author .time", "like_count": ".like-wrapper .count",
        },
        "detail": {
            "title": "#detail-title, .title", "content": "#detail-desc, .desc", "image": ".note-slider-img, .swiper-slide img",
            "author": ".author-wrapper .username, .username", "like_count": ".like-wrapper .count",
            "collect_count": ".collect-wrapper .count", "comment_count": ".chat-wrapper .count",
        },
    },
    "parser_rules": {
        "content_id": {"source": "url", "pattern": "/explore/([^/?]+)"},
        "url": {"source": "content_link", "type": "href", "absolute": True},
        "cover_url": {"source": "cover", "type": "src"},
        "title": {"source": "title", "type": "text", "trim": True},
        "author_name": {"source": "author", "type": "text", "trim": True},
        "published_at": {"source": "publish_time", "type": "xiaohongshu_time", "optional": True},
        "like_count": {"source": "like_count", "type": "compact_number", "optional": True},
        "collect_count": {"source": "collect_count", "type": "compact_number", "optional": True},
        "comment_count": {"source": "comment_count", "type": "compact_number", "optional": True},
        "images": {"source": "image", "type": "src_list", "deduplicate": True},
        "text": {"source": "content", "type": "text", "trim": True, "optional": True},
        "result_wait_ms": 2500,
        "access_block_indicators": ["captcha", "verify you are human", "access denied", "登录后", "请登录"],
    },
    "enabled": True,
}
DEFAULT_PROMPTS: tuple[dict[str, object], ...] = (
    {"name": "query-expansion-default", "purpose": "query_expansion", "template": "Expand public content research keywords for {topic} on {platform}; retain all user keywords and add concise related terms. Research goals: {research_goals}.", "enabled": True},
    {"name": "text-analysis-default", "purpose": "text_analysis", "template": "Analyze the content structure for {topic}. Identify reusable patterns; do not reproduce the source text.", "enabled": True},
    {"name": "visual-analysis-default", "purpose": "visual_analysis", "template": "Analyze the local image using the specified generic visual fields. Put only industry-specific observations in domain_attributes.", "enabled": True},
    {"name": "trend-analysis-default", "purpose": "trend_analysis", "template": "Aggregate patterns across multiple contents for {topic}; clearly state limitations when the sample is insufficient.", "enabled": True},
    {"name": "creative-concept-default", "purpose": "creative_concept", "template": "Synthesize distinct, original creative directions for {topic} from this aggregated trend evidence: {trend_basis}. Do not reproduce one source item.", "enabled": True},
    {"name": "image-prompt-default", "purpose": "image_prompt", "template": "Write safe, generic, text-only image prompts for {topic}. Concept: {concept_name}. Visual evidence: {visual_context}. Domain attributes: {domain_attributes}. Trend basis: {trend_basis}. Do not call a rendering service.", "enabled": True},
    {"name": "report-default", "purpose": "report", "template": "Produce a source-grounded trend research report for {topic}; distinguish observed facts, AI inference, and limitations.", "enabled": True},
)
DEFAULT_RANKING = {"name": "default", "enabled": True, "like_weight": 1.0, "favorite_weight": 1.2, "comment_weight": 1.5, "share_weight": 1.5, "view_weight": 0.1, "freshness_half_life_hours": 72, "growth_window_hours": 24}


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuration item not found")


_HEADER_NAME = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")


def _validate_browser_headers(headers: object) -> None:
    """Reject malformed header input before it reaches the browser context."""
    if headers is None:
        return
    if not isinstance(headers, dict):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Browser headers must be a JSON object")
    for name, value in headers.items():
        if not isinstance(name, str) or not _HEADER_NAME.fullmatch(name):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Browser header name is invalid")
        if not isinstance(value, str) or "\r" in value or "\n" in value:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Browser header value is invalid")


def _validate_browser_connection(value: dict[str, object]) -> None:
    mode = value.get("mode", "isolated")
    if mode not in {"isolated", "system_cdp"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Browser mode must be isolated or system_cdp")
    if mode != "system_cdp":
        return
    endpoint = value.get("cdp_endpoint")
    if not isinstance(endpoint, str) or not endpoint.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="A local CDP endpoint is required when using the system browser")
    parsed = urlparse(endpoint.strip())
    try:
        port = parsed.port
    except ValueError:
        port = None
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.username or parsed.password or not port:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="The system browser CDP endpoint must use localhost and an explicit port")


def _mask_secret(value: str) -> str:
    return "*" * max(0, len(value) - 4) + value[-4:]


def _setting_read(item: Any) -> AppSettingRead:
    value = item.value
    if item.key == "browser_defaults" and isinstance(value, dict):
        value = dict(value)
        headers = value.get("headers")
        if isinstance(headers, dict):
            value["headers"] = {str(name): _mask_secret(header_value) for name, header_value in headers.items() if isinstance(header_value, str)}
    return AppSettingRead.model_validate({"key": item.key, "value": value, "description": item.description, "updated_at": item.updated_at})


def _preserve_masked_browser_headers(database: Session, incoming: dict[str, object]) -> dict[str, object]:
    headers = incoming.get("headers")
    if not isinstance(headers, dict):
        return incoming
    existing = AppSettingRepository(database).get_by_key("browser_defaults")
    existing_value = existing.value if existing and isinstance(existing.value, dict) else {}
    existing_headers = existing_value.get("headers") if isinstance(existing_value.get("headers"), dict) else {}
    incoming["headers"] = {
        name: existing_headers[name] if isinstance(value, str) and isinstance(existing_headers.get(name), str) and value == _mask_secret(existing_headers[name]) else value
        for name, value in headers.items()
    }
    return incoming


@router.get("/settings", response_model=list[AppSettingRead])
def list_settings(database: Session = Depends(get_db)) -> list[AppSettingRead]:
    ensure_collection_defaults(database)
    repository = AppSettingRepository(database)
    return [_setting_read(item) for item in repository.list()]


def ensure_collection_defaults(database: Session) -> None:
    settings = AppSettingRepository(database)
    existing_settings = {item.key for item in settings.list()}
    for key, (value, description) in DEFAULT_SETTINGS.items():
        if key not in existing_settings:
            settings.upsert(key, {"value": value, "description": description})
    platforms = configuration_repositories(database)["platforms"]
    existing_platforms = {item.name for item in platforms.list()}
    for platform in (DEFAULT_GENERIC_WEB_PLATFORM, DEFAULT_XIAOHONGSHU_PLATFORM):
        if str(platform["name"]) not in existing_platforms:
            platforms.create(platform)
    xiaohongshu = next((item for item in platforms.list() if item.name == "xiaohongshu"), None)
    if xiaohongshu is not None and "result_wait_ms" not in xiaohongshu.parser_rules:
        xiaohongshu.parser_rules = {**xiaohongshu.parser_rules, "result_wait_ms": 2500}
        database.commit()


def ensure_analysis_defaults(database: Session) -> None:
    """Seed editable analysis defaults once; runtime behavior always reads SQLite."""
    ensure_collection_defaults(database)
    repositories = configuration_repositories(database)
    prompts = repositories["prompt-templates"]
    existing_prompts = {item.name for item in prompts.list()}
    for default in DEFAULT_PROMPTS:
        if str(default["name"]) not in existing_prompts:
            prompts.create(default)
    ranking = repositories["ranking-configs"]
    if not any(item.name == "default" for item in ranking.list()):
        ranking.create(DEFAULT_RANKING)


@router.post("/prompt-templates/reset-defaults", response_model=list[PromptTemplateRead])
def reset_prompt_defaults(database: Session = Depends(get_db)) -> list[PromptTemplateRead]:
    repository = configuration_repositories(database)["prompt-templates"]
    existing = {item.name: item for item in repository.list()}
    for default in DEFAULT_PROMPTS:
        item = existing.get(str(default["name"]))
        if item is None:
            repository.create(default)
        else:
            repository.update(item, default)
    return list(repository.list())


@router.put("/settings/{key}", response_model=AppSettingRead)
def update_setting(key: str, payload: AppSettingUpsert, database: Session = Depends(get_db)) -> AppSettingRead:
    value = payload.value
    if key == "browser_defaults":
        if not isinstance(value, dict):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Browser defaults must be a JSON object")
        value = _preserve_masked_browser_headers(database, dict(value))
        _validate_browser_headers(value.get("headers"))
        _validate_browser_connection(value)
    saved = AppSettingRepository(database).upsert(key, {**payload.model_dump(), "value": value})
    return _setting_read(saved)


@router.post("/settings/reset-defaults", response_model=list[AppSettingRead])
def reset_settings(database: Session = Depends(get_db)) -> list[AppSettingRead]:
    repository = AppSettingRepository(database)
    for key, (value, description) in DEFAULT_SETTINGS.items():
        repository.upsert(key, {"value": value, "description": description})
    return [_setting_read(item) for item in repository.list()]


def _crud_routes(
    path: str, create_schema: type[Any], read_schema: type[Any], repository_key: str,
) -> None:
    @router.get(path, response_model=list[read_schema])
    def list_items(database: Session = Depends(get_db)) -> list[Any]:
        ensure_analysis_defaults(database)
        return list(configuration_repositories(database)[repository_key].list())

    @router.post(path, response_model=read_schema, status_code=status.HTTP_201_CREATED)
    def create_item(payload: dict[str, Any] = Body(...), database: Session = Depends(get_db)) -> Any:
        try:
            validated = create_schema.model_validate(payload)
            return configuration_repositories(database)[repository_key].create(validated.model_dump())
        except ValidationError as error:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=error.errors()) from error
        except IntegrityError as error:
            database.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Configuration name already exists") from error

    @router.put(f"{path}/{{item_id}}", response_model=read_schema)
    def update_item(item_id: int, payload: dict[str, Any] = Body(...), database: Session = Depends(get_db)) -> Any:
        repository = configuration_repositories(database)[repository_key]
        item = repository.get(item_id)
        if item is None:
            raise _not_found()
        try:
            validated = create_schema.model_validate(payload)
            values = validated.model_dump()
            if repository_key == "ai-providers" and not values.get("api_key"):
                values.pop("api_key")
            return repository.update(item, values)
        except ValidationError as error:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=error.errors()) from error
        except IntegrityError as error:
            database.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Configuration name already exists") from error

    @router.delete(f"{path}/{{item_id}}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_item(item_id: int, database: Session = Depends(get_db)) -> Response:
        repository = configuration_repositories(database)[repository_key]
        item = repository.get(item_id)
        if item is None:
            raise _not_found()
        repository.delete(item)
        return Response(status_code=status.HTTP_204_NO_CONTENT)


_crud_routes("/platforms", PlatformConfigCreate, PlatformConfigRead, "platforms")
_crud_routes("/ai-providers", AIProviderConfigCreate, AIProviderConfigRead, "ai-providers")
_crud_routes("/prompt-templates", PromptTemplateCreate, PromptTemplateRead, "prompt-templates")
_crud_routes("/ranking-configs", RankingConfigCreate, RankingConfigRead, "ranking-configs")


@router.post("/platforms/{item_id}/test", response_model=PlatformConfigTestRead)
async def test_platform_configuration(
    item_id: int, payload: PlatformConfigTestRequest, database: Session = Depends(get_db),
) -> PlatformConfigTestRead:
    from app.services.platform_configuration_test import PlatformConfigurationTestService

    platform = configuration_repositories(database)["platforms"].get(item_id)
    if platform is None:
        raise _not_found()
    return await PlatformConfigurationTestService(database).run(platform, query=payload.query, limit=payload.limit)


@router.post("/ai-providers/{item_id}/test", response_model=AIProviderConfigTestRead)
async def test_ai_provider_configuration(item_id: int, database: Session = Depends(get_db)) -> AIProviderConfigTestRead:
    from app.services.provider_configuration_test import ProviderConfigurationTestService

    provider = configuration_repositories(database)["ai-providers"].get(item_id)
    if provider is None:
        raise _not_found()
    return await ProviderConfigurationTestService().run(provider)


@router.post("/browser/test-connection", response_model=BrowserConnectionTestRead)
async def test_system_browser_connection(database: Session = Depends(get_db)) -> BrowserConnectionTestRead:
    from app.services.browser_connection_test import BrowserConnectionTestService

    return await BrowserConnectionTestService(database).run()


@router.post("/ranking-configs/reset-default", response_model=RankingConfigRead)
def reset_ranking_default(database: Session = Depends(get_db)) -> RankingConfigRead:
    repository = configuration_repositories(database)["ranking-configs"]
    default = next((item for item in repository.list() if item.name == "default"), None)
    return repository.update(default, DEFAULT_RANKING) if default else repository.create(DEFAULT_RANKING)
