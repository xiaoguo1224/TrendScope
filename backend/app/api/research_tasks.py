from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.content import ContentItem
from app.models.research_task import ResearchTask, ResearchTaskStatus
from app.repositories.research_task import ResearchTaskRepository
from app.schemas.research_task import ContentItemRead, ResearchTaskCreate, ResearchTaskRead
from app.services.collection import ContentCollectionService

router = APIRouter(prefix="/research/tasks", tags=["research-tasks"])


@router.post("", response_model=ResearchTaskRead, status_code=status.HTTP_201_CREATED)
def create_task(payload: ResearchTaskCreate, database: Session = Depends(get_db)) -> ResearchTaskRead:
    return _task_response(ResearchTaskRepository(database).create(payload), database)


@router.get("", response_model=list[ResearchTaskRead])
def list_tasks(database: Session = Depends(get_db)) -> list[ResearchTaskRead]:
    return [_task_response(task, database) for task in ResearchTaskRepository(database).list()]


@router.get("/{task_id}", response_model=ResearchTaskRead)
def get_task(task_id: int, database: Session = Depends(get_db)) -> ResearchTaskRead:
    task = ResearchTaskRepository(database).get(task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research task not found")
    return _task_response(task, database)


@router.post("/{task_id}/run", response_model=ResearchTaskRead)
async def run_task(task_id: int, database: Session = Depends(get_db)) -> ResearchTaskRead:
    task = ResearchTaskRepository(database).get(task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research task not found")
    result = await ContentCollectionService(database).run(task)
    return _task_response(result, database)


@router.get("/{task_id}/contents", response_model=list[ContentItemRead])
def list_contents(task_id: int, database: Session = Depends(get_db)) -> list[ContentItemRead]:
    task = ResearchTaskRepository(database).get(task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research task not found")
    return list(database.query(ContentItem).filter(ContentItem.research_task_id == task_id).order_by(ContentItem.collected_at.desc()))


def _task_response(task: ResearchTask, database: Session) -> ResearchTaskRead:
    collected_count = database.query(ContentItem).filter(ContentItem.research_task_id == task.id).count()
    stage = task.status.value
    progress = {
        ResearchTaskStatus.PENDING: 0,
        ResearchTaskStatus.EXPANDING_QUERY: 15,
        ResearchTaskStatus.COLLECTING: 50,
        ResearchTaskStatus.RANKING: 65,
        ResearchTaskStatus.ANALYZING: 80,
        ResearchTaskStatus.GENERATING_REPORT: 90,
        ResearchTaskStatus.COMPLETED: 100,
        ResearchTaskStatus.PARTIAL: 100,
        ResearchTaskStatus.FAILED: 100,
    }[task.status]
    return ResearchTaskRead.model_validate(task).model_copy(update={
        "current_stage": stage, "progress": progress, "collected_count": collected_count,
    })
