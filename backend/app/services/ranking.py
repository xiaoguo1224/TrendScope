from __future__ import annotations

import math
from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.configuration import ensure_analysis_defaults
from app.models.configuration import RankingConfig
from app.models.content import ContentItem, ContentMetricSnapshot
from app.schemas.analysis import MetricVelocity, RankedContentItem, RankingBoard, RankingsRead

METRIC_WEIGHTS = {
    "like_count": "like_weight", "favorite_count": "favorite_weight", "comment_count": "comment_weight",
    "share_count": "share_weight", "view_count": "view_weight",
}
METRIC_LABELS = {
    "favorite_count": "Most Saved", "comment_count": "Most Discussed", "share_count": "Most Shared",
    "view_count": "Most Viewed",
}


class RankingService:
    def __init__(self, database: Session) -> None:
        self.database = database

    def rank_task(self, task_id: int) -> RankingsRead:
        ensure_analysis_defaults(self.database)
        config = self.database.scalar(select(RankingConfig).where(RankingConfig.enabled.is_(True)).order_by(RankingConfig.id))
        if config is None:  # Defensive: defaults are seeded above, but a disabled configuration remains valid.
            config = self.database.scalar(select(RankingConfig).order_by(RankingConfig.id))
        if config is None:
            raise RuntimeError("No ranking configuration is available")
        contents = self.database.scalars(
            select(ContentItem).where(ContentItem.research_task_id == task_id)
            .options(selectinload(ContentItem.metric_snapshots))
        ).all()
        ranked = [self._score(content, config) for content in contents]
        boards = [RankingBoard(name="Hot", items=sorted(ranked, key=lambda item: item.hot_score, reverse=True))]
        rising = [item for item in ranked if item.growth_score is not None]
        if rising:
            boards.append(RankingBoard(name="Rising", items=sorted(rising, key=lambda item: item.growth_score or 0, reverse=True)))
        for metric, label in METRIC_LABELS.items():
            matching = [item for item in ranked if metric in item.metrics]
            if matching:
                boards.append(RankingBoard(name=label, metric=metric, items=sorted(matching, key=lambda item: item.metrics[metric], reverse=True)))
        return RankingsRead(task_id=task_id, config_name=config.name, boards=boards)

    def _score(self, content: ContentItem, config: RankingConfig) -> RankedContentItem:
        metrics = {metric: int(value) for metric in METRIC_WEIGHTS if (value := getattr(content, metric)) is not None}
        weighted_logs = [(math.log1p(value), float(getattr(config, METRIC_WEIGHTS[metric]))) for metric, value in metrics.items()]
        total_weight = sum(weight for _, weight in weighted_logs)
        engagement = sum(value * weight for value, weight in weighted_logs) / total_weight if total_weight else 0.0
        reference_time = content.published_at or content.collected_at
        age_hours = max(0.0, (_utc_now() - _as_utc(reference_time)).total_seconds() / 3600)
        freshness = math.exp(-math.log(2) * age_hours / config.freshness_half_life_hours)
        velocities = self._velocities(content.metric_snapshots, config.growth_window_hours)
        growth_components = [
            (math.log1p(max(0.0, velocity.value_per_hour or 0.0)), float(getattr(config, METRIC_WEIGHTS[metric])))
            for metric, velocity in velocities.items() if velocity.value_per_hour is not None
        ]
        growth_weight = sum(weight for _, weight in growth_components)
        growth = sum(value * weight for value, weight in growth_components) / growth_weight if growth_weight else None
        hot = engagement * freshness + (growth or 0.0)
        return RankedContentItem(
            content_item_id=content.id, title=content.title, url=content.url, metrics=metrics,
            metric_velocities=velocities, engagement_score=round(engagement, 6),
            freshness_score=round(freshness, 6), growth_score=round(growth, 6) if growth is not None else None,
            hot_score=round(hot, 6),
        )

    @staticmethod
    def _velocities(snapshots: Iterable[ContentMetricSnapshot], window_hours: int) -> dict[str, MetricVelocity]:
        ordered = sorted(snapshots, key=lambda snapshot: _as_utc(snapshot.captured_at))
        if len(ordered) < 2:
            return {metric: MetricVelocity() for metric in METRIC_WEIGHTS}
        end = ordered[-1]
        end_time = _as_utc(end.captured_at)
        candidates = [snapshot for snapshot in ordered[:-1] if (end_time - _as_utc(snapshot.captured_at)).total_seconds() <= window_hours * 3600]
        start = candidates[0] if candidates else ordered[0]
        hours = (end_time - _as_utc(start.captured_at)).total_seconds() / 3600
        if hours <= 0:
            return {metric: MetricVelocity() for metric in METRIC_WEIGHTS}
        result: dict[str, MetricVelocity] = {}
        for metric in METRIC_WEIGHTS:
            before, after = getattr(start, metric), getattr(end, metric)
            result[metric] = MetricVelocity(
                value_per_hour=(float(after - before) / hours if before is not None and after is not None else None),
                start_at=start.captured_at, end_at=end.captured_at,
            )
        return result


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
