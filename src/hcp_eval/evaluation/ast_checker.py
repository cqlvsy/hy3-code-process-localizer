"""AST-based static analysis for candidate code."""

from __future__ import annotations

import ast
import logging
import textwrap
from typing import Any, Optional

from ..schemas import EvidenceRecord, ErrorType

logger = logging.getLogger(__name__)


class ASTChecker:
    """Perform static analysis on Python code using AST."""

    def check(self, code: str, entry_point: str) -> list[EvidenceRecord]:
        """
        Run all AST-based checks on the given code.

        Returns:
            List of evidence records from static analysis.
        """
        evidence = []

        # Parse the code
        try:
            tree = ast.parse(textwrap.dedent(code))
        except SyntaxError as e:
            evidence.append(
                EvidenceRecord(
                    source="static_check",
                    status="contradicted",
                    detail=f"Syntax error in generated code: {e}",
                    target_step="S7",
                    error_type=ErrorType.FORMAT_ERROR,
                    confidence=1.0,
                )
            )
            return evidence

        # Run individual checks
        evidence.extend(self._check_function_exists(tree, entry_point))
        evidence.extend(self._check_function_signature(tree, entry_point))
        evidence.extend(self._check_for_dangerous_patterns(code, tree))
        evidence.extend(self._check_code_structure(tree))

        return evidence

    def _check_function_exists(self, tree: ast.AST, entry_point: str) -> list[EvidenceRecord]:
        """Check that the expected function is defined."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == entry_point:
                return []
        return [
            EvidenceRecord(
                source="static_check",
                status="contradicted",
                detail=f"Expected function '{entry_point}' not found in code",
                target_step="S7",
                error_type=ErrorType.FORMAT_ERROR,
                confidence=1.0,
            )
        ]

    def _check_function_signature(self, tree: ast.AST, entry_point: str) -> list[EvidenceRecord]:
        """Check function signature for common issues."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == entry_point:
                issues = []
                # Check for no parameters (unusual but not always wrong)
                if len(node.args.args) == 0:
                    issues.append("Function takes no parameters")
                # Check for *args/**kwargs without clear reason
                if node.args.vararg or node.args.kwarg:
                    issues.append("Function uses *args or **kwargs which may hide signature issues")

                if issues:
                    return [
                        EvidenceRecord(
                            source="static_check",
                            status="warning",
                            detail=f"Signature observations for '{entry_point}': {'; '.join(issues)}",
                            target_step="S7",
                            confidence=0.5,
                        )
                    ]
                return []
        return []

    def _check_for_dangerous_patterns(self, code: str, tree: ast.AST) -> list[EvidenceRecord]:
        """Check for potentially dangerous or problematic patterns."""
        evidence = []
        dangerous = {
            "eval": "Use of eval() is a security risk",
            "exec": "Use of exec() is a security risk",
            "__import__": "Dynamic import detected",
            "compile": "Use of compile() may indicate dynamic code execution",
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = ""
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr

                if func_name in dangerous:
                    evidence.append(
                        EvidenceRecord(
                            source="static_check",
                            status="warning",
                            detail=dangerous[func_name],
                            target_step="S7",
                            error_type=ErrorType.SECURITY_VIOLATION,
                            confidence=0.7,
                        )
                    )

        return evidence

    def _check_code_structure(self, tree: ast.AST) -> list[EvidenceRecord]:
        """Check overall code structure quality."""
        evidence = []
        function_count = sum(1 for node in ast.walk(tree) if isinstance(node, ast.FunctionDef))
        class_count = sum(1 for node in ast.walk(tree) if isinstance(node, ast.ClassDef))

        if class_count > 0:
            evidence.append(
                EvidenceRecord(
                    source="static_check",
                    status="insufficient",
                    detail=f"Code contains {class_count} class definition(s); expected a simple function",
                    target_step="S3",
                    error_type=ErrorType.ALGORITHM_INVALID,
                    confidence=0.4,
                )
            )

        if function_count > 3:
            evidence.append(
                EvidenceRecord(
                    source="static_check",
                    status="insufficient",
                    detail=f"Code contains {function_count} functions; may indicate over-engineering",
                    target_step="S3",
                    confidence=0.3,
                )
            )

        return evidence
