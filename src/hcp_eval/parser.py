"""Response parsers for Hy3 solver and reviewer output."""

from __future__ import annotations

import json
import logging
import re

from .schemas import (
    ComplexityClaim,
    ErrorType,
    EvidenceRecord,
    ProcessStep,
    SolutionRecord,
)

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> str:
    """Extract JSON from text that may contain markdown fences or leading/trailing text."""
    # Try to find JSON within markdown code fences
    pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        return matches[0].strip()

    # Try to find JSON object/array directly
    text = text.strip()
    if text.startswith("{") or text.startswith("["):
        # Find the matching bracket
        return text

    # Try to find first { to last }
    start = text.find("{")
    if start >= 0:
        # Count brackets to find end
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]

    return text


def parse_solution_response(raw_response: str, task_id: str = "unknown") -> SolutionRecord:
    """Parse Hy3 solver response into a SolutionRecord."""
    try:
        json_str = _extract_json(raw_response)
        data = json.loads(json_str)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("Failed to parse solution JSON: %s", e)
        return SolutionRecord(
            task_id=task_id,
            code="",
            parse_error=f"JSON parse error: {e}",
        )

    # Parse steps
    steps = []
    for step_data in data.get("steps", []):
        try:
            step = ProcessStep(
                id=step_data.get("id", ""),
                type=step_data.get("type", ""),
                claim=step_data.get("claim", ""),
                related_clauses=step_data.get("related_clauses", []),
            )
            steps.append(step)
        except Exception as e:
            logger.warning("Failed to parse step: %s", e)

    # Parse complexity
    complexity_data = data.get("complexity", {})
    complexity = ComplexityClaim(
        time=complexity_data.get("time", "unknown"),
        space=complexity_data.get("space", "unknown"),
    )

    return SolutionRecord(
        task_id=task_id,
        steps=steps,
        complexity=complexity,
        code=data.get("code", ""),
    )


def parse_reviewer_response(raw_response: str) -> list[EvidenceRecord]:
    """Parse Hy3 reviewer response into a list of EvidenceRecords."""
    try:
        json_str = _extract_json(raw_response)
        data = json.loads(json_str)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("Failed to parse reviewer JSON: %s", e)
        return [
            EvidenceRecord(
                source="hy3_review",
                status="insufficient",
                detail=f"Failed to parse reviewer response: {e}",
                confidence=0.0,
            )
        ]

    issues = data.get("issues", [])
    evidence_list = []
    for issue in issues:
        try:
            error_type_str = issue.get("error_type", "UNKNOWN")
            try:
                error_type = ErrorType(error_type_str)
            except ValueError:
                error_type = ErrorType.UNKNOWN

            ev = EvidenceRecord(
                source="hy3_review",
                status=issue.get("status", "insufficient"),
                detail=issue.get("detail", ""),
                target_step=issue.get("target_step"),
                target_clause=issue.get("target_clause"),
                error_type=error_type,
                confidence=issue.get("confidence", 0.8),
            )
            evidence_list.append(ev)
        except Exception as e:
            logger.warning("Failed to parse evidence record: %s", e)

    return evidence_list
