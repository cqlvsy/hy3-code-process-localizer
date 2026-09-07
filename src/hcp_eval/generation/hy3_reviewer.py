"""Hy3 Reviewer - reviews solution process quality."""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from ..hy3_client import Hy3Client
from ..schemas import EvidenceRecord, SolutionRecord, EvaluationResult, ProblemSpec

logger = logging.getLogger(__name__)


class Hy3Reviewer:
    """Reviews solution process quality using Hy3."""

    def __init__(self, client: Optional[Hy3Client] = None):
        self.client = client

    def review(
        self,
        problem: ProblemSpec,
        solution: SolutionRecord,
        eval_result: EvaluationResult,
        existing_evidence: List[EvidenceRecord],
    ) -> List[EvidenceRecord]:
        """
        Review a solution's process quality.

        Args:
            problem: The original problem specification.
            solution: The Hy3-generated solution.
            eval_result: Current evaluation result from execution/static checks.
            existing_evidence: Evidence already collected from other sources.

        Returns:
            List of new EvidenceRecords from Hy3 review.
        """
        if self.client is None:
            logger.warning("Hy3 client not initialized. Skipping review.")
            return []

        try:
            return self.client.review_solution(
                problem=problem,
                solution=solution,
                eval_result=eval_result,
                evidence=existing_evidence,
            )
        except Exception as e:
            logger.error("Hy3 review failed: %s", e)
            return [
                EvidenceRecord(
                    source="hy3_review",
                    status="insufficient",
                    detail=f"Review failed: {e}",
                    confidence=0.0,
                )
            ]
