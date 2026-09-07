"""Rule-based checking for process steps and claims."""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from ..schemas import (
    ErrorType,
    EvidenceRecord,
    ProcessStep,
    SolutionRecord,
)

logger = logging.getLogger(__name__)


class RuleChecker:
    """Apply rule-based checks to solution process steps."""

    # Keywords that suggest edge case handling
    EDGE_CASE_KEYWORDS = [
        "empty", "null", "none", "zero", "negative", "boundary",
        "edge", "corner", "single element", "duplicate", "sorted",
        "maximum", "minimum", "overflow", "underflow", "空", "空列表",
        "边界", "极值", "重复", "空输入",
    ]

    # Patterns indicating complexity claims
    COMPLEXITY_PATTERNS = {
        r"O\(1\)": "O(1)",
        r"O\(log\s*n\)": "O(log n)",
        r"O\(n\)": "O(n)",
        r"O\(n\s*log\s*n\)": "O(n log n)",
        r"O\(n\^?2\)|O\(n\*\*2\)": "O(n^2)",
        r"O\(2?\s*\^?\s*n\)|O\(n\*\*n\)": "O(2^n)",
    }

    def check_process_completeness(self, solution: SolutionRecord) -> list[EvidenceRecord]:
        """Check that all S1-S7 steps are present and non-empty."""
        evidence = []
        step_ids = {s.id for s in solution.steps}

        required_steps = ["S1", "S2", "S3", "S4", "S5", "S6", "S7"]
        for step_id in required_steps:
            if step_id not in step_ids:
                evidence.append(
                    EvidenceRecord(
                        source="static_check",
                        status="contradicted",
                        detail=f"Missing required step {step_id}",
                        target_step=step_id,
                        error_type=ErrorType.REASONING_GAP,
                        confidence=0.9,
                    )
                )
            else:
                # Check that the step has meaningful content
                step = next((s for s in solution.steps if s.id == step_id), None)
                if step and len(step.claim.strip()) < 10:
                    evidence.append(
                        EvidenceRecord(
                            source="static_check",
                            status="warning",
                            detail=f"Step {step_id} has minimal content ({len(step.claim)} chars)",
                            target_step=step_id,
                            error_type=ErrorType.REASONING_GAP,
                            confidence=0.6,
                        )
                    )

        return evidence

    def check_edge_case_mention(self, step: ProcessStep) -> Optional[EvidenceRecord]:
        """Check if S2 (constraints) mentions edge cases."""
        if step.id != "S2":
            return None

        claim_lower = step.claim.lower()
        found_keywords = [kw for kw in self.EDGE_CASE_KEYWORDS if kw.lower() in claim_lower]

        if not found_keywords:
            return EvidenceRecord(
                source="static_check",
                status="warning",
                detail=(
                    "S2 (Constraints & Edge Cases) does not explicitly mention "
                    "common edge cases (empty input, duplicates, boundaries, etc.)"
                ),
                target_step="S2",
                error_type=ErrorType.CONDITION_MISSING,
                confidence=0.6,
            )
        return None

    def check_complexity_consistency(self, solution: SolutionRecord) -> list[EvidenceRecord]:
        """Check if claimed complexity is consistent with code patterns."""
        evidence = []
        code = solution.code.lower()
        claimed_time = solution.complexity.time.lower()

        # Heuristic: nested loops suggest O(n^2) or worse
        nested_loop_count = code.count("for ") + code.count("while ")
        # Rough heuristic - count indentation levels suggesting nesting
        lines = solution.code.splitlines()
        max_indent = 0
        for line in lines:
            stripped = line.lstrip()
            if stripped:
                indent = len(line) - len(stripped)
                max_indent = max(max_indent, indent)

        # Very rough heuristic: 8+ spaces of max nesting suggests O(n^2)
        if max_indent >= 8 and ("o(n)" in claimed_time or "o(1)" in claimed_time):
            evidence.append(
                EvidenceRecord(
                    source="static_check",
                    status="contradicted",
                    detail=(
                        f"Code has deep nesting (max indent={max_indent}) but "
                        f"claims time complexity {solution.complexity.time}"
                    ),
                    target_step="S5",
                    error_type=ErrorType.COMPLEXITY_MISCLAIM,
                    confidence=0.7,
                )
            )

        return evidence

    def check_plan_code_alignment(self, solution: SolutionRecord) -> list[EvidenceRecord]:
        """Check if the algorithm described in S3 matches the implementation in S7."""
        evidence = []

        # Get S3 (algorithm choice) and S7 (code) content
        s3_step = next((s for s in solution.steps if s.id == "S3"), None)
        if not s3_step:
            return evidence

        s3_claim = s3_step.claim.lower()
        code = solution.code.lower()

        # Check for common algorithm keywords in both
        algo_keywords = {
            "recursion": ["recursive", "recurse", "base case"],
            "iteration": ["loop", "for ", "while ", "iterate"],
            "dynamic programming": ["dp", "memo", "cache", "dynamic programming"],
            "greedy": ["greedy", "sort first", "take local optimum"],
            "divide and conquer": ["divide", "conquer", "merge", "split"],
            "hash": ["hash", "dict", "set", "map"],
            "two pointer": ["two pointer", "left.*right", "start.*end"],
            "binary search": ["binary search", "mid", "low.*high"],
            "sorting": ["sort(", ".sort", "sorted("],
            "backtracking": ["backtrack", "prune", "dfs"],
        }

        mentioned_algos = []
        for algo, keywords in algo_keywords.items():
            if any(kw in s3_claim for kw in keywords):
                mentioned_algos.append(algo)

        # Verify at least one mentioned algorithm appears in code
        if mentioned_algos:
            found_in_code = False
            for algo in mentioned_algos:
                keywords = algo_keywords.get(algo, [])
                if any(kw in code for kw in keywords):
                    found_in_code = True
                    break

            if not found_in_code:
                evidence.append(
                    EvidenceRecord(
                        source="static_check",
                        status="contradicted",
                        detail=(
                            f"S3 mentions algorithms [{', '.join(mentioned_algos)}] "
                            f"but code does not show clear implementation of any of them"
                        ),
                        target_step="S7",
                        error_type=ErrorType.PLAN_CODE_MISMATCH,
                        confidence=0.65,
                    )
                )

        return evidence

    def run_all_checks(self, solution: SolutionRecord) -> list[EvidenceRecord]:
        """Run all rule-based checks and return combined evidence."""
        evidence = []

        # Completeness check
        evidence.extend(self.check_process_completeness(solution))

        # Per-step checks
        for step in solution.steps:
            edge_evidence = self.check_edge_case_mention(step)
            if edge_evidence:
                evidence.append(edge_evidence)

        # Cross-step consistency checks
        evidence.extend(self.check_complexity_consistency(solution))
        evidence.extend(self.check_plan_code_alignment(solution))

        return evidence
