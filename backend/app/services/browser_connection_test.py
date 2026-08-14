from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.browser.adapter import BrowserAdapter
from app.models.configuration import AppSetting
from app.schemas.configuration import BrowserConnectionTestRead
from app.services.collection import ContentCollectionService

logger = logging.getLogger(__name__)


class BrowserConnectionTestService:
    """Checks that the saved local CDP connection can create a service-owned tab."""

    def __init__(self, database: Session, *, browser_factory: Callable[[dict[str, object]], BrowserAdapter] | None = None) -> None:
        self.database = database
        self.browser_factory = browser_factory or ContentCollectionService._create_browser

    async def run(self) -> BrowserConnectionTestRead:
        settings = self._browser_settings()
        if settings.get("mode", "isolated") != "system_cdp":
            return BrowserConnectionTestRead(
                success=False,
                message="Select 'Connect system browser' and save the local CDP address before testing.",
            )
        browser: BrowserAdapter | None = None
        try:
            browser = self.browser_factory(settings)
            # about:blank exercises CDP attachment and a new tab without contacting a platform.
            await browser.open("about:blank")
            return BrowserConnectionTestRead(
                success=True,
                message="Connected to the system browser. Your browser remains open; TrendScope only closed its temporary test tab.",
            )
        except Exception as error:
            logger.warning("system_browser_connection_test_failed", exc_info=True)
            detail = str(error).strip() or error.__class__.__name__
            return BrowserConnectionTestRead(success=False, message=f"System browser connection failed: {detail[:300]}")
        finally:
            if browser is not None:
                try:
                    await browser.close()
                except Exception:
                    logger.warning("system_browser_connection_test_close_failed", exc_info=True)

    def _browser_settings(self) -> dict[str, object]:
        setting = self.database.scalar(select(AppSetting).where(AppSetting.key == "browser_defaults"))
        return setting.value if setting and isinstance(setting.value, dict) else {"mode": "isolated"}
