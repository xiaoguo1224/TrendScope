from __future__ import annotations

from collections.abc import Callable

from app.browser.adapter import BrowserAdapter
from app.models.configuration import PlatformConfig
from app.platforms.adapter import PlatformAdapter
from app.platforms.generic_web import GenericWebPlatformAdapter


class PlatformRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, Callable[[PlatformConfig, BrowserAdapter], PlatformAdapter]] = {}
        self.register("generic-web", GenericWebPlatformAdapter)

    def register(self, name: str, factory: Callable[[PlatformConfig, BrowserAdapter], PlatformAdapter]) -> None:
        self._factories[name] = factory

    def create(self, config: PlatformConfig, browser: BrowserAdapter) -> PlatformAdapter:
        factory = self._factories.get(config.name, GenericWebPlatformAdapter)
        return factory(config, browser)
