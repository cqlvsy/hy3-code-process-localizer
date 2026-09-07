"""Code utilities for normalizing and preparing candidate code for execution."""

from __future__ import annotations

import ast
import re
from typing import Optional


def get_defined_function_name(code: str) -> Optional[str]:
    """Return the name of the first top-level function defined in the code."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None

    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            return node.name
    return None


def normalize_function_name(code: str, entry_point: str) -> str:
    """
    Ensure the candidate code defines a function named ``entry_point``.

    - If ``entry_point`` is already among the defined top-level functions, the
      code is returned unchanged (handles solutions with helper functions).
    - If exactly one top-level function is defined (with a different name),
      rename it to ``entry_point`` so dataset tests will execute correctly.
    - If multiple functions are defined but none match ``entry_point``, rename
      the first one as a best-effort fallback.

    Returns the (possibly modified) code.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code

    defined = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
    if not defined:
        return code  # No function found; execution will fail naturally
    if entry_point in defined:
        return code  # Already correctly named (helper functions may also exist)

    # Rename the first defined function to the expected entry point
    return re.sub(
        rf"def\s+{re.escape(defined[0])}\s*\(",
        f"def {entry_point}(",
        code,
    )


def prepare_function_code(
    solution_code: str, entry_point: str, oracle_code: Optional[str] = None
) -> str:
    """
    Build the complete executable code for running tests against a candidate.

    - Normalizes the candidate function name to ``entry_point``.
    - If ``oracle_code`` is provided (for plus tests), appends the renamed
      canonical oracle so plus assertions can compare candidate vs oracle.
    """
    normalized = normalize_function_name(solution_code, entry_point)
    if oracle_code:
        return normalized + "\n\n" + oracle_code + "\n"
    return normalized
