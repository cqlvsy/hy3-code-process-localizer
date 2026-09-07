"""Hy3 Solver - generates S1-S7 solutions for coding problems."""

from __future__ import annotations

import logging
from typing import Any, Optional

from ..hy3_client import Hy3Client
from ..prompt_builder import build_solver_prompt
from ..parser import parse_solution_response
from ..schemas import SolutionRecord

logger = logging.getLogger(__name__)


class Hy3Solver:
    """Generates complete S1-S7 process solutions using Hy3."""

    def __init__(self, client: Optional[Hy3Client] = None):
        self.client = client

    def solve(self, problem_prompt: str, entry_point: str) -> SolutionRecord:
        """
        Generate a complete solution for a coding problem.

        Args:
            problem_prompt: The problem description text.
            entry_point: The function name to implement.

        Returns:
            SolutionRecord with S1-S7 steps, complexity, and code.
        """
        if self.client is None:
            raise RuntimeError("Hy3 client not initialized. Pass a Hy3Client instance.")

        return self.client.generate_solution(problem_prompt, entry_point)

    def solve_batch(
        self,
        problems: list[tuple[str, str]],
        on_progress=None,
    ) -> list[SolutionRecord]:
        """
        Generate solutions for multiple problems.

        Args:
            problems: List of (problem_prompt, entry_point) tuples.
            on_progress: Optional callback(current, total).

        Returns:
            List of SolutionRecords.
        """
        solutions = []
        total = len(problems)

        for i, (prompt, entry_point) in enumerate(problems):
            logger.info("Solving problem %d/%d: %s", i + 1, total, entry_point)
            solution = self.solve(prompt, entry_point)
            solutions.append(solution)

            if on_progress:
                on_progress(i + 1, total)

        return solutions
