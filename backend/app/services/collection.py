from __future__ import annotations

import asyncio
import logging
from pathlib import Path
import re
from typing import Callable
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.browser.adapter import BrowserAdapter
from app.browser.playwright import PlaywrightBrowserAdapter
from app.core.config import get_settings
from app.api.configuration import ensure_collection_defaults
from app.models.configuration import AppSetting, PlatformConfig
from app.models.content import ContentItem, ContentMetricSnapshot
from app.models.research_task import ResearchTask, ResearchTaskStatus
from app.media import image_suffix
from app.platforms.generic_web import PublicAccessBlockedError
from app.platforms.registry import PlatformRegistry
from app.services.query_expansion import QueryExpansionService

logger = logging.getLogger(__name__)


class ContentCollectionService:
    def __init__(
        self, database: Session, *, browser_factory: Callable[[dict[str, object]], BrowserAdapter] | None = None,
        registry: PlatformRegistry | None = None, query_expansion: QueryExpansionService | None = None,
    ) -> None:
        self.database = database
        self.browser_factory = browser_factory or self._create_browser
        self.registry = registry or PlatformRegistry()
        self.query_expansion = query_expansion or QueryExpansionService(database)

    async def run(self, task: ResearchTask) -> ResearchTask:
        ensure_collection_defaults(self.database)
        config = self.database.scalar(select(PlatformConfig).where(PlatformConfig.name == task.platform))
        if config is None:
            return self._fail(task, f"No platform configuration exists for '{task.platform}'")
        if not config.enabled:
            return self._fail(task, f"Platform '{task.platform}' is disabled")
        # The interval remains page-configurable while the resolved value is supplied to the adapter,
        # keeping browser behavior out of the business pipeline itself.
        config.parser_rules = {
            **config.parser_rules,
            "scroll_interval_ms": config.parser_rules.get(
                "scroll_interval_ms", self._collection_settings().get("scroll_interval_ms", 0),
            ),
        }
        task.status = ResearchTaskStatus.EXPANDING_QUERY
        task.error_message = None
        self.database.commit()
        try:
            if self._has_reusable_expansion(task):
                logger.info("query_expansion_reused task_id=%s", task.id)
            else:
                task.expanded_keywords = await self.query_expansion.expand(task)
            task.status = ResearchTaskStatus.COLLECTING
            self.database.commit()
            browser = self.browser_factory(self._browser_settings())
            adapter = self.registry.create(config, browser)
            failures: list[str] = []
            collected = 0
            try:
                for keyword in self._search_keywords(task):
                    if collected >= task.max_items:
                        break
                    try:
                        results = await adapter.search(keyword, task.max_items - collected)
                    except PublicAccessBlockedError as error:
                        return self._fail(task, str(error))
                    except Exception as error:
                        logger.warning("collection_query_failed task_id=%s keyword=%s", task.id, keyword, exc_info=True)
                        failures.append(f"{keyword}: {self._safe_error(error)}")
                        continue
                    for result in results:
                        if collected >= task.max_items:
                            break
                        try:
                            await self._persist_content(task, result, browser)
                            collected += 1
                        except Exception as error:
                            self.database.rollback()
                            logger.warning("collection_item_failed task_id=%s", task.id, exc_info=True)
                            failures.append(f"content: {self._safe_error(error)}")
                    request_interval_ms = int(self._collection_settings().get("request_interval_ms", 0))
                    if request_interval_ms > 0 and collected < task.max_items:
                        await asyncio.sleep(min(request_interval_ms, 10_000) / 1000)
                task.status = ResearchTaskStatus.PARTIAL if failures else ResearchTaskStatus.COMPLETED
                task.error_message = "; ".join(failures[:10]) or None
                self.database.commit()
                self.database.refresh(task)
                return task
            finally:
                await adapter.close()
        except Exception as error:
            self.database.rollback()
            logger.exception("collection_run_failed task_id=%s", task.id)
            return self._fail(task, self._safe_error(error))

    async def _persist_content(self, task: ResearchTask, result: dict[str, object], browser: BrowserAdapter) -> ContentItem:
        external_id = str(result.get("external_id") or "").strip()
        url = str(result.get("url") or "").strip()
        if not external_id or not url:
            raise ValueError("Collected content requires external_id and URL")
        item = self.database.scalar(select(ContentItem).where(
            ContentItem.research_task_id == task.id, ContentItem.platform == task.platform, ContentItem.external_id == external_id,
        ))
        image_urls = [str(value) for value in result.get("image_urls", []) if isinstance(value, str)]
        if item is None:
            item = ContentItem(research_task_id=task.id, platform=task.platform, external_id=external_id, url=url)
            self.database.add(item)
        for field in ("url", "title", "text", "author_name", "published_at", "like_count", "favorite_count", "comment_count", "share_count", "view_count", "media_type", "query_keyword", "raw_data"):
            if field in result:
                setattr(item, field, result[field])
        item.image_urls = image_urls
        item.video_urls = [str(value) for value in result.get("video_urls", []) if isinstance(value, str)]
        self.database.flush()
        if self._browser_settings().get("download_images"):
            item.local_image_paths = await self._download_images(task.id, item.id, image_urls, browser)
        self.database.add(ContentMetricSnapshot(
            content_item_id=item.id, like_count=item.like_count, favorite_count=item.favorite_count,
            comment_count=item.comment_count, share_count=item.share_count, view_count=item.view_count,
        ))
        self.database.commit()
        self.database.refresh(item)
        return item

    async def _download_images(self, task_id: int, content_id: int, urls: list[str], browser: BrowserAdapter) -> list[str]:
        media_dir = get_settings().data_dir / "tasks" / str(task_id) / "media" / str(content_id)
        media_dir.mkdir(parents=True, exist_ok=True)
        paths: list[str] = []
        for index, url in enumerate(urls):
            try:
                content = await browser.download_media(url)
                suffix = image_suffix(content, url)
                if suffix is None:
                    logger.warning("public_media_not_supported_image task_id=%s content_id=%s url=%s", task_id, content_id, url)
                    continue
                destination = media_dir / f"image-{index + 1}{suffix}"
                destination.write_bytes(content)
                paths.append(destination.as_posix())
            except Exception:
                logger.warning("public_media_download_failed task_id=%s content_id=%s", task_id, content_id, exc_info=True)
        return paths

    def _search_keywords(self, task: ResearchTask) -> list[str]:
        expanded = task.expanded_keywords or {}
        values = list(task.keywords) + [keyword for category in expanded.values() for keyword in category]
        return list(dict.fromkeys(keyword.strip() for keyword in values if keyword.strip()))

    @staticmethod
    def _has_reusable_expansion(task: ResearchTask) -> bool:
        expanded = task.expanded_keywords
        if not isinstance(expanded, dict):
            return False
        original = {value.strip().casefold() for value in task.keywords if value.strip()}
        return any(
            isinstance(values, list) and any(
                isinstance(value, str) and value.strip() and value.strip().casefold() not in original
                for value in values
            )
            for values in expanded.values()
        )

    def _browser_settings(self) -> dict[str, object]:
        setting = self.database.scalar(select(AppSetting).where(AppSetting.key == "browser_defaults"))
        return setting.value if setting and isinstance(setting.value, dict) else {"mode": "isolated", "headless": True, "timeout_seconds": 120, "download_images": True, "headers": {}}

    def _collection_settings(self) -> dict[str, object]:
        setting = self.database.scalar(select(AppSetting).where(AppSetting.key == "collection_defaults"))
        return setting.value if setting and isinstance(setting.value, dict) else {"request_interval_ms": 0}

    @staticmethod
    def _create_browser(settings: dict[str, object]) -> BrowserAdapter:
        browser_mode = str(settings.get("mode", "isolated"))
        cdp_endpoint = settings.get("cdp_endpoint") if browser_mode == "system_cdp" else None
        if browser_mode not in {"isolated", "system_cdp"}:
            raise ValueError("Browser mode must be 'isolated' or 'system_cdp'")
        if browser_mode == "system_cdp":
            cdp_endpoint = ContentCollectionService._cdp_endpoint(cdp_endpoint)
        return PlaywrightBrowserAdapter(
            headless=bool(settings.get("headless", True)),
            timeout_ms=int(settings.get("timeout_seconds", 120)) * 1000,
            headers=ContentCollectionService._browser_headers(settings.get("headers")),
            cdp_endpoint=cdp_endpoint,
        )

    @staticmethod
    def _cdp_endpoint(value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("A local CDP endpoint is required when using the system browser")
        endpoint = value.strip()
        parsed = urlparse(endpoint)
        try:
            port = parsed.port
        except ValueError as error:
            raise ValueError("The system browser CDP endpoint must include a valid local port") from error
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("The system browser CDP endpoint must use localhost")
        if parsed.username or parsed.password or not port:
            raise ValueError("The system browser CDP endpoint must include only a local host and port")
        return endpoint

    @staticmethod
    def _browser_headers(value: object) -> dict[str, str]:
        if value in (None, ""):
            return {}
        if not isinstance(value, dict):
            raise ValueError("Browser headers must be a JSON object")
        headers: dict[str, str] = {}
        for name, header_value in value.items():
            if not isinstance(name, str) or not re.fullmatch(r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+", name):
                raise ValueError("Browser header name is invalid")
            if not isinstance(header_value, str) or "\r" in header_value or "\n" in header_value:
                raise ValueError("Browser header value is invalid")
            headers[name] = header_value
        return headers

    def _fail(self, task: ResearchTask, error: str) -> ResearchTask:
        task.status = ResearchTaskStatus.FAILED
        task.error_message = error
        self.database.commit()
        self.database.refresh(task)
        return task

    @staticmethod
    def _safe_error(error: Exception) -> str:
        return str(error)[:500] or error.__class__.__name__
