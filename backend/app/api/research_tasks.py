from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.research_task import ResearchTaskRepository
from app.schemas.research_task import ResearchTaskCreate, ResearchTaskRead

router = APIRouter(prefix="/research/tasks", tags=["research-tasks"])


@router.post("", response_model=ResearchTaskRead, status_code=status.HTTP_201_CREATED)
def create_task(payload: ResearchTaskCreate, database: Session = Depends(get_db)) -> ResearchTaskRead:
    return ResearchTaskRepository(database).create(payload)


@router.get("", response_model=list[ResearchTaskRead])
def list_tasks(database: Session = Depends(get_db)) -> list[ResearchTaskRead]:
    return ResearchTaskRepository(database).list()


@router.get("/{task_id}", response_model=ResearchTaskRead)
def get_task(task_id: int, database: Session = Depends(get_db)) -> ResearchTaskRead:
    task = ResearchTaskRepository(database).get(task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research task not found")
    return task
