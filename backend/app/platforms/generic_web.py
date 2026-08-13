from __future__ import annotations

import hashlib
import asyncio
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote_plus, urlparse

from app.browser.adapter import BrowserAdapter
from app.models.configuration import PlatformConfig


class PublicAccessBlockedError(RuntimeError):
    """Raised when a configured public page signals login, verification, or access denial."""


class GenericWebPlatformAdapter:
    """Config-driven adapter for ordinary, publicly accessible search-result pages."""

    def __init__(self, config: PlatformConfig, browser: BrowserAdapter) -> None:
        self.config = config
        self.browser = browser
        self._current_result: dict[str, Any] | None = None

    async def search(self, query: str, limit: int) -> list[dict[str, Any]]:
        if not self.config.enabled:
            raise ValueError(f"Platform '{self.config.name}' is disabled")
        if not self.config.search_url_template:
            raise ValueError(f"Platform '{self.config.name}' has no search URL template")
        url = self.config.search_url_template.format(query=quote_plus(query), limit=limit)
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Platform search URL must be a public HTTP(S) URL")
        await self.browser.open(url)
        indicators = [str(value) for value in self.config.parser_rules.get(
            "access_block_indicators", ["captcha", "verify", "sign in", "log in", "access denied"],
        )]
        if await self.browser.is_access_blocked(indicators):
            raise PublicAccessBlockedError("Public access was blocked by a login, verification, or permission requirement")
        scroll_count = int(self.config.parser_rules.get("scroll_count", 0))
        scroll_amount = int(self.config.parser_rules.get("scroll_amount", 800))
        scroll_interval_ms = int(self.config.parser_rules.get("scroll_interval_ms", 0))
        for _ in range(max(0, min(scroll_count, 20))):
            await self.browser.scroll(scroll_amount)
            if scroll_interval_ms > 0:
                await asyncio.sleep(min(scroll_interval_ms, 10_000) / 1000)
        item_selector = self.config.selectors.get("item")
        field_selectors = {key.removeprefix("field_"): value for key, value in self.config.selectors.items() if key.startswith("field_")}
        extracted = await self.browser.extract_visible_content(item_selector, field_selectors)
        return [self._normalize(item, query) for item in extracted[:limit]]

    async def open_content(self, url: str) -> None:
        await self.browser.open(url)

    async def extract_content(self) -> dict[str, Any]:
        if self._current_result is not None:
            return self._current_result
        items = await self.browser.extract_visible_content()
        return self._normalize(items[0], "") if items else {}

    async def download_media(self, content: dict[str, Any]) -> list[bytes]:
        return [await self.browser.download_media(url) for url in content.get("image_urls", [])]

    async def close(self) -> None:
        await self.browser.close()

    def _normalize(self, source: dict[str, Any], query: str) -> dict[str, Any]:
        rules = self.config.parser_rules
        source = dict(source)
        for target, source_name in rules.get("field_map", {}).items():
            if isinstance(source_name, str) and source_name in source:
                source[target] = source[source_name]
        url = self._string(source.get("url"))
        title = self._string(source.get("title"))
        text = self._string(source.get("text"))
        external_id = self._string(source.get("external_id")) or hashlib.sha256(
            (url or f"{title}|{text}").encode("utf-8")
        ).hexdigest()[:32]
        return {
            "external_id": external_id,
            "url": url or "",
            "title": title,
            "text": text,
            "author_name": self._string(source.get("author_name")),
            "published_at": self._parse_datetime(source.get("published_at")),
            "like_count": self._parse_count(source.get("like_count")),
            "favorite_count": self._parse_count(source.get("favorite_count")),
            "comment_count": self._parse_count(source.get("comment_count")),
            "share_count": self._parse_count(source.get("share_count")),
            "view_count": self._parse_count(source.get("view_count")),
            "media_type": self._string(source.get("media_type")) or ("image" if source.get("image_urls") else None),
            "image_urls": self._urls(source.get("image_urls")),
            "video_urls": self._urls(source.get("video_urls")),
            "query_keyword": query,
            "raw_data": source,
        }

    @staticmethod
    def _string(value: object) -> str | None:
        return str(value).strip() if value is not None and str(value).strip() else None

    @staticmethod
    def _urls(value: object) -> list[str]:
        values = value if isinstance(value, list) else [value] if value else []
        return [str(item) for item in values if urlparse(str(item)).scheme in {"http", "https"}]

    @staticmethod
    def _parse_count(value: object) -> int | None:
        if value is None or value == "":
            return None
        try:
            text = str(value).strip().lower().replace(",", "")
            multiplier = 10_000 if text.endswith("w") else 1_000 if text.endswith("k") else 1
            return max(0, int(float(text.rstrip("wk")) * multiplier))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_datetime(value: object) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            return None
