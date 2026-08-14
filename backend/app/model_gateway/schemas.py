from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ModelRequest:
    """Provider-neutral input passed from an Agent/service to ModelGateway."""

    purpose: str
    prompt: str
    context: dict[str, Any] = field(default_factory=dict)
    image_path: Path | None = None
    require_structured_output: bool = True


@dataclass(frozen=True)
class ModelResponse:
    """Provider-neutral result; raw vendor envelopes never escape the adapter."""

    data: dict[str, Any]
    provider_name: str
    model_name: str
    endpoint: str
