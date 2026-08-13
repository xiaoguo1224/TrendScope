from __future__ import annotations

from typing import Any


class MockPlatformAdapter:
    def __init__(self, results: list[dict[str, Any]] | None = None) -> None:
        self.results = results or []
        self.opened_url: str | None = None

    async def search(self, query: str, limit: int) -> list[dict[str, Any]]:
        return self.results[:limit]

    async def open_content(self, url: str) -> None:
        self.opened_url = url

    async def extract_content(self) -> dict[str, Any]:
        return self.results[0] if self.results else {}

    async def download_media(self, content: dict[str, Any]) -> list[bytes]:
        return []
