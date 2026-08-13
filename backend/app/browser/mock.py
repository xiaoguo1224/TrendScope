from __future__ import annotations

from typing import Any


class MockBrowserAdapter:
    def __init__(self, visible_content: list[dict[str, Any]] | None = None) -> None:
        self.current_url: str | None = None
        self.visible_content = visible_content or []
        self.blocked = False

    async def open(self, url: str) -> None:
        self.current_url = url

    async def scroll(self, amount: int) -> None:
        return None

    async def extract_visible_content(
        self, item_selector: str | None = None, field_selectors: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        return self.visible_content

    async def screenshot(self) -> bytes:
        return b"mock-screenshot"

    async def download_media(self, url: str) -> bytes:
        return b"mock-media"

    async def is_access_blocked(self, indicators: list[str]) -> bool:
        return self.blocked

    async def close(self) -> None:
        return None
