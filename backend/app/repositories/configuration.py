from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.configuration import AIProviderConfig, AppSetting, PlatformConfig, PromptTemplate, RankingConfig

ModelType = TypeVar("ModelType")


class NamedConfigRepository(Generic[ModelType]):
    def __init__(self, database: Session, model: type[ModelType]) -> None:
        self.database = database
        self.model = model

    def list(self) -> Sequence[ModelType]:
        return self.database.scalars(select(self.model).order_by(self.model.id)).all()  # type: ignore[attr-defined]

    def get(self, item_id: int) -> ModelType | None:
        return self.database.get(self.model, item_id)

    def create(self, values: dict[str, Any]) -> ModelType:
        item = self.model(**values)  # type: ignore[call-arg]
        self.database.add(item)
        self.database.commit()
        self.database.refresh(item)
        return item

    def update(self, item: ModelType, values: dict[str, Any]) -> ModelType:
        for key, value in values.items():
            setattr(item, key, value)
        self.database.commit()
        self.database.refresh(item)
        return item

    def delete(self, item: ModelType) -> None:
        self.database.delete(item)
        self.database.commit()


class AppSettingRepository:
    def __init__(self, database: Session) -> None:
        self.database = database

    def list(self) -> Sequence[AppSetting]:
        return self.database.scalars(select(AppSetting).order_by(AppSetting.key)).all()

    def upsert(self, key: str, values: dict[str, Any]) -> AppSetting:
        item = self.database.scalar(select(AppSetting).where(AppSetting.key == key))
        if item is None:
            item = AppSetting(key=key, **values)
            self.database.add(item)
        else:
            item.value = values["value"]
            item.description = values.get("description")
        self.database.commit()
        self.database.refresh(item)
        return item


def configuration_repositories(database: Session) -> dict[str, NamedConfigRepository[Any]]:
    return {
        "platforms": NamedConfigRepository(database, PlatformConfig),
        "ai-providers": NamedConfigRepository(database, AIProviderConfig),
        "prompt-templates": NamedConfigRepository(database, PromptTemplate),
        "ranking-configs": NamedConfigRepository(database, RankingConfig),
    }
