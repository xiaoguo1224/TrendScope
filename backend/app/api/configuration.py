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
DEFAULT_RANKING = {"name": "default", "enabled": True, "like_weight": 1.0, "favorite_weight": 1.2, "comment_weight": 1.5, "share_weight": 1.5, "view_weight": 0.1, "freshness_half_life_hours": 72, "growth_window_hours": 24}


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuration item not found")


@router.get("/settings", response_model=list[AppSettingRead])
def list_settings(database: Session = Depends(get_db)) -> list[AppSettingRead]:
    repository = AppSettingRepository(database)
    for key, (value, description) in DEFAULT_SETTINGS.items():
        repository.upsert(key, {"value": value, "description": description}) if not any(item.key == key for item in repository.list()) else None
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
