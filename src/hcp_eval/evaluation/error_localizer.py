"""Core error localization logic combining all evidence sources."""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from ..schemas import (
    ErrorType,
    EvidenceRecord,
    EvaluationResult,
    ProblemSpec,
    SolutionRecord,
)
from ..execution import SandboxRunner, run_sbfl_analysis
from ..code_utils import prepare_function_code
from .ast_checker import ASTChecker
from .rule_checker import RuleChecker
from .evidence_merger import EvidenceMerger

logger = logging.getLogger(__name__)


class ErrorLocalizer:
    """
    Main orchestrator for evaluating a single problem-solution pair.

    Coordinates:
    1. Code execution (sandbox)
    2. Coverage collection & SBFL
    3. AST-based static analysis
    4. Rule-based process checking
    5. Evidence merging
    6. Final determination
    """

    def __init__(self, timeout: int = 30):
        self.sandbox = SandboxRunner(timeout=timeout)
        self.ast_checker = ASTChecker()
        self.rule_checker = RuleChecker()
        self.merger = EvidenceMerger()

    def evaluate(
        self,
        problem: ProblemSpec,
        solution: SolutionRecord,
        collect_coverage_data: bool = True,
    ) -> EvaluationResult:
        """
        Full evaluation pipeline for one problem.
        """
        start_time = time.monotonic()
        all_evidence: list[EvidenceRecord] = []

        # Phase 1: Execute base tests
        base_code = prepare_function_code(solution.code, problem.entry_point)
        logger.info("[%s] Running %d base tests...", problem.task_id, len(problem.base_tests))
        base_results = self.sandbox.run_all_tests(
            base_code, problem.base_tests, problem.entry_point
        )
        base_passed = all(r.passed for r in base_results)

        # Phase 2: Execute plus tests (with oracle for comparison)
        plus_code = prepare_function_code(
            solution.code, problem.entry_point, problem.oracle_code
        )
        logger.info("[%s] Running %d plus tests...", problem.task_id, len(problem.plus_tests))
        plus_results = self.sandbox.run_all_tests(
            plus_code, problem.plus_tests, problem.entry_point
        )
        plus_passed = all(r.passed for r in plus_results)

        # Phase 3: Collect test evidence
        test_evidence = self._collect_test_evidence(base_results, plus_results)
        all_evidence.extend(test_evidence)

        # Phase 4: Static analysis (AST)
        logger.info("[%s] Running AST analysis...", problem.task_id)
        ast_evidence = self.ast_checker.check(solution.code, problem.entry_point)
        all_evidence.extend(ast_evidence)

        # Phase 5: Rule-based process checking
        logger.info("[%s] Running rule checks...", problem.task_id)
        rule_evidence = self.rule_checker.run_all_checks(solution)
        all_evidence.extend(rule_evidence)

        # Phase 6: SBFL (optional, slower)
        suspect_lines = []
        if collect_coverage_data and (problem.plus_tests or problem.base_tests):
            logger.info("[%s] Running SBFL analysis...", problem.task_id)
            suspect_lines, sbfl_evidence = run_sbfl_analysis(
                function_code=plus_code,
                base_tests=problem.base_tests,
                plus_tests=problem.plus_tests,
                base_results=base_results,
                plus_results=plus_results,
                function_name=problem.entry_point,
            )
            all_evidence.extend(sbfl_evidence)

        # Phase 7: Merge evidence and determine results
        merged_evidence = self.merger.merge([all_evidence])
        first_error_step = self.merger.determine_first_error_step(merged_evidence)
        primary_error_type = self.merger.determine_primary_error_type(merged_evidence)
        violated_clause = self.merger.find_violated_clause(merged_evidence)

        final_correct = base_passed and plus_passed
        process_correct = first_error_step is None

        # Build a temp result for unsupported success detection
        temp_result = EvaluationResult(
            task_id=problem.task_id,
            dataset=problem.dataset,
            final_correct=final_correct,
        )
        unsupported_success = self.merger.detect_unsupported_success(temp_result, merged_evidence)

        # Count test results
        all_results = base_results + plus_results
        total_tests = len(all_results)
        passed_tests = sum(1 for r in all_results if r.passed)
        failed_tests = sum(1 for r in all_results if not r.passed)
        exec_errors = sum(
            1 for r in all_results
            if not r.passed and r.error and ("Error" in r.error or "Exception" in r.error)
        )

        eval_time_ms = int((time.monotonic() - start_time) * 1000)

        return EvaluationResult(
            task_id=problem.task_id,
            dataset=problem.dataset,
            final_correct=final_correct,
            base_passed=base_passed,
            plus_passed=plus_passed,
            process_correct=process_correct,
            first_error_step=first_error_step,
            violated_clause=violated_clause,
            primary_error_type=primary_error_type,
            unsupported_success=unsupported_success,
            suspect_code_lines=suspect_lines,
            evidence=merged_evidence,
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            execution_errors=exec_errors,
            eval_time_ms=eval_time_ms,
        )

    def _collect_test_evidence(
        self,
        base_results: list,
        plus_results: list,
    ) -> list[EvidenceRecord]:
        """Convert test execution results into evidence records."""
        evidence = []

        for i, result in enumerate(base_results):
            if not result.passed:
                err_type = self._classify_test_error(result)
                evidence.append(EvidenceRecord(
                    source="base_test",
                    status="contradicted",
                    detail=f"Base test {i+1} failed: {(result.error or 'unknown')[:200]}",
                    target_step="S7",
                    error_type=err_type,
                    confidence=1.0,
                ))

        for i, result in enumerate(plus_results):
            if not result.passed:
                err_type = self._classify_test_error(result)
                evidence.append(EvidenceRecord(
                    source="plus_test",
                    status="contradicted",
                    detail=f"Plus test {i+1} failed: {(result.error or 'unknown')[:200]}",
                    target_step="S7",
                    error_type=err_type,
                    confidence=1.0,
                ))

        return evidence

    @staticmethod
    def _classify_test_error(result) -> ErrorType:
        """Classify a test failure into an error type."""
        error_msg = result.error or ""
        if result.timeout:
            return ErrorType.TIMEOUT
        if "Error" in error_msg or "Exception" in error_msg:
            return ErrorType.RUNTIME_ERROR
        if "Assertion" in error_msg:
            return ErrorType.EDGE_CASE_FAILURE
        return ErrorType.UNKNOWN
