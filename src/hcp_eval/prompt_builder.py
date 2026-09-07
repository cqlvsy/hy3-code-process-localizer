"""Prompt templates for Hy3 Solver and Reviewer."""

from __future__ import annotations

from typing import Any, Optional

SOLVER_SYSTEM_PROMPT = """You are Tencent Hunyuan Hy3 solving a Python function task.

Your job is to produce a complete, well-reasoned solution with explicit process steps.

RULES:
1. Return ONLY valid JSON. No markdown, no code fences, no explanation outside JSON.
2. Do not use external files, network access, or hidden tests.
3. Expose your full reasoning process using exactly these 7 steps:
   - S1 (requirement_understanding): What does the problem ask for? What are the inputs and outputs?
   - S2 (constraints_and_edges): What constraints, edge cases, and boundary conditions exist?
   - S3 (algorithm_choice): What algorithm or approach will you use? Why?
   - S4 (correctness_argument): Why is this approach correct? Provide a brief proof or argument.
   - S5 (complexity_analysis): What is the time and space complexity? Justify briefly.
   - S6 (self_test_plan): What test cases would you run to verify correctness?
   - S7 (code_implementation): The complete, runnable Python function code.

4. Each step MUST include:
   - "id": step identifier ("S1" through "S7")
   - "type": the type name as shown above
   - "claim": your reasoning/analysis/content for this step
   - "related_clauses": list of clause IDs this step addresses (e.g., ["C1", "C2"])

5. Top-level fields required:
   - "steps": array of the 7 step objects
   - "complexity": object with "time" and "space" fields (e.g., {"time": "O(n)", "space": "O(n)"})
   - "code": string containing the complete Python function implementation

6. The code must be a single function matching the entry point name, with no additional code outside it.
"""


def build_solver_prompt(problem_prompt: str, entry_point: str) -> tuple[str, str]:
    """Build system and user prompts for the Hy3 solver."""
    user_prompt = f"""Solve the following Python programming problem.

Entry point function name: {entry_point}

Problem statement:
{problem_prompt}

Return your complete solution as JSON with steps S1-S7, complexity analysis, and code implementation."""
    return SOLVER_SYSTEM_PROMPT, user_prompt


REVIEWER_SYSTEM_PROMPT = """You are Tencent Hunyuan Hy3 reviewing a Python coding solution process.

Your role is to assess the QUALITY OF THE REASONING PROCESS, not just whether tests pass.

PRINCIPLES:
1. Use execution evidence and static analysis as HARD CONSTRAINTS.
2. Never override a deterministic test failure with linguistic argument.
3. Find the EARLIEST process step that becomes invalid.
4. Return ONLY valid JSON. No markdown, no code fences.

For each issue found, provide:
- "source": "hy3_review"
- "status": "contradicted" | "warning" | "insufficient"
- "detail": clear description of the issue
- "target_step": the step ID where the issue originates (S1-S7)
- "target_clause": relevant clause ID if applicable
- "error_type": one of the standard error types
- "confidence": 0.0-1.0

If the process looks correct overall, return an empty issues array."""


def build_reviewer_prompt(
    problem: Any,
    solution: Any,
    eval_result: Any,
    existing_evidence: list,
) -> tuple[str, str]:
    """Build prompts for the Hy3 reviewer."""
    import json

    # Build problem summary
    problem_summary = {
        "task_id": problem.task_id,
        "prompt": problem.prompt[:2000],  # Truncate very long prompts
        "entry_point": problem.entry_point,
        "clauses": [c.model_dump() for c in problem.clauses],
    }

    # Build solution summary (without raw response to save tokens)
    solution_summary = {
        "task_id": solution.task_id,
        "steps": [s.model_dump() for s in solution.steps],
        "complexity": solution.complexity.model_dump(),
        "code": solution.code,
    }

    # Build execution summary
    exec_summary = {
        "final_correct": eval_result.final_correct,
        "base_passed": eval_result.base_passed,
        "plus_passed": eval_result.plus_passed,
        "total_tests": eval_result.total_tests,
        "passed_tests": eval_result.passed_tests,
        "failed_tests": eval_result.failed_tests,
        "execution_errors": eval_result.execution_errors,
    }

    # Build existing evidence summary
    evidence_summary = [e.model_dump() for e in existing_evidence]

    user_prompt = f"""Review the following solution process for correctness.

## Problem
```json
{json.dumps(problem_summary, ensure_ascii=False, indent=2)}
```

## Solution (Hy3 Generated)
```json
{json.dumps(solution_summary, ensure_ascii=False, indent=2)}
```

## Execution Results
```json
{json.dumps(exec_summary, ensure_ascii=False, indent=2)}
```

## Existing Evidence (from static analysis and testing)
```json
{json.dumps(evidence_summary, ensure_ascii=False, indent=2)}
```

Analyze the reasoning process step by step. Identify the earliest step where an error or logical flaw appears.
Return a JSON object with an "issues" array containing your findings."""

    return REVIEWER_SYSTEM_PROMPT, user_prompt
