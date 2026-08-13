from app.platforms.adapter import PlatformAdapter
from app.platforms.generic_web import GenericWebPlatformAdapter
from app.platforms.mock import MockPlatformAdapter
from app.platforms.registry import PlatformRegistry

__all__ = ["GenericWebPlatformAdapter", "MockPlatformAdapter", "PlatformAdapter", "PlatformRegistry"]
