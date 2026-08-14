from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class ModelCapabilities:
    """Normalized model capabilities kept independently from any vendor protocol."""

    text: bool = True
    vision: bool = False
    structured_output: bool = True
    tools: bool = False
    streaming: bool = False

    @classmethod
    def from_config(cls, value: object, *, provider_type: str) -> "ModelCapabilities":
        defaults = cls(vision=provider_type == "vision")
        if not isinstance(value, Mapping):
            return defaults
        return cls(
            text=bool(value.get("text", defaults.text)),
            vision=bool(value.get("vision", defaults.vision)),
            structured_output=bool(value.get("structured_output", defaults.structured_output)),
            tools=bool(value.get("tools", defaults.tools)),
            streaming=bool(value.get("streaming", defaults.streaming)),
        )

    def supports(self, capability: str) -> bool:
        return bool(getattr(self, capability, False))
