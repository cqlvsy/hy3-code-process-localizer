#!/usr/bin/env python3
"""Recompute per-dataset and combined reports using the NEW difficulty heuristic.

This script does NOT call any API.  It re-derives difficulty labels from dataset
features (plus-test count, prompt length, solution complexity), patches the
cached eval_results.jsonl records, then regenerates:

  - results/<dataset>/metrics.json
  - results/<dataset>/analysis_report.md
  - results/combined_report.md

Usage:
    python scripts/recompute_with_difficulty.py
"""
import json
import logging
import sys
from pathlib import Path

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hcp_eval.adapters.evalplus_adapter import EvalPlusAdapter, create_adapter
from hcp_eval.evaluation import ErrorLocalizer, MetricsCalculator, ReportWriter
from hcp_eval.schemas import EvaluationResult

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

DATASETS = ["mbppplus", "humanevalplus"]


def load_results(jsonl_path: Path) -> list[EvaluationResult]:
    """Load cached evaluation results from JSONL."""
    results: list[EvaluationResult] = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                results.append(EvaluationResult.model_validate_json(line))
    logger.info("Loaded %d results from %s", len(results), jsonl_path)
    return results


def build_difficulty_map(dataset_name: str) -> dict[str, str]:
    """Load dataset via (new) adapter and return {task_id: difficulty}."""
    adapter = create_adapter(dataset_name)
    problems = adapter.load_problems()
    return {p.task_id: p.difficulty for p in problems}


def recompute_dataset(dataset_name: str):
    """Recompute one dataset's metrics & reports with new difficulty."""
    out_dir = ROOT / "results" / dataset_name
    jsonl_path = out_dir / "eval_results.jsonl"
    if not jsonl_path.exists():
        logger.warning("No %s — skipping", jsonl_path)
        return

    # 1. Build id→difficulty from dataset (new heuristic)
    diff_map = build_difficulty_map(dataset_name)
    dist_counts: dict[str, int] = {}
    for d in diff_map.values():
        dist_counts[d] = dist_counts.get(d, 0) + 1
    logger.info(
        "%s difficulty distribution: %s",
        dataset_name,
        dict(sorted(dist_counts.items())),
    )

    # 2. Load cached results
    results = load_results(jsonl_path)

    # 3. Pass difficulty_map to metrics (EvaluationResult has no difficulty field)
    logger.info(
        "%s: using difficulty_map with %d entries",
        dataset_name,
        len(diff_map),
    )

    # 4. Recompute metrics
    calc = MetricsCalculator()
    metrics = calc.compute(
        results,
        dataset_name=dataset_name,
        model_name="hy3",
        difficulty_map=diff_map,
    )
    calc.save_metrics(metrics, str(out_dir / "metrics.json"))
    logger.info("%s: wrote metrics.json", dataset_name)

    # 5. Recompute analysis report
    writer = ReportWriter(output_dir=out_dir)
    writer.write_analysis_report(metrics, results)
    logger.info("%s: wrote analysis_report.md", dataset_name)

    # Also rewrite CSV (includes difficulty column if present)
    writer.write_csv(results)


def main():
    for ds in DATASETS:
        recompute_dataset(ds)

    # Regenerate combined report
    combined_script = ROOT / "scripts" / "make_combined_report.py"
    if combined_script.exists():
        import subprocess

        logger.info("Regenerating combined_report.py ...")
        subprocess.run(
            [sys.executable, str(combined_script)],
            cwd=str(ROOT),
            check=True,
        )
        logger.info("Done.")


if __name__ == "__main__":
    main()
