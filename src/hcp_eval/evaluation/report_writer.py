"""Report generation for evaluation results."""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any, Optional

from ..schemas import EvaluationResult, MetricsSummary

logger = logging.getLogger(__name__)


class ReportWriter:
    """Write evaluation reports in multiple formats."""

    def __init__(self, output_dir: Path = Path("results")):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write_csv(self, results: list[EvaluationResult], filename: str = "eval_results.csv") -> Path:
        """Write evaluation results to CSV."""
        path = self.output_dir / filename

        fieldnames = [
            "task_id",
            "dataset",
            "final_correct",
            "base_passed",
            "plus_passed",
            "process_correct",
            "first_error_step",
            "violated_clause",
            "primary_error_type",
            "unsupported_success",
            "total_tests",
            "passed_tests",
            "failed_tests",
            "execution_errors",
            "eval_time_ms",
            "suspect_lines_count",
            "evidence_count",
        ]

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for r in results:
                writer.writerow({
                    "task_id": r.task_id,
                    "dataset": r.dataset,
                    "final_correct": r.final_correct,
                    "base_passed": r.base_passed,
                    "plus_passed": r.plus_passed,
                    "process_correct": r.process_correct,
                    "first_error_step": r.first_error_step or "",
                    "violated_clause": r.violated_clause or "",
                    "primary_error_type": r.primary_error_type.value,
                    "unsupported_success": r.unsupported_success,
                    "total_tests": r.total_tests,
                    "passed_tests": r.passed_tests,
                    "failed_tests": r.failed_tests,
                    "execution_errors": r.execution_errors,
                    "eval_time_ms": r.eval_time_ms or 0,
                    "suspect_lines_count": len(r.suspect_code_lines),
                    "evidence_count": len(r.evidence),
                })

        logger.info("CSV results written to %s (%d rows)", path, len(results))
        return path

    def write_detailed_jsonl(
        self, results: list[EvaluationResult], filename: str = "eval_results.jsonl"
    ) -> Path:
        """Write detailed evaluation results to JSONL."""
        path = self.output_dir / filename

        with open(path, "w", encoding="utf-8") as f:
            for r in results:
                f.write(r.model_dump_json() + "\n")

        logger.info("Detailed JSONL written to %s", path)
        return path

    def write_metrics(self, metrics: MetricsSummary, filename: str = "metrics.json") -> Path:
        """Write metrics summary to JSON."""
        path = self.output_dir / filename

        with open(path, "w", encoding="utf-8") as f:
            f.write(metrics.model_dump_json(indent=2))

        logger.info("Metrics written to %s", path)
        return path

    def write_analysis_report(
        self,
        metrics: MetricsSummary,
        results: list[EvaluationResult],
        filename: str = "analysis_report.md",
    ) -> Path:
        """Generate a comprehensive Markdown analysis report."""
        path = self.output_dir / filename

        lines = [
            "# Hy3 Code Process Evaluation - Analysis Report",
            "",
            f"**Generated:** {metrics.timestamp}",
            f"**Dataset:** {metrics.dataset_name or 'N/A'}",
            f"**Model:** {metrics.model_name}",
            f"**Sample Size:** {metrics.sample_size}",
            "",
            "---",
            "",
            "## 1. Overall Results",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total Problems | {metrics.total_problems} |",
            f"| Final Accuracy | {metrics.final_accuracy:.2%} |",
            f"| Base Pass Rate | {metrics.base_pass_rate:.2%} |",
            f"| Plus Pass Rate | {metrics.plus_pass_rate:.2%} |",
            f"| Process Accuracy | {metrics.process_accuracy:.2%} |",
            f"| Unsupported Success Count | {metrics.unsupported_success_count} |",
            f"| Unsupported Success Rate | {metrics.unsupported_success_rate:.2%} |",
            "",
            "## 2. Error Type Distribution",
            "",
            "| Error Type | Count | Percentage |",
            "|------------|-------|------------|",
        ]

        for et, count in sorted(
            metrics.error_type_distribution.items(), key=lambda x: x[1], reverse=True
        ):
            pct = count / metrics.total_problems * 100 if metrics.total_problems > 0 else 0
            lines.append(f"| `{et}` | {count} | {pct:.1f}% |")

        lines.extend([
            "",
            "## 3. Difficulty Breakdown",
            "",
        ])

        for diff, data in metrics.difficulty_breakdown.items():
            lines.extend([
                f"### {diff.title()} (n={data['count']})",
                "",
                f"- Final Accuracy: **{data['final_accuracy']:.2%}**",
                f"- Process Accuracy: **{data['process_accuracy']:.2%}**",
                "- Common Errors:",
            ])
            for err in data.get("common_errors", []):
                lines.append(f"  - `{err['error_type']}`: {err['count']} occurrences")
            lines.append("")

        # Add validation metrics if available
        if metrics.localization_accuracy is not None:
            lines.extend([
                "## 4. Validation Results",
                "",
                "| Metric | Value |",
                "|--------|-------|",
                f"| Localization Accuracy | {metrics.localization_accuracy:.2%} |",
                f"| False Positive Rate | {metrics.false_positive_rate:.2%} |",
                f"| Error Type Accuracy | {metrics.error_type_accuracy:.2%} |",
                "",
            ])

        # Add per-step error analysis
        step_errors: dict[str, int] = {}
        for r in results:
            if r.first_error_step:
                step_errors[r.first_error_step] = step_errors.get(r.first_error_step, 0) + 1

        if step_errors:
            lines.extend([
                "## 5. First Error Step Distribution",
                "",
                "| Step | Name | Count |",
                "|-------|------|-------|",
            ])
            step_names = {
                "S1": "Requirement Understanding",
                "S2": "Constraints & Edge Cases",
                "S3": "Algorithm Choice",
                "S4": "Correctness Argument",
                "S5": "Complexity Analysis",
                "S6": "Self-Test Plan",
                "S7": "Code Implementation",
            }
            for step in sorted(step_errors.keys()):
                name = step_names.get(step, "Unknown")
                lines.append(f"| {step} | {name} | {step_errors[step]} |")
            lines.append("")

        # Add典型案例
        lines.extend([
            "## 6. Typical Case Analysis",
            "",
            "### Cases with Unsupported Success (Correct Answer, Wrong Process)",
            "",
        ])
        us_cases = [r for r in results if r.unsupported_success]
        if us_cases:
            for r in us_cases[:5]:  # Show up to 5
                lines.extend([
                    f"- **{r.task_id}**: Error at `{r.first_error_step}`, "
                    f"type=`{r.primary_error_type.value}`",
                ])
        else:
            lines.append("- No cases of unsupported success detected.")
        lines.append("")

        # Most common failure patterns
        lines.extend([
            "## 7. Model Capability Boundary Analysis",
            "",
            "### Observed Failure Patterns",
            "",
        ])
        failure_patterns = self._analyze_failure_patterns(results)
        for pattern in failure_patterns:
            lines.append(f"- {pattern}")
        lines.append("")

        lines.extend([
            "---",
            "",
            "*This report was generated by the Hy3 Code Process Localizer.*",
            "*Project: Personal/activity work, not an official Tencent release.*",
            "",
        ])

        report_text = "\n".join(lines)
        path.write_text(report_text, encoding="utf-8")
        logger.info("Analysis report written to %s", path)
        return path

    @staticmethod
    def _analyze_failure_patterns(results: list[EvaluationResult]) -> list[str]:
        """Identify common failure patterns across results."""
        patterns = []

        # Check for systematic issues
        plus_fail_base_pass = sum(
            1 for r in results if r.base_passed and not r.plus_passed
        )
        if plus_fail_base_pass > 0:
            patterns.append(
                f"**Edge case sensitivity**: {plus_fail_base_pass} solutions pass base tests "
                f"but fail on enhanced (plus) tests, suggesting incomplete edge case handling."
            )

        process_fail_answer_correct = sum(
            1 for r in results if not r.process_correct and r.final_correct
        )
        if process_fail_answer_correct > 0:
            patterns.append(
                f"**Correct-by-coincidence**: {process_fail_answer_correct} solutions produce "
                f"correct answers through flawed reasoning processes."
            )

        s1_s2_errors = sum(
            1 for r in results
            if r.first_error_step in ("S1", "S2")
        )
        if s1_s2_errors > 0:
            patterns.append(
                f"**Understanding-level errors**: {s1_s2_errors} errors originate at "
                f"S1 (requirement understanding) or S2 (constraints), indicating potential "
                f"issues with problem comprehension."
            )

        s7_only_errors = sum(
            1 for r in results
            if r.first_error_step == "S7" and r.process_correct
        )
        if s7_only_errors > 0:
            patterns.append(
                f"**Implementation-only errors**: {s7_only_errors} solutions have sound "
                f"reasoning but contain code implementation bugs."
            )

        runtime_errors = sum(1 for r in results if r.execution_errors > 0)
        if runtime_errors > 0:
            patterns.append(
                f"**Runtime exceptions**: {runtime_errors} solutions trigger runtime errors "
                f"during test execution."
            )

        if not patterns:
            patterns.append("No systematic failure patterns identified in current results.")

        return patterns
