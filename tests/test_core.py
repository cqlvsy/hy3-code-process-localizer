"""Tests for the Hy3 Code Process Localizer."""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hcp_eval.schemas import (
    Clause,
    ComplexityClaim,
    ErrorType,
    EvidenceRecord,
    ProcessStep,
    ProblemSpec,
    SolutionRecord,
    EvaluationResult,
    MetricsSummary,
    SuspectCodeLine,
)


class TestSchemas:
    """Test data model validation."""

    def test_clause_creation(self):
        clause = Clause(id="C1", text="Input must be a list")
        assert clause.id == "C1"
        assert "list" in clause.text

    def test_process_step(self):
        step = ProcessStep(
            id="S1",
            type="requirement_understanding",
            claim="The function should return unique elements",
            related_clauses=["C1", "C2"],
        )
        assert step.id == "S1"
        assert len(step.related_clauses) == 2

    def test_problem_spec(self):
        spec = ProblemSpec(
            task_id="Mbpp/1",
            dataset="mbppplus",
            prompt="Write a function that returns unique elements",
            entry_point="unique",
            canonical_solution="def unique(x): return list(set(x))",
            base_tests=["assert unique([1,2,2,3]) == [1,2,3]"],
            plus_tests=[
                "assert unique([]) == []",
                "assert unique([1,1,1]) == [1]",
                "assert unique([1,2,3]) == [1,2,3]",
            ],
            clauses=[Clause(id="C1", text="Return unique elements")],
        )
        assert spec.entry_point == "unique"
        assert len(spec.plus_tests) == 3

    def test_solution_record(self):
        solution = SolutionRecord(
            task_id="Mbpp/1",
            steps=[
                ProcessStep(
                    id="S1", type="req", claim="Understand requirement", related_clauses=[]
                ),
            ],
            complexity=ComplexityClaim(time="O(n)", space="O(n)"),
            code="def solution(x): return list(set(x))",
        )
        assert solution.code == "def solution(x): return list(set(x))"
        assert solution.complexity.time == "O(n)"

    def test_evidence_record(self):
        ev = EvidenceRecord(
            source="plus_test",
            status="contradicted",
            detail="Failed on empty input",
            target_step="S2",
            target_clause="C2",
            error_type=ErrorType.CONDITION_MISSING,
            confidence=0.95,
        )
        assert ev.status == "contradicted"
        assert ev.error_type == ErrorType.CONDITION_MISSING

    def test_evaluation_result(self):
        result = EvaluationResult(
            task_id="Mbpp/1",
            dataset="mbppplus",
            final_correct=False,
            base_passed=True,
            plus_passed=False,
            process_correct=False,
            first_error_step="S2",
            violated_clause="C2",
            primary_error_type=ErrorType.CONDITION_MISSING,
        )
        assert not result.final_correct
        assert result.base_passed
        assert result.first_error_step == "S2"

    def test_suspect_code_line(self):
        line = SuspectCodeLine(line=5, score=0.82, reason="High suspiciousness")
        assert line.line == 5
        assert 0 <= line.score <= 1


class TestErrorTypes:
    """Test error type enum completeness."""

    def test_all_error_types_exist(self):
        expected = [
            "FORMAT_ERROR", "SPEC_MISREAD", "CONDITION_MISSING",
            "UNJUSTIFIED_ASSUMPTION", "ALGORITHM_INVALID", "REASONING_GAP",
            "COMPLEXITY_MISCLAIM", "EDGE_CASE_FAILURE", "PLAN_CODE_MISMATCH",
            "PROCESS_RESULT_MISMATCH", "RUNTIME_ERROR", "TIMEOUT",
            "SECURITY_VIOLATION", "UNKNOWN",
        ]
        actual = [et.value for et in ErrorType]
        assert set(expected) == set(actual)


class TestParser:
    """Test response parsing."""

    def test_extract_json_from_markdown(self):
        from hcp_eval.parser import _extract_json

        # Test markdown fence extraction
        text = '```json\n{"key": "value"}\n```'
        result = _extract_json(text)
        assert result == '{"key": "value"}'

    def test_extract_json_direct(self):
        from hcp_eval.parser import _extract_json

        text = '{"name": "test", "steps": []}'
        result = _extract_json(text)
        assert '"name": "test"' in result

    def test_parse_solution(self):
        from hcp_eval.parser import parse_solution_response

        json_str = """
        {
            "steps": [
                {"id": "S1", "type": "requirement_understanding", "claim": "Understand", "related_clauses": ["C1"]},
                {"id": "S2", "type": "constraints", "claim": "Handle empty", "related_clauses": ["C2"]},
                {"id": "S3", "type": "algorithm", "claim": "Use set", "related_clauses": []},
                {"id": "S4", "type": "correctness", "claim": "Set removes dupes", "related_clauses": []},
                {"id": "S5", "type": "complexity", "claim": "O(n) time", "related_clauses": []},
                {"id": "S6", "type": "test_plan", "claim": "Test empty and dupes", "related_clauses": []},
                {"id": "S7", "type": "code", "claim": "Implement", "related_clauses": []}
            ],
            "complexity": {"time": "O(n)", "space": "O(n)"},
            "code": "def f(x):\\n    return list(set(x))"
        }
        """
        solution = parse_solution_response(json_str, task_id="test")
        assert len(solution.steps) == 7
        assert solution.complexity.time == "O(n)"
        assert "set" in solution.code


class TestEvidenceMerger:
    """Test evidence merging logic."""

    def test_merge_deduplication(self):
        from hcp_eval.evaluation.evidence_merger import EvidenceMerger

        merger = EvidenceMerger()
        ev1 = EvidenceRecord(
            source="plus_test", status="contradicted",
            detail="Test failed", target_step="S2",
            error_type=ErrorType.EDGE_CASE_FAILURE, confidence=1.0,
        )
        ev2 = EvidenceRecord(
            source="static_check", status="warning",
            detail="Missing edge case", target_step="S2",
            error_type=ErrorType.CONDITION_MISSING, confidence=0.6,
        )

        merged = merger.merge([[ev1, ev2]])
        # Both have different (step, type, source) so both should remain
        assert len(merged) == 2
        # plus_test should come first (higher priority)
        assert merged[0].source == "plus_test"

    def test_first_error_step(self):
        from hcp_eval.evaluation.evidence_merger import EvidenceMerger

        merger = EvidenceMerger()
        evidence = [
            EvidenceRecord(source="test", status="contradicted", detail="err", target_step="S3", error_type=ErrorType.ALGORITHM_INVALID, confidence=0.9),
            EvidenceRecord(source="test", status="contradicted", detail="err", target_step="S1", error_type=ErrorType.SPEC_MISREAD, confidence=0.9),
        ]
        assert merger.determine_first_error_step(evidence) == "S1"

    def test_unsupported_success_detection(self):
        from hcp_eval.evaluation.evidence_merger import EvidenceMerger
        from hcp_eval.schemas import EvaluationResult

        merger = EvidenceMerger()
        # Correct answer but early contradiction
        result = EvaluationResult(
            task_id="test", dataset="test", final_correct=True,
        )
        evidence = [
            EvidenceRecord(
                source="review", status="contradicted",
                detail="S1 has issues", target_step="S1",
                error_type=ErrorType.SPEC_MISREAD, confidence=0.8,
            ),
        ]
        assert merger.detect_unsupported_success(result, evidence) == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
