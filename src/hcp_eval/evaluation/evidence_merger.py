"""Evidence merging and conflict resolution."""

from __future__ import annotations

import logging
from typing import Any, Optional

from ..schemas import (
    ErrorType,
    EvidenceRecord,
    EvaluationResult,
    StepId,
)

logger = logging.getLogger(__name__)

# Priority order for evidence sources (higher = more authoritative)
SOURCE_PRIORITY = {
    "plus_test": 100,       # Test failures are ground truth
    "base_test": 90,         # Base test failures
    "sbfl": 80,              # Coverage-based localization
    "static_check": 60,      # Static analysis findings
    "hy3_review": 50,        # LLM review (supplementary)
}

# Step ordering for determining "first error"
STEP_ORDER = {"S1": 1, "S2": 2, "S3": 3, "S4": 4, "S5": 5, "S6": 6, "S7": 7}


class EvidenceMerger:
    """Merge evidence from multiple sources into a coherent assessment."""

    def merge(
        self,
        evidence_lists: list[list[EvidenceRecord]],
    ) -> list[EvidenceRecord]:
        """
        Merge multiple evidence lists into a single deduplicated, prioritized list.

        Args:
            evidence_lists: Lists of evidence from different sources.

        Returns:
            Merged and sorted evidence list.
        """
        all_evidence = []
        for ev_list in evidence_lists:
            all_evidence.extend(ev_list)

        # Sort by priority (descending), then by step order (ascending)
        all_evidence.sort(
            key=lambda e: (
                -SOURCE_PRIORITY.get(e.source, 0),
                STEP_ORDER.get(e.target_step or "S7", 99),
                -e.confidence,
            )
        )

        # Deduplicate: keep highest-priority version of similar evidence
        merged = []
        seen_keys = set()
        for ev in all_evidence:
            # Create a key based on target_step + error_type
            key = (ev.target_step, ev.error_type, ev.source)
            if key not in seen_keys:
                seen_keys.add(key)
                merged.append(ev)

        return merged

    def determine_first_error_step(self, evidence: list[EvidenceRecord]) -> Optional[str]:
        """
        Determine the earliest step where an error occurs.

        Only considers evidence with 'contradicted' status.
        """
        contradicted = [e for e in evidence if e.status == "contradicted"]

        if not contradicted:
            return None

        # Find the earliest step with contradicted evidence
        earliest_step = None
        earliest_order = float("inf")

        for ev in contradicted:
            if ev.target_step:
                order = STEP_ORDER.get(ev.target_step, 99)
                if order < earliest_order:
                    earliest_order = order
                    earliest_step = ev.target_step

        return earliest_step

    def determine_primary_error_type(
        self, evidence: list[EvidenceRecord]
    ) -> ErrorType:
        """
        Determine the primary error type from all evidence.

        Prioritizes higher-confidence, earlier-step errors.
        """
        contradicted = [e for e in evidence if e.status == "contradicted" and e.error_type]

        if not contradicted:
            return ErrorType.UNKNOWN

        # Sort by step order then confidence
        contradicted.sort(
            key=lambda e: (
                STEP_ORDER.get(e.target_step or "S7", 99),
                -e.confidence,
            )
        )

        return contradicted[0].error_type

    def detect_unsupported_success(
        self,
        eval_result: EvaluationResult,
        evidence: list[EvidenceRecord],
    ) -> bool:
        """
        Detect cases where final answer is correct but process is flawed.

        This identifies:
        - Correct by coincidence
        - Passed tests but wrong reasoning
        - Right answer, wrong method
        """
        if not eval_result.final_correct:
            return False

        # If final is correct but there are contradicted evidences in early steps
        early_contradictions = [
            e
            for e in evidence
            if e.status == "contradicted"
            and e.target_step
            and STEP_ORDER.get(e.target_step, 99) <= 5  # S1-S5
        ]

        # Also check for process-level issues.
        # IMPORTANT: only *contradicted* evidence counts. A low-confidence
        # `warning` (e.g. a step with minimal content) must NOT by itself
        # trigger an unsupported-success verdict.
        process_issues = [
            e
            for e in evidence
            if e.status == "contradicted"
            and e.error_type
            in (
                ErrorType.UNJUSTIFIED_ASSUMPTION,
                ErrorType.REASONING_GAP,
                ErrorType.ALGORITHM_INVALID,
                ErrorType.SPEC_MISREAD,
            )
        ]

        return len(early_contradictions) > 0 or len(process_issues) > 0

    def find_violated_clause(self, evidence: list[EvidenceRecord]) -> Optional[str]:
        """Find the most frequently violated clause across evidence."""
        clause_counts: dict[str, int] = {}
        for ev in evidence:
            if ev.status == "contradicted" and ev.target_clause:
                clause_counts[ev.target_clause] = clause_counts.get(ev.target_clause, 0) + 1

        if not clause_counts:
            return None

        # Return the most violated clause
        return max(clause_counts.keys(), key=lambda c: clause_counts[c])
