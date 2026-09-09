"""Rule-based checking for process steps and claims."""

from __future__ import annotations

import ast
import logging
import re
import textwrap
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
        """Check if claimed complexity is consistent with code patterns.

        Uses AST-based loop-nesting analysis instead of a naive indentation
        heuristic: a single loop (depth 1) is fully consistent with an O(n)
        claim, while *nested* loops (depth >= 2) contradict a sub-quadratic
        claim such as O(n) or O(1). Plain indentation depth is never treated
        as evidence on its own.
        """
        evidence = []
        claimed_time = solution.complexity.time.lower()

        # Only challenge claims that are (at most) sub-quadratic.
        sub_quadratic = any(
            tok in claimed_time
            for tok in ["o(1)", "o(log", "o(n)", "o(n log"]
        )
        if not sub_quadratic:
            return evidence

        # Parse code; fall back to no flag if it does not parse.
        try:
            tree = ast.parse(textwrap.dedent(solution.code))
        except SyntaxError:
            return evidence

        max_loop_depth = self._max_loop_depth(tree)

        # Nested loops (depth >= 2) imply O(n^2) or worse, contradicting an
        # O(n) / O(1) claim. A single loop is fine.
        if max_loop_depth >= 2:
            evidence.append(
                EvidenceRecord(
                    source="static_check",
                    status="contradicted",
                    detail=(
                        f"Code contains nested loops (depth={max_loop_depth}) but "
                        f"claims time complexity {solution.complexity.time}, which is "
                        f"sub-quadratic"
                    ),
                    target_step="S5",
                    error_type=ErrorType.COMPLEXITY_MISCLAIM,
                    confidence=0.7,
                )
            )

        return evidence

    @staticmethod
    def _max_loop_depth(node: ast.AST, depth: int = 0) -> int:
        """Return the maximum nesting depth of loops within *node*."""
        best = depth
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.For, ast.AsyncFor, ast.While)):
                best = max(best, RuleChecker._max_loop_depth(child, depth + 1))
            else:
                best = max(best, RuleChecker._max_loop_depth(child, depth))
        return best

    def check_plan_code_alignment(self, solution: SolutionRecord) -> list[EvidenceRecord]:
        """Check if the algorithm described in S3 matches the implementation in S7.

        Algorithm mentions are detected from S3 prose with *word-safe* keyword
        matching (so e.g. "formula for" or "for exact" does not trip the
        "iteration" detector), and confirmed against actual code constructs via
        AST where possible.
        """
        evidence = []

        s3_step = next((s for s in solution.steps if s.id == "S3"), None)
        if not s3_step:
            return evidence

        s3 = s3_step.claim.lower()
        code = solution.code.lower()

        algo_keywords = {
            "recursion": ["recursive", "recurse", "recursion"],
            "iteration": ["iterative", "iteration", "loop", "while loop", "for loop", "iterate"],
            "dynamic programming": ["dynamic programming", " memo", " memoiz", "cache"],
            "greedy": ["greedy"],
            "divide and conquer": ["divide and conquer", "mergesort", "merge sort"],
            "hash": ["hash", "hashmap", "dictionary", " hashset"],
            "two pointer": ["two pointer", "two-pointer", "two pointers"],
            "binary search": ["binary search", "bisect"],
            "sorting": ["sort(", ".sort", "sorted("],
            "backtracking": ["backtrack", "depth-first", " dfs"],
        }

        # Negation-aware mention detection: a keyword such as "iteration" inside a
        # negated phrase like "without manual iteration" / "no loop" must NOT be
        # treated as the solution *planning* to use that construct.
        negation_near = re.compile(r"\b(without|no|not|avoid|instead of)\b", re.IGNORECASE)

        def mentioned(keywords: list[str]) -> bool:
            for kw in keywords:
                idx = s3.find(kw)
                while idx != -1:
                    before = s3[max(0, idx - 25):idx]
                    if not negation_near.search(before):
                        return True
                    idx = s3.find(kw, idx + 1)
            return False

        mentioned_algos = [a for a, kws in algo_keywords.items() if mentioned(kws)]
        if not mentioned_algos:
            return evidence

        # Confirm via code constructs (AST-based where possible).
        try:
            tree = ast.parse(textwrap.dedent(solution.code))
        except SyntaxError:
            return evidence
        has_loop = any(
            isinstance(n, (ast.For, ast.AsyncFor, ast.While)) for n in ast.walk(tree)
        )
        has_sort = ("sorted(" in code) or (".sort(" in code)
        func_names = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        has_recursion = any(
            isinstance(c, ast.Call)
            and isinstance(c.func, ast.Name)
            and c.func.id in func_names
            for c in ast.walk(tree)
        )

        found = False
        for algo in mentioned_algos:
            if algo == "iteration" and has_loop:
                found = True
                break
            if algo == "recursion" and has_recursion:
                found = True
                break
            if algo == "sorting" and has_sort:
                found = True
                break
            if algo in (
                "dynamic programming",
                "greedy",
                "divide and conquer",
                "hash",
                "two pointer",
                "binary search",
                "backtracking",
            ):
                kws = algo_keywords[algo]
                if any(kw.strip() and kw in code for kw in kws):
                    found = True
                    break

        if not found:
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
