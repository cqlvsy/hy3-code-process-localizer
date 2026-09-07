"""Base adapter interface for dataset loading."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator

from ..schemas import ProblemSpec


class BaseAdapter(ABC):
    """Abstract base class for dataset adapters."""

    @abstractmethod
    def load_problems(self) -> list[ProblemSpec]:
        """Load all problems from the dataset."""
        ...

    @abstractmethod
    def sample_problems(self, n: int, seed: int = 42) -> list[ProblemSpec]:
        """Sample n problems from the dataset reproducibly."""
        ...

    @abstractmethod
    def get_dataset_name(self) -> str:
        """Return the dataset identifier string."""
        ...
