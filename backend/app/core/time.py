from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

SHANGHAI_TIME_ZONE = ZoneInfo("Asia/Shanghai")


def as_shanghai_time(value: datetime) -> datetime:
    """Return an aware Asia/Shanghai timestamp, treating legacy SQLite values as UTC."""
    aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value
    return aware.astimezone(SHANGHAI_TIME_ZONE)
