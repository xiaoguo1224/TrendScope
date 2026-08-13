from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class VisionProvider(Protocol):
    async def analyze_image(self, *, image_path: Path, prompt: str, context: dict[str, Any]) -> dict[str, Any]: ...


class MockVisionProvider:
    """Deterministic local-image provider used for tests and offline deployments."""

    async def analyze_image(self, *, image_path: Path, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        title = str(context.get("title") or "").strip()
        topic = str(context.get("topic") or "").strip()
        subject = title or topic or image_path.stem
        return {
            "subject": subject,
            "main_colors": [], "secondary_colors": [], "style": "not_classified",
            "composition": "not_classified", "camera_angle": "not_classified",
            "lighting": "not_classified", "background": "not_classified",
            "visual_focus": subject, "scene": "not_classified", "mood": "neutral",
            "target_audience": [], "notable_elements": [image_path.name],
            "reusable_visual_patterns": [], "domain_attributes": {}, "confidence": 0.0,
        }
