from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.browser.adapter import BrowserAdapter
from app.models.configuration import AppSetting, PlatformConfig
from app.platforms.generic_web import PublicAccessBlockedError
from app.platforms.registry import PlatformRegistry
from app.schemas.configuration import PlatformConfigTestRead
from app.services.collection import ContentCollectionService

logger = logging.getLogger(__name__)


class PlatformConfigurationTestService:
    """Executes a bounded public-page smoke test for one saved platform configuration."""

    def __init__(self, database: Session, *, browser_factory: Callable[[dict[str, object]], BrowserAdapter] | None = None) -> None:
        self.database = database
        self.browser_factory = browser_factory or ContentCollectionService._create_browser

    async def run(self, config: PlatformConfig, *, query: str, limit: int) -> PlatformConfigTestRead:
        browser = self.browser_factory(self._browser_settings())
        adapter = PlatformRegistry().create(config, browser)
        try:
            results = await adapter.search(query, limit)
            first_result = self._display_content(results[0]) if results else None
            detail_result = None
            if results and results[0].get("url"):
                await adapter.open_content(str(results[0]["url"]))
                detail_result = self._display_content(await adapter.extract_content())
            if not results:
                return PlatformConfigTestRead(
                    success=False,
                    message="Configuration test found no matching search cards. Check the selector, login state, or increase result_wait_ms in advanced parser rules.",
                )
            return PlatformConfigTestRead(success=True, search_result_count=len(results), first_result=first_result, detail_result=detail_result, message="Configuration test completed using publicly visible page content.")
        except PublicAccessBlockedError as error:
            return PlatformConfigTestRead(success=False, message=str(error))
        except Exception as error:
            logger.warning("platform_configuration_test_failed platform=%s", config.name, exc_info=True)
            detail = str(error).strip() or error.__class__.__name__
            return PlatformConfigTestRead(success=False, message=f"Configuration test failed: {detail[:300]}")
        finally:
            await adapter.close()

    def _browser_settings(self) -> dict[str, object]:
        setting = self.database.scalar(select(AppSetting).where(AppSetting.key == "browser_defaults"))
        return setting.value if setting and isinstance(setting.value, dict) else {"mode": "isolated", "headless": True, "timeout_seconds": 30, "headers": {}}

    @staticmethod
    def _display_content(value: dict[str, Any]) -> dict[str, Any]:
        fields = ("external_id", "url", "title", "text", "author_name", "published_at", "like_count", "favorite_count", "comment_count", "share_count", "view_count", "image_urls")
        return {field: value.get(field) for field in fields if value.get(field) not in (None, "", [])}
