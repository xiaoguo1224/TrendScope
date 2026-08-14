from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.configuration import ensure_collection_defaults
from app.core.database import get_db
from app.core.config import get_settings
from app.models.configuration import PlatformConfig
from app.models.content import ContentItem
from app.models.research_task import ResearchTask, ResearchTaskStatus
from app.repositories.research_task import ResearchTaskRepository
from app.schemas.research_task import ContentItemRead, ResearchTaskCreate, ResearchTaskRead
from app.schemas.analysis import AnalysisItemRead, RankingsRead, TrendAnalysisRead
from app.schemas.reporting import CreativeConceptRead, ImagePromptRead, ReportRead
from app.services.analysis import AnalysisService
from app.services.collection import ContentCollectionService
from app.services.ranking import RankingService
from app.services.reporting import ReportingService

router = APIRouter(prefix="/research/tasks", tags=["research-tasks"])


@router.post("", response_model=ResearchTaskRead, status_code=status.HTTP_201_CREATED)
def create_task(payload: ResearchTaskCreate, database: Session = Depends(get_db)) -> ResearchTaskRead:
    ensure_collection_defaults(database)
    platform = database.query(PlatformConfig).filter(PlatformConfig.name == payload.platform).one_or_none()
    if platform is None or not platform.enabled:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Research task platform must be an enabled platform configuration")
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
    if result.status is not ResearchTaskStatus.FAILED:
        await ReportingService(database).report_for_task(result, regenerate=True)
    return _task_response(result, database)


@router.get("/{task_id}/contents", response_model=list[ContentItemRead])
def list_contents(task_id: int, database: Session = Depends(get_db)) -> list[ContentItemRead]:
    task = ResearchTaskRepository(database).get(task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research task not found")
    return list(database.query(ContentItem).filter(ContentItem.research_task_id == task_id).order_by(ContentItem.collected_at.desc()))


@router.get("/{task_id}/rankings", response_model=RankingsRead)
def get_rankings(task_id: int, database: Session = Depends(get_db)) -> RankingsRead:
    _get_task_or_404(task_id, database)
    return RankingService(database).rank_task(task_id)


@router.get("/{task_id}/analysis", response_model=list[AnalysisItemRead])
async def get_analysis(task_id: int, database: Session = Depends(get_db)) -> list[AnalysisItemRead]:
    task = _get_task_or_404(task_id, database)
    return await AnalysisService(database).analyze_task(task)


@router.get("/{task_id}/trends", response_model=TrendAnalysisRead)
async def get_trends(task_id: int, database: Session = Depends(get_db)) -> TrendAnalysisRead:
    task = _get_task_or_404(task_id, database)
    return await AnalysisService(database).trends_for_task(task)


@router.get("/{task_id}/concepts", response_model=list[CreativeConceptRead])
async def get_concepts(task_id: int, database: Session = Depends(get_db)) -> list[CreativeConceptRead]:
    return await ReportingService(database).concepts_for_task(_get_task_or_404(task_id, database))


@router.get("/{task_id}/prompts", response_model=list[ImagePromptRead])
async def get_prompts(task_id: int, database: Session = Depends(get_db)) -> list[ImagePromptRead]:
    return await ReportingService(database).prompts_for_task(_get_task_or_404(task_id, database))


@router.get("/{task_id}/report", response_model=ReportRead)
async def get_report(task_id: int, database: Session = Depends(get_db)) -> ReportRead:
    return await ReportingService(database).report_for_task(_get_task_or_404(task_id, database))


@router.get("/{task_id}/report/download")
async def download_report(
    task_id: int, file_format: Literal["markdown", "json", "prompts"] = "markdown", database: Session = Depends(get_db),
) -> FileResponse:
    report = await ReportingService(database).report_for_task(_get_task_or_404(task_id, database))
    files = {
        "markdown": (Path(report.report_path), "report.md", "text/markdown"),
        "json": (Path(report.report_path).with_name("report.json"), "report.json", "application/json"),
        "prompts": (Path(report.prompts_path), "prompts.md", "text/markdown"),
    }
    path, filename, media_type = files[file_format]
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report export file is unavailable")
    return FileResponse(path, media_type=media_type, filename=f"research-task-{task_id}-{filename}")


@router.get("/{task_id}/contents/{content_id}/media/{filename}")
def get_local_media(task_id: int, content_id: int, filename: str, database: Session = Depends(get_db)) -> FileResponse:
    content = database.query(ContentItem).filter(
        ContentItem.id == content_id, ContentItem.research_task_id == task_id,
    ).one_or_none()
    if content is None or Path(filename).name != filename:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Local media file not found")
    path = get_settings().data_dir / "tasks" / str(task_id) / "media" / str(content_id) / filename
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Local media file not found")
    return FileResponse(path)


def _get_task_or_404(task_id: int, database: Session) -> ResearchTask:
    task = ResearchTaskRepository(database).get(task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research task not found")
    return task


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
