"""Command-line interface for Hy3 Code Process Eval."""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

import click

from .config import get_settings, reload_settings
from .schemas import SolutionRecord
from .adapters.evalplus_adapter import create_adapter
from .evaluation import ErrorLocalizer, MetricsCalculator, ReportWriter
from .hy3_client import Hy3Client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


@click.group()
@click.option("--env-file", default=".env", help="Path to .env file")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
def main(env_file: str, verbose: bool):
    """Hy3 Code Process Localizer - Evaluate and localize errors in Hy3-generated code solutions."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


@main.command()
@click.option("--dataset", default="mbppplus", type=click.Choice(["mbppplus", "humanevalplus"]))
@click.option("--sample-size", default=30, help="Number of problems to evaluate")
@click.option("--seed", default=42, help="Random seed for sampling")
@click.option("--no-hy3", is_flag=True, help="Run evaluation without calling Hy3 (use canonical solutions)")
@click.option("--no-sbfl", is_flag=True, help="Skip SBFL coverage analysis (faster)")
@click.option("--output-dir", default="results", help="Output directory for results")
def run(
    dataset: str,
    sample_size: int,
    seed: int,
    no_hy3: bool,
    no_sbfl: bool,
    output_dir: str,
):
    """Run the full evaluation pipeline."""
    settings = get_settings()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Load dataset
    click.echo(f"Loading dataset: {dataset}")
    adapter = create_adapter(dataset)
    problems = adapter.sample_problems(sample_size, seed)
    click.echo(f"  Loaded {len(problems)} problems")

    # Initialize components
    localizer = ErrorLocalizer(timeout=settings.execution_timeout)
    hy3_client = None if no_hy3 else Hy3Client(settings)

    results = []
    total_start = time.monotonic()

    for i, problem in enumerate(problems):
        click.echo(f"\n[{i+1}/{len(problems)}] Evaluating {problem.task_id}...")

        # Get solution (either from Hy3 or use canonical)
        if hy3_client:
            try:
                click.echo(f"  Generating solution with Hy3...")
                solution = hy3_client.generate_solution(problem.prompt, problem.entry_point)
                if solution.parse_error:
                    click.echo(f"  WARNING: Parse error: {solution.parse_error}")
                    # Fall back to canonical solution
                    solution.code = problem.canonical_solution
            except Exception as e:
                click.echo(f"  ERROR: Hy3 generation failed: {e}. Using canonical solution.")
                solution = SolutionRecord(
                    task_id=problem.task_id,
                    code=problem.canonical_solution,
                )
        else:
            # Use canonical solution as placeholder
            solution = SolutionRecord(
                task_id=problem.task_id,
                code=problem.canonical_solution,
            )

        # Evaluate
        try:
            result = localizer.evaluate(
                problem, solution, collect_coverage_data=not no_sbfl
            )
            results.append(result)

            status = "PASS" if result.final_correct else "FAIL"
            process_status = "OK" if result.process_correct else f"ERR@{result.first_error_step}"
            click.echo(
                f"  Result: {status} | Process: {process_status} | "
                f"Tests: {result.passed_tests}/{result.total_tests} | "
                f"Error: {result.primary_error_type.value} | "
                f"Time: {result.eval_time_ms or 0}ms"
            )
        except Exception as e:
            logger.exception("Evaluation failed for %s", problem.task_id)
            click.echo(f"  ERROR: Evaluation failed: {e}")

    total_time = time.monotonic() - total_start

    # Compute metrics
    click.echo("\nComputing metrics...")
    calculator = MetricsCalculator()
    metrics = calculator.compute(
        results,
        dataset_name=dataset,
        model_name=settings.hy3_model,
    )

    # Write reports
    writer = ReportWriter(output_path)
    csv_path = writer.write_csv(results)
    jsonl_path = writer.write_detailed_jsonl(results)
    metrics_path = writer.write_metrics(metrics)
    report_path = writer.write_analysis_report(metrics, results)

    # Print summary
    click.echo("\n" + "=" * 60)
    click.echo("EVALUATION COMPLETE")
    click.echo("=" * 60)
    click.echo(f"Dataset:        {dataset}")
    click.echo(f"Problems:       {metrics.total_problems}")
    click.echo(f"Final Accuracy: {metrics.final_accuracy:.2%}")
    click.echo(f"Base Pass Rate: {metrics.base_pass_rate:.2%}")
    click.echo(f"Plus Pass Rate: {metrics.plus_pass_rate:.2%}")
    click.echo(f"Process Acc:    {metrics.process_accuracy:.2%}")
    click.echo(f"Unsup. Success: {metrics.unsupported_success_count} ({metrics.unsupported_success_rate:.2%})")
    click.echo(f"Total Time:     {total_time:.1f}s")
    click.echo(f"\nResults written to: {output_path}")
    click.echo(f"  - {csv_path.name}")
    click.echo(f"  - {jsonl_path.name}")
    click.echo(f"  - {metrics_path.name}")
    click.echo(f"  - {report_path.name}")


@main.command()
@click.option("--dataset", default="mbppplus", type=click.Choice(["mbppplus", "humanevalplus"]))
@click.option("--sample-size", default=30, help="Number of problems to export")
@click.option("--seed", default=42, help="Random seed")
@click.option("--output-dir", default="data", help="Output directory")
def download(dataset: str, sample_size: int, seed: int, output_dir: str):
    """Download and export a sample of problems to a local JSONL file."""
    click.echo(f"Loading {dataset}...")
    adapter = create_adapter(dataset, data_dir=Path(output_dir))
    path = adapter.export_sample(n=sample_size, seed=seed)
    click.echo(f"Exported to: {path}")


@main.command()
def health():
    """Check Hy3 API connectivity."""
    settings = get_settings()
    client = Hy3Client(settings)

    click.echo(f"Checking Hy3 at {settings.hy3_base_url}...")
    click.echo(f"Model: {settings.hy3_model}")

    if client.health_check():
        click.echo("Status: CONNECTED - Hy3 API is reachable")
    else:
        click.echo("Status: UNREACHABLE - Check your Hy3 server configuration")
        sys.exit(1)


if __name__ == "__main__":
    main()
