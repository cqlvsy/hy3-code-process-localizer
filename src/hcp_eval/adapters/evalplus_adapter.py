"""EvalPlus MBPP+ and HumanEval+ dataset adapter using the official evalplus API."""

from __future__ import annotations

import json
import logging
import random
import re
from pathlib import Path
from typing import Any, Optional

from .base import BaseAdapter
from ..schemas import Clause, ProblemSpec

logger = logging.getLogger(__name__)

# Cap plus tests to keep evaluation runtime feasible while remaining representative.
DEFAULT_MAX_PLUS = 40


class EvalPlusAdapter(BaseAdapter):
    """Adapter for EvalPlus MBPP+ and HumanEval+ datasets.

    Uses the official ``evalplus.data`` API which provides unified access to
    base and plus (augmented) tests for both datasets.
    """

    def __init__(
        self,
        dataset_name: str = "mbppplus",
        data_dir: Optional[Path] = None,
        split: str = "test",
        max_plus: int = DEFAULT_MAX_PLUS,
    ):
        self.dataset_name = dataset_name
        self.data_dir = data_dir or Path("data")
        self.split = split
        self.max_plus = max_plus
        self._problems: Optional[list[ProblemSpec]] = None

    def get_dataset_name(self) -> str:
        return self.dataset_name

    # ------------------------------------------------------------------ #
    # Loading
    # ------------------------------------------------------------------ #

    def _find_local_file(self) -> Optional[Path]:
        if self.dataset_name == "mbppplus":
            candidates = [
                self.data_dir / "imported_mbppplus_sample.jsonl",
                self.data_dir / "mbppplus.jsonl",
            ]
        else:
            candidates = [
                self.data_dir / "imported_humanevalplus_sample.jsonl",
                self.data_dir / "humanevalplus.jsonl",
            ]
        for path in candidates:
            if path.exists():
                return path
        return None

    def load_problems(self) -> list[ProblemSpec]:
        if self._problems is not None:
            return self._problems

        local_file = self._find_local_file()
        if local_file:
            logger.info("Loading %s from local file: %s", self.dataset_name, local_file)
            problems = []
            with open(local_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            problems.append(ProblemSpec.model_validate_json(line))
                        except Exception as e:
                            logger.warning("Skipping malformed line: %s", e)
            self._problems = problems
            return problems

        # Fall back to official evalplus API
        problems = self._load_from_evalplus()
        self._problems = problems
        logger.info("Loaded %d problems from %s", len(problems), self.dataset_name)
        return problems

    def _load_from_evalplus(self) -> list[ProblemSpec]:
        from evalplus.data import get_mbpp_plus, get_human_eval_plus

        if self.dataset_name == "mbppplus":
            raw = get_mbpp_plus()
        else:
            raw = get_human_eval_plus()

        return [self._convert_record(task_id, rec) for task_id, rec in raw.items()]

    # ------------------------------------------------------------------ #
    # Conversion
    # ------------------------------------------------------------------ #

    def _convert_record(self, task_id: str, rec: dict) -> ProblemSpec:
        entry_point = rec.get("entry_point") or "solution"
        canonical_solution = rec.get("canonical_solution") or ""

        # HumanEval+ stores only the function body in canonical_solution; the
        # full definition (signature + docstring) lives in the prompt. Always
        # reconstruct by prepending the prompt (the body may itself start with a
        # nested `def`, so a startswith("def ") heuristic is unreliable).
        if self.dataset_name == "humanevalplus" and canonical_solution.strip():
            canonical_solution = rec.get("prompt", "") + "\n" + canonical_solution

        base_tests, plus_tests, oracle_code = self._build_tests(rec, entry_point, canonical_solution)

        clauses = self._extract_clauses(rec.get("prompt", ""), entry_point)

        return ProblemSpec(
            task_id=task_id,
            dataset=self.dataset_name,
            difficulty="medium",
            prompt=rec.get("prompt", ""),
            entry_point=entry_point,
            canonical_solution=canonical_solution,
            base_tests=base_tests,
            plus_tests=plus_tests,
            clauses=clauses,
            oracle_code=oracle_code,
        )

    def _build_tests(
        self, rec: dict, entry_point: str, canonical_solution: str
    ) -> tuple[list[str], list[str], Optional[str]]:
        """Build base and plus test lists and the renamed oracle code."""
        base_tests: list[str] = []
        plus_tests: list[str] = []

        if self.dataset_name == "mbppplus":
            # Base tests are explicit assertions in the `assertion` field
            assertion = rec.get("assertion", "")
            for line in assertion.splitlines():
                line = line.strip()
                if line.startswith("assert"):
                    base_tests.append(line)
            plus_inputs = rec.get("plus_input", [])
        else:
            # HumanEval+: the `test` field defines a `check(candidate)` function that
            # contains setup assignments AND assert statements. Run it as a single
            # unit (replacing `candidate` with the entry point) so setup state is
            # preserved, then ensure `check` is actually invoked.
            test_field = rec.get("test", "")
            base_test = test_field.replace("candidate", entry_point)
            if "check(" not in base_test.split("def")[-1]:
                base_test = base_test.rstrip() + f"\ncheck({entry_point})\n"
            elif f"check({entry_point})" not in base_test:
                base_test = base_test.rstrip() + f"\ncheck({entry_point})\n"
            base_tests.append(base_test)
            plus_inputs = rec.get("plus_input", [])

        # Build plus tests using canonical solution as oracle
        oracle_code = None
        if plus_inputs and canonical_solution:
            oracle_code = re.sub(
                rf"def\s+{re.escape(entry_point)}\s*\(",
                f"def {entry_point}_oracle(",
                canonical_solution,
            )
            for inp in plus_inputs[: self.max_plus]:
                # inp is a list of positional arguments
                args = ", ".join(repr(a) for a in inp)
                plus_tests.append(
                    f"assert {entry_point}({args}) == {entry_point}_oracle({args})"
                )

        return base_tests, plus_tests, oracle_code

    def _extract_clauses(self, prompt: str, entry_point: str) -> list[Clause]:
        clauses = []
        patterns = [
            (r"(?:input|takes?|accepts?)\s+(?:a\s+)?(list|array|string|int|float|str)\b", "Input type constraint"),
            (r"(?:return|output|should return)\b", "Output requirement"),
            (r"(?:empty|None|null|empty\s+list|empty\s+string|\b0\b|\bnegative\b)", "Edge case"),
            (r"(?:unique|distinct|duplicate|without repetition)", "Uniqueness requirement"),
            (r"(?:O\([^)]+\)|linear|logarithmic|constant time)", "Complexity constraint"),
            (r"(?:sorted|ascending|descending|order)", "Ordering requirement"),
        ]
        seen_texts = set()
        for i, (pattern, clause_type) in enumerate(patterns, 1):
            for m in re.findall(pattern, prompt, re.IGNORECASE):
                text = m if isinstance(m, str) else " ".join(m)
                if text not in seen_texts:
                    seen_texts.add(text)
                    clauses.append(Clause(id=f"C{i}", text=f"{clause_type}: {text[:100]}"))

        clauses.insert(
            0,
            Clause(id="C0", text=f"Function '{entry_point}' must satisfy the problem requirements"),
        )
        return clauses

    # ------------------------------------------------------------------ #
    # Sampling & export
    # ------------------------------------------------------------------ #

    def sample_problems(self, n: int, seed: int = 42) -> list[ProblemSpec]:
        problems = self.load_problems()
        if n >= len(problems):
            return problems
        rng = random.Random(seed)
        return rng.sample(problems, n)

    def export_sample(
        self, output_path: Optional[Path] = None, n: int = 30, seed: int = 42
    ) -> Path:
        problems = self.sample_problems(n, seed)
        output_path = output_path or self.data_dir / f"imported_{self.dataset_name}_sample.jsonl"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for p in problems:
                f.write(p.model_dump_json() + "\n")
        logger.info("Exported %d problems to %s", len(problems), output_path)
        return output_path


def create_adapter(dataset_name: str, data_dir: Optional[Path] = None) -> BaseAdapter:
    if dataset_name in ("mbppplus", "humanevalplus"):
        return EvalPlusAdapter(dataset_name=dataset_name, data_dir=data_dir)
    raise ValueError(f"Unsupported dataset: {dataset_name}. Use 'mbppplus' or 'humanevalplus'")
