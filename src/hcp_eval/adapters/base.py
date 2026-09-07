"""Base adapter interface for dataset loaders."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from ..schemas import ProblemSpec


class BaseAdapter(ABC):
    """Abstract base class for all dataset adapters."""

    @abstractmethod
    def get_dataset_name(self) -> str:
        """Return the canonical dataset name (e.g., 'mbppplus')."""
        ...

    @abstractmethod
    def load_problems(self) -> list[ProblemSpec]:
        """Load all problems from the dataset source."""
        ...

    @abstractmethod
    def sample_problems(self, n: int, seed: int = 42) -> list[ProblemSpec]:
        """Sample n problems reproducibly."""
        ...

    def export_sample(
        self, output_path: Optional[Path] = None, n: int = 30, seed: int = 42
    ) -> Path:
        """
        Export a sample of problems to a JSONL file for offline use.

        Subclasses should override this if they have custom export needs,
        but the default implementation works for most cases.
        """
        problems = self.sample_problems(n, seed)
        output_path = output_path or Path("data") / f"imported_{self.get_dataset_name()}_sample.jsonl"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            for p in problems:
                f.write(p.model_dump_json() + "\n")

        return output_path
