from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.research_task import ResearchTask
from app.schemas.research_task import ResearchTaskCreate


class ResearchTaskRepository:
    def __init__(self, database: Session) -> None:
        self.database = database

    def create(self, payload: ResearchTaskCreate) -> ResearchTask:
        task = ResearchTask(**payload.model_dump())
        self.database.add(task)
        self.database.commit()
        self.database.refresh(task)
        return task

    def list(self) -> list[ResearchTask]:
        return list(self.database.scalars(select(ResearchTask).order_by(ResearchTask.created_at.desc())))

    def get(self, task_id: int) -> ResearchTask | None:
        return self.database.get(ResearchTask, task_id)
