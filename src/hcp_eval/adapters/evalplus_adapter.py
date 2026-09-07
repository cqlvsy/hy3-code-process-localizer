"""EvalPlus MBPP+ and HumanEval+ dataset adapter."""

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


class EvalPlusAdapter(BaseAdapter):
    """Adapter for EvalPlus MBPP+ and HumanEval+ datasets.

    Supports loading from:
    1. HuggingFace datasets library (online)
    2. Local JSONL files (offline/pre-downloaded)
    """

    def __init__(
        self,
        dataset_name: str = "mbppplus",
        data_dir: Optional[Path] = None,
        split: str = "test",
    ):
        """
        Args:
            dataset_name: 'mbppplus' or 'humanevalplus'
            data_dir: Local directory containing pre-downloaded .jsonl files
            split: Dataset split to use (typically 'test')
        """
        self.dataset_name = dataset_name
        self.data_dir = data_dir or Path("data")
        self.split = split
        self._problems: Optional[list[ProblemSpec]] = None

    def get_dataset_name(self) -> str:
        return self.dataset_name

    def _find_local_file(self) -> Optional[Path]:
        """Find a local JSONL file for this dataset."""
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

    def _load_from_huggingface(self) -> list[dict]:
        """Load dataset from HuggingFace."""
        try:
            from datasets import load_dataset

            hf_name = (
                "evalplus/mbppplus"
                if self.dataset_name == "mbppplus"
                else "evalplus/humanevalplus"
            )
            logger.info("Loading %s from HuggingFace...", hf_name)
            ds = load_dataset(hf_name, split=self.split)
            return list(ds)
        except ImportError:
            logger.warning(
                "datasets library not installed. Install with: pip install datasets"
            )
            return []
        except Exception as e:
            logger.warning("Failed to load from HuggingFace: %s", e)
            return []

    def _load_from_local(self) -> list[dict]:
        """Load dataset from local JSONL file."""
        local_file = self._find_local_file()
        if not local_file:
            return []

        logger.info("Loading from local file: %s", local_file)
        records = []
        with open(local_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        logger.warning("Skipping malformed line: %s", e)
        return records

    def _extract_clauses(self, prompt: str, entry_point: str) -> list[Clause]:
        """Extract specification clauses from problem text."""
        clauses = []
        # Common patterns to identify clauses
        patterns = [
            # Input constraints
            (r"(?:input|takes?|accepts?)\s+(?:a\s+)?(list|array|string|int|float|str)\s+(?:of\s+)?(\w+)", "Input type constraint"),
            # Output requirements
            (r"(?:return|output|should return)\s+(.+?)(?:\.|$)", "Output requirement"),
            # Edge cases mentioned
            (r"(?:empty|None|null|empty\s+list|empty\s+string|\b0\b|\bnegative\b)", "Edge case"),
            # Uniqueness/deduplication
            (r"(?:unique|distinct|duplicate|without repetition)", "Uniqueness requirement"),
            # Complexity hints
            (r"(?:O\([^)]+\)|linear|logarithmic|constant time)", "Complexity constraint"),
            # Ordering/sorting
            (r"(?:sorted|ascending|descending|order)", "Ordering requirement"),
        ]

        seen_texts = set()
        for i, (pattern, clause_type) in enumerate(patterns, 1):
            matches = re.findall(pattern, prompt, re.IGNORECASE)
            for m in matches:
                text = (f"{m[0]} {m[1]}" if isinstance(m, tuple) and len(m) > 1 else str(m))
                if text not in seen_texts:
                    seen_texts.add(text)
                    clauses.append(
                        Clause(id=f"C{i}", text=f"{clause_type}: {text[:100]}")
                    )

        # Always add a basic functionality clause
        clauses.insert(0, Clause(id="C0", text=f"Function '{entry_point}' must satisfy the problem requirements"))

        return clauses

    def _convert_record(self, record: dict) -> ProblemSpec:
        """Convert a raw dataset record to ProblemSpec."""
        task_id = record.get("task_id", f"{self.dataset_name}/{record.get('task_id', 'unknown')}")

        # Handle different field names between MBPP+ and HumanEval+
        prompt = record.get("prompt") or record.get("text", "")
        entry_point = record.get("entry_point") or record.get("declaration", "").split("(")[0].replace("def ", "") if record.get("declaration") else "solution"
        canonical_solution = record.get("canonical_solution") or record.get("code", "")

        # Tests - handle both base and plus tests
        base_tests = record.get("base_test_list") or record.get("test_list") or []
        plus_tests = record.get("plus_test_list") or record.get("test_list") or []

        # Ensure tests are strings
        base_tests = [t if isinstance(t, str) else str(t) for t in base_tests]
        plus_tests = [t if isinstance(t, str) else str(t) for t in plus_tests]

        # Extract difficulty if available
        difficulty = record.get("difficulty", "medium")

        # Extract clauses
        clauses = self._extract_clauses(prompt, entry_point)

        return ProblemSpec(
            task_id=task_id,
            dataset=self.dataset_name,
            difficulty=difficulty,
            prompt=prompt,
            entry_point=entry_point,
            canonical_solution=canonical_solution,
            base_tests=base_tests,
            plus_tests=plus_tests,
            clauses=clauses,
        )

    def load_problems(self) -> list[ProblemSpec]:
        """Load all problems from the dataset."""
        if self._problems is not None:
            return self._problems

        # Try local first, then HuggingFace
        records = self._load_from_local()
        if not records:
            records = self._load_from_huggingface()

        self._problems = [self._convert_record(r) for r in records]
        logger.info("Loaded %d problems from %s", len(self._problems), self.dataset_name)
        return self._problems

    def sample_problems(self, n: int, seed: int = 42) -> list[ProblemSpec]:
        """Sample n problems reproducibly."""
        problems = self.load_problems()
        if n >= len(problems):
            return problems

        rng = random.Random(seed)
        return rng.sample(problems, n)

    def export_sample(
        self, output_path: Optional[Path] = None, n: int = 30, seed: int = 42
    ) -> Path:
        """Export a sample of problems to a JSONL file for offline use."""
        problems = self.sample_problems(n, seed)
        output_path = output_path or self.data_dir / f"imported_{self.dataset_name}_sample.jsonl"

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for p in problems:
                f.write(p.model_dump_json() + "\n")

        logger.info("Exported %d problems to %s", len(problems), output_path)
        return output_path


def create_adapter(dataset_name: str, data_dir: Optional[Path] = None) -> BaseAdapter:
    """Factory function to create the appropriate adapter."""
    if dataset_name in ("mbppplus", "humanevalplus"):
        return EvalPlusAdapter(dataset_name=dataset_name, data_dir=data_dir)
    raise ValueError(f"Unsupported dataset: {dataset_name}. Use 'mbppplus' or 'humanevalplus'")
