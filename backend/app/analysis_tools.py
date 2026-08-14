from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.content import ContentItem
from app.models.research_task import ResearchTask
from app.services.ranking import RankingService


class TaskAnalysisToolRegistry:
    """Read-only, task-scoped evidence tools available to the analysis agent."""

    MAX_TEXT_LENGTH = 1600
    MAX_RESULTS = 12

    def __init__(self, database: Session, task: ResearchTask) -> None:
        self.database = database
        self.task = task

    @staticmethod
    def definitions() -> list[dict[str, Any]]:
        return [
            {"name": "get_ranked_contents", "description": "Read representative content summaries from a ranking board.", "arguments": {"board": "Hot|Rising", "limit": "1-12"}},
            {"name": "get_content_detail", "description": "Read title, text, public metrics and media references for one content item in this task.", "arguments": {"content_item_id": "integer"}},
            {"name": "get_image_evidence", "description": "List locally available images for representative content. Select at most one image for visual evidence.", "arguments": {"content_item_id": "integer"}},
            {"name": "get_task_constraints", "description": "Read the task topic, platform, user keywords, time range and goals.", "arguments": {}},
        ]

    def execute(self, name: str, arguments: object) -> dict[str, Any]:
        args = arguments if isinstance(arguments, dict) else {}
        if name == "get_ranked_contents":
            return self._ranked_contents(str(args.get("board", "Hot")), int(args.get("limit", 8)))
        if name == "get_content_detail":
            return self._content_detail(self._content_id(args))
        if name == "get_image_evidence":
            return self._image_evidence(self._content_id(args))
        if name == "get_task_constraints":
            return self._task_constraints()
        raise ValueError(f"Unsupported analysis tool '{name}'")

    def _task_constraints(self) -> dict[str, Any]:
        return {
            "task_id": self.task.id, "platform": self.task.platform, "topic": self.task.topic,
            "keywords": self.task.keywords, "time_range": self.task.time_range,
            "research_goals": self.task.research_goals or "",
        }

    def _ranked_contents(self, board_name: str, limit: int) -> dict[str, Any]:
        board = next((board for board in RankingService(self.database).rank_task(self.task.id).boards if board.name.casefold() == board_name.casefold()), None)
        if board is None:
            return {"board": board_name, "items": [], "message": "The requested board is unavailable for the collected metrics."}
        content_by_id = {item.id: item for item in self.database.scalars(select(ContentItem).where(ContentItem.research_task_id == self.task.id))}
        values = []
        for ranked in board.items[:max(1, min(limit, self.MAX_RESULTS))]:
            content = content_by_id.get(ranked.content_item_id)
            if content is not None:
                values.append(self._content_summary(content, ranking=ranked.model_dump(mode="json")))
        return {"board": board.name, "items": values}

    def _content_detail(self, content_id: int) -> dict[str, Any]:
        content = self._content(content_id)
        return self._content_summary(content, include_text=True)

    def _image_evidence(self, content_id: int) -> dict[str, Any]:
        content = self._content(content_id)
        paths = [path for path in content.local_image_paths or [] if Path(path).is_file()]
        return {"content_item_id": content.id, "title": content.title, "available_images": paths[:4], "image_count": len(paths)}

    def _content(self, content_id: int) -> ContentItem:
        content = self.database.scalar(select(ContentItem).where(ContentItem.id == content_id, ContentItem.research_task_id == self.task.id))
        if content is None:
            raise ValueError("The requested content item is not part of this research task")
        return content

    @staticmethod
    def _content_id(arguments: dict[str, Any]) -> int:
        value = arguments.get("content_item_id")
        if not isinstance(value, int) or value <= 0:
            raise ValueError("content_item_id must be a positive integer")
        return value

    def _content_summary(self, content: ContentItem, *, ranking: dict[str, Any] | None = None, include_text: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "content_item_id": content.id, "title": content.title, "author_name": content.author_name,
            "published_at": content.published_at, "metrics": {
                name: getattr(content, name) for name in ("like_count", "favorite_count", "comment_count", "share_count", "view_count")
                if getattr(content, name) is not None
            },
            "has_local_images": any(Path(path).is_file() for path in content.local_image_paths or []),
        }
        if include_text:
            payload["text"] = (content.text or "")[:self.MAX_TEXT_LENGTH]
        if ranking is not None:
            payload["ranking"] = ranking
        return payload
