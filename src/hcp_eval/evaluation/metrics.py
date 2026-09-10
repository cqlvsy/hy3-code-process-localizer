"""Metrics computation and aggregation."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from ..schemas import (
    ErrorType,
    EvaluationResult,
    MetricsSummary,
)

logger = logging.getLogger(__name__)


class MetricsCalculator:
    """Compute aggregated metrics from evaluation results."""

    def compute(self, results: list[EvaluationResult], **kwargs) -> MetricsSummary:
        """
        Compute full metrics summary from a list of evaluation results.

        Args:
            results: List of per-problem evaluation results.
            **kwargs: Additional metadata (dataset_name, model_name, etc.)

        Returns:
            MetricsSummary with all computed metrics.
        """
        n = len(results)
        if n == 0:
            return MetricsSummary(timestamp=datetime.now(timezone.utc).isoformat())

        # Basic accuracy metrics
        final_correct = sum(1 for r in results if r.final_correct)
        base_passed = sum(1 for r in results if r.base_passed)
        plus_passed = sum(1 for r in results if r.plus_passed)
        process_correct = sum(1 for r in results if r.process_correct)
        unsupported_success = sum(1 for r in results if r.unsupported_success)

        # Error type distribution
        error_dist: dict[str, int] = {}
        for r in results:
            et = r.primary_error_type.value
            error_dist[et] = error_dist.get(et, 0) + 1

        # Difficulty breakdown
        difficulty_breakdown = self._compute_difficulty_breakdown(
            results, difficulty_map=kwargs.get("difficulty_map")
        )

        # Per-step error distribution
        step_error_dist: dict[str, int] = {}
        for r in results:
            if r.first_error_step:
                step_error_dist[r.first_error_step] = (
                    step_error_dist.get(r.first_error_step, 0) + 1
                )

        return MetricsSummary(
            total_problems=n,
            final_accuracy=round(final_correct / n, 4),
            base_pass_rate=round(base_passed / n, 4),
            plus_pass_rate=round(plus_passed / n, 4),
            process_accuracy=round(process_correct / n, 4),
            unsupported_success_count=unsupported_success,
            unsupported_success_rate=round(unsupported_success / n, 4) if n > 0 else 0.0,
            error_type_distribution=error_dist,
            difficulty_breakdown=difficulty_breakdown,
            dataset_name=kwargs.get("dataset_name", ""),
            sample_size=n,
            model_name=kwargs.get("model_name", "hy3"),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def _compute_difficulty_breakdown(
        self, results: list[EvaluationResult], difficulty_map: dict[str, str] | None = None
    ) -> dict[str, dict[str, Any]]:
        """Break down results by difficulty level."""
        by_difficulty: dict[str, list[EvaluationResult]] = {}
        for r in results:
            if difficulty_map:
                diff = difficulty_map.get(r.task_id, "medium")
            else:
                diff = getattr(r, "difficulty", "medium")
            if diff not in by_difficulty:
                by_difficulty[diff] = []
            by_difficulty[diff].append(r)

        breakdown = {}
        for diff, group in sorted(by_difficulty.items()):
            n = len(group)
            breakdown[diff] = {
                "count": n,
                "final_accuracy": round(sum(1 for g in group if g.final_correct) / n, 4)
                if n > 0
                else 0.0,
                "process_accuracy": round(
                    sum(1 for g in group if g.process_correct) / n, 4
                )
                if n > 0
                else 0.0,
                "common_errors": self._top_errors(group, 3),
            }
        return breakdown

    @staticmethod
    def _top_errors(results: list[EvaluationResult], top_n: int = 3) -> list[dict]:
        """Find the most common error types in a result group."""
        counts: dict[str, int] = {}
        for r in results:
            et = r.primary_error_type.value
            counts[et] = counts.get(et, 0) + 1

        sorted_errors = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return [{"error_type": et, "count": c} for et, c in sorted_errors[:top_n]]

    def compute_validation_metrics(
        self,
        results: list[EvaluationResult],
        ground_truth: list[dict],
    ) -> dict[str, Any]:
        """
        Compute validation metrics against ground truth annotations.

        Args:
            results: Evaluation results from the system.
            ground_truth: List of dicts with expected values for each problem.

        Returns:
            Dict with localization_accuracy, false_positive_rate, etc.
        """
        if len(results) != len(ground_truth):
            logger.warning(
                "Results count (%d) != ground truth count (%d)",
                len(results),
                len(ground_truth),
            )
            min_len = min(len(results), len(ground_truth))
            results = results[:min_len]
            ground_truth = ground_truth[:min_len]

        correct_localization = 0
        total_with_errors = 0
        false_positives = 0
        total_correct_answers = 0
        correct_error_types = 0
        total_error_classifications = 0

        for result, gt in zip(results, ground_truth):
            expected_first_error = gt.get("expected_first_error_step")
            expected_process_correct = gt.get("expected_process_correct", True)
            expected_error_type = gt.get("expected_error_type")

            # Localization accuracy (on samples where there IS an error)
            if not expected_process_correct:
                total_with_errors += 1
                if result.first_error_step == expected_first_error:
                    correct_localization += 1

            # False positive rate (on actually-correct processes)
            if expected_process_correct:
                total_correct_answers += 1
                if not result.process_correct:
                    false_positives += 1

            # Error type accuracy
            if expected_error_type:
                total_error_classifications += 1
                if result.primary_error_type.value == expected_error_type:
                    correct_error_types += 1

        return {
            "localization_accuracy": (
                round(correct_localization / total_with_errors, 4)
                if total_with_errors > 0
                else None
            ),
            "false_positive_rate": (
                round(false_positives / total_correct_answers, 4)
                if total_correct_answers > 0
                else None
            ),
            "error_type_accuracy": (
                round(correct_error_types / total_error_classifications, 4)
                if total_error_classifications > 0
                else None
            ),
            "total_validated": len(results),
            "samples_with_errors": total_with_errors,
            "correct_samples": total_correct_answers,
        }

    def save_metrics(self, metrics: MetricsSummary, path: str) -> None:
        """Save metrics to a JSON file."""
        with open(path, "w", encoding="utf-8") as f:
            f.write(metrics.model_dump_json(indent=2))
        logger.info("Metrics saved to %s", path)
