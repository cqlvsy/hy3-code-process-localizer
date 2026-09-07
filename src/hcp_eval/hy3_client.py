"""Hy3 API client using OpenAI-compatible interface."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

from openai import OpenAI

from .config import get_settings
from .schemas import SolutionRecord

logger = logging.getLogger(__name__)


class Hy3Client:
    """Client for interacting with Hy3 via OpenAI-compatible API."""

    def __init__(self, settings: Optional[Any] = None):
        self.settings = settings or get_settings()
        self.client = OpenAI(
            base_url=self.settings.hy3_base_url,
            api_key=self.settings.hy3_api_key,
            timeout=self.settings.hy3_timeout,
        )

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> tuple[str, int]:
        """
        Send a generation request to Hy3.

        Returns:
            Tuple of (response_text, latency_ms)
        """
        start_time = time.monotonic()

        # Use extra_body to pass reasoning_effort if supported
        response = self.client.chat.completions.create(
            model=self.settings.hy3_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature or self.settings.hy3_temperature,
            max_tokens=max_tokens or self.settings.hy3_max_tokens,
            extra_body={
                "reasoning_effort": self.settings.hy3_reasoning_effort,
            },
        )

        latency_ms = int((time.monotonic() - start_time) * 1000)
        content = response.choices[0].message.content or ""
        return content, latency_ms

    def generate_solution(
        self, problem_prompt: str, entry_point: str, task_id: str = "unknown"
    ) -> SolutionRecord:
        """Generate a complete S1-S7 solution for a coding problem."""
        from .prompt_builder import build_solver_prompt

        system_prompt, user_prompt = build_solver_prompt(problem_prompt, entry_point)

        raw_response, latency_ms = self.generate(system_prompt, user_prompt)

        from .parser import parse_solution_response

        solution = parse_solution_response(raw_response, task_id=task_id)
        solution.raw_response = raw_response
        solution.generation_time_ms = latency_ms

        return solution

    def review_solution(
        self,
        problem: Any,
        solution: SolutionRecord,
        eval_result: Any,
        evidence: list,
    ) -> list:
        """
        Use Hy3 to review a solution's process quality.

        Returns:
            List of EvidenceRecord objects.
        """
        from .prompt_builder import build_reviewer_prompt
        from .parser import parse_reviewer_response

        system_prompt, user_prompt = build_reviewer_prompt(
            problem=problem,
            solution=solution,
            eval_result=eval_result,
            existing_evidence=evidence,
        )

        raw_response, _latency = self.generate(system_prompt, user_prompt)

        return parse_reviewer_response(raw_response)

    def health_check(self) -> bool:
        """Check if Hy3 API is reachable."""
        try:
            response = self.client.chat.completions.create(
                model=self.settings.hy3_model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
            )
            return response.choices[0].message.content is not None
        except Exception as e:
            logger.warning("Hy3 health check failed: %s", e)
            return False
