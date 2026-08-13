from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.configuration import AppSettingRepository, configuration_repositories
from app.schemas.configuration import (
    AIProviderConfigCreate, AIProviderConfigRead, AppSettingRead, AppSettingUpsert,
    PlatformConfigCreate, PlatformConfigRead, PromptTemplateCreate, PromptTemplateRead,
    RankingConfigCreate, RankingConfigRead,
)

router = APIRouter(prefix="/config", tags=["configuration"])

DEFAULT_SETTINGS: dict[str, tuple[object, str]] = {
    "collection_defaults": ({"max_items": 50, "time_range": "7d", "request_interval_ms": 1200, "scroll_interval_ms": 1000}, "Default collection parameters"),
    "browser_defaults": ({"headless": True, "timeout_seconds": 30, "download_images": True}, "Default browser parameters"),
}
DEFAULT_GENERIC_WEB_PLATFORM = {
    "name": "generic-web",
    "search_url_template": "https://www.bing.com/search?q={query}",
    "selectors": {"item": "li.b_algo", "field_title": "h2", "field_url": "h2 a", "field_text": "p"},
    "parser_rules": {"scroll_count": 2, "access_block_indicators": ["captcha", "verify you are human", "access denied"]},
    "enabled": True,
}
DEFAULT_PROMPTS: tuple[dict[str, object], ...] = (
    {"name": "query-expansion-default", "purpose": "query_expansion", "template": "Expand public content research keywords for {topic} on {platform}; retain all user keywords and add concise related terms. Research goals: {research_goals}.", "enabled": True},
    {"name": "text-analysis-default", "purpose": "text_analysis", "template": "Analyze the content structure for {topic}. Identify reusable patterns; do not reproduce the source text.", "enabled": True},
    {"name": "visual-analysis-default", "purpose": "visual_analysis", "template": "Analyze the local image using the specified generic visual fields. Put only industry-specific observations in domain_attributes.", "enabled": True},
    {"name": "trend-analysis-default", "purpose": "trend_analysis", "template": "Aggregate patterns across multiple contents for {topic}; clearly state limitations when the sample is insufficient.", "enabled": True},
)
DEFAULT_RANKING = {"name": "default", "enabled": True, "like_weight": 1.0, "favorite_weight": 1.2, "comment_weight": 1.5, "share_weight": 1.5, "view_weight": 0.1, "freshness_half_life_hours": 72, "growth_window_hours": 24}


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuration item not found")


@router.get("/settings", response_model=list[AppSettingRead])
def list_settings(database: Session = Depends(get_db)) -> list[AppSettingRead]:
    ensure_collection_defaults(database)
    repository = AppSettingRepository(database)
    return list(repository.list())


def ensure_collection_defaults(database: Session) -> None:
    settings = AppSettingRepository(database)
    existing_settings = {item.key for item in settings.list()}
    for key, (value, description) in DEFAULT_SETTINGS.items():
        if key not in existing_settings:
            settings.upsert(key, {"value": value, "description": description})
    platforms = configuration_repositories(database)["platforms"]
    if not any(item.name == "generic-web" for item in platforms.list()):
        platforms.create(DEFAULT_GENERIC_WEB_PLATFORM)


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
    return AppSettingRepository(database).upsert(key, payload.model_dump())


@router.post("/settings/reset-defaults", response_model=list[AppSettingRead])
def reset_settings(database: Session = Depends(get_db)) -> list[AppSettingRead]:
    repository = AppSettingRepository(database)
    for key, (value, description) in DEFAULT_SETTINGS.items():
        repository.upsert(key, {"value": value, "description": description})
    return list(repository.list())


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


@router.post("/ranking-configs/reset-default", response_model=RankingConfigRead)
def reset_ranking_default(database: Session = Depends(get_db)) -> RankingConfigRead:
    repository = configuration_repositories(database)["ranking-configs"]
    default = next((item for item in repository.list() if item.name == "default"), None)
    return repository.update(default, DEFAULT_RANKING) if default else repository.create(DEFAULT_RANKING)
