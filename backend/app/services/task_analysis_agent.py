from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.analysis_tools import TaskAnalysisToolRegistry
from app.models.research_task import ResearchTask
from app.providers.llm import LLMProvider
from app.providers.vision import VisionProvider


class TaskAnalysisResult(BaseModel):
    copywriting_summary: str
    visual_summary: str
    audience_summary: str
    popularity_summary: str
    reusable_patterns: list[str]
    trend_tags: list[str]
    evidence: list[str]
    limitations: list[str]
    hot_topics: list[str] = Field(default_factory=list)
    rising_topics: list[str] = Field(default_factory=list)
    visual_patterns: list[str] = Field(default_factory=list)
    copywriting_patterns: list[str] = Field(default_factory=list)
    audience_patterns: list[str] = Field(default_factory=list)
    scenario_patterns: list[str] = Field(default_factory=list)
    style_patterns: list[str] = Field(default_factory=list)
    domain_patterns: list[str] = Field(default_factory=list)


class TaskAnalysisAgent:
    """A bounded, tool-directed model workflow for one whole research task."""

    MAX_TOOL_CALLS = 4

    def __init__(self, registry: TaskAnalysisToolRegistry, *, llm_provider: LLMProvider, vision_provider: VisionProvider) -> None:
        self.registry = registry
        self.llm_provider = llm_provider
        self.vision_provider = vision_provider

    async def run(self) -> TaskAnalysisResult:
        observations, image_path = await self._collect_evidence()
        visual_evidence = await self._visual_evidence(image_path)
        context = {
            "analysis_type": "task_summary", "task": self.registry.execute("get_task_constraints", {}),
            "tool_observations": observations, "visual_evidence": visual_evidence,
        }
        prompt = (
            "Synthesize one task-level content trend analysis from the supplied tool evidence. "
            "Do not analyze each item separately and do not invent metrics. Return exactly one JSON object with: "
            "copywriting_summary, visual_summary, audience_summary, popularity_summary, reusable_patterns, "
            "trend_tags, evidence, limitations, hot_topics, rising_topics, visual_patterns, copywriting_patterns, "
            "audience_patterns, scenario_patterns, style_patterns, domain_patterns. The four summary fields are strings; "
            "every list contains plain strings."
        )
        response = await self.llm_provider.generate_structured(prompt=prompt, context=context)
        try:
            return TaskAnalysisResult.model_validate(response)
        except ValidationError as error:
            repaired = await self.llm_provider.generate_structured(
                prompt=f"Repair the previous JSON to the exact required task-summary schema. Validation errors: {str(error)[:3000]}",
                context={**context, "previous_json": response},
            )
            return TaskAnalysisResult.model_validate(repaired)

    async def _collect_evidence(self) -> tuple[list[dict[str, Any]], Path | None]:
        plan = await self.llm_provider.generate_structured(
            prompt=(
                "You are planning a task-level trend analysis. Choose up to four read-only tools needed for representative evidence. "
                "Return JSON only: {\"calls\":[{\"name\":string,\"arguments\":object}]}. "
                f"Available tools: {json.dumps(TaskAnalysisToolRegistry.definitions(), ensure_ascii=False)}"
            ),
            context={"analysis_type": "tool_plan", "task": self.registry.execute("get_task_constraints", {})},
        )
        calls = plan.get("calls") if isinstance(plan.get("calls"), list) else []
        if not calls:
            calls = [
                {"name": "get_ranked_contents", "arguments": {"board": "Hot", "limit": 8}},
                {"name": "get_task_constraints", "arguments": {}},
            ]
        observations: list[dict[str, Any]] = []
        image_path: Path | None = None
        for call in calls[:self.MAX_TOOL_CALLS]:
            if not isinstance(call, dict) or not isinstance(call.get("name"), str):
                continue
            try:
                result = self.registry.execute(call["name"], call.get("arguments", {}))
                observations.append({"tool": call["name"], "result": result})
                if call["name"] == "get_image_evidence" and image_path is None:
                    images = result.get("available_images") if isinstance(result, dict) else []
                    if isinstance(images, list):
                        image_path = next((Path(value) for value in images if isinstance(value, str) and Path(value).is_file()), None)
            except ValueError as error:
                observations.append({"tool": call["name"], "error": str(error)})
        if not observations:
            observations.append({"tool": "get_ranked_contents", "result": self.registry.execute("get_ranked_contents", {"board": "Hot", "limit": 8})})
        if image_path is None:
            image_content_id = self._representative_image_content_id(observations)
            if image_content_id is not None:
                result = self.registry.execute("get_image_evidence", {"content_item_id": image_content_id})
                observations.append({"tool": "get_image_evidence", "result": result})
                images = result.get("available_images", [])
                image_path = next((Path(value) for value in images if isinstance(value, str) and Path(value).is_file()), None)
        return observations, image_path

    @staticmethod
    def _representative_image_content_id(observations: list[dict[str, Any]]) -> int | None:
        for observation in observations:
            result = observation.get("result")
            if not isinstance(result, dict):
                continue
            for item in result.get("items", []):
                if isinstance(item, dict) and item.get("has_local_images") and isinstance(item.get("content_item_id"), int):
                    return item["content_item_id"]
        return None

    async def _visual_evidence(self, image_path: Path | None) -> dict[str, Any]:
        if image_path is None:
            return {"available": False, "limitation": "No representative local image was selected by the task-scoped tools."}
        return await self.vision_provider.analyze_image(
            image_path=image_path,
            prompt=(
                "Extract concise evidence for a task-level visual trend summary. Return JSON with subject, main_colors, style, "
                "composition, lighting, mood, notable_elements, reusable_visual_patterns, domain_attributes and confidence."
            ),
            context={"analysis_type": "task_visual_evidence", "task_id": self.registry.task.id},
        )
