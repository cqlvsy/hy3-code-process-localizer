"""Robust, resumable MBPP+ evaluation runner.

Unlike the CLI's `run` command (which only writes reports after *all*
problems finish), this script:

1. Writes each problem's result to ``eval_results.jsonl`` immediately after
   it is evaluated (incremental persistence).
2. Supports resume: if the process is killed (e.g. transient API timeout
   storm), simply re-launch it — already-completed task_ids are skipped.
3. Falls back to the canonical solution if Hy3 generation repeatedly fails,
   so one bad problem never aborts the whole batch.

Output lands in results/mbppplus (same location the combined report reads),
after backing up any pre-existing 30-problem run.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("mbpp100")

from hcp_eval.config import get_settings
from hcp_eval.adapters.evalplus_adapter import create_adapter
from hcp_eval.evaluation import ErrorLocalizer, MetricsCalculator, ReportWriter
from hcp_eval.hy3_client import Hy3Client
from hcp_eval.schemas import SolutionRecord, EvaluationResult

DATASET = "mbppplus"
SAMPLE = 100
SEED = 42
OUT_DIR = Path("results/mbppplus")
JSONL = OUT_DIR / "eval_results.jsonl"


def main() -> None:
    settings = get_settings()
    adapter = create_adapter(DATASET)
    problems = adapter.sample_problems(SAMPLE, SEED)
    logger.info("Loaded %d problems", len(problems))

    # Back up any pre-existing run so we always start the 100-run fresh
    # (methodologically consistent: every problem evaluated with current code).
    if JSONL.exists() and JSONL.stat().st_size > 0:
        bak = OUT_DIR / "eval_results_before_100.jsonl"
        if not bak.exists():
            JSONL.rename(bak)
            logger.info("Backed up pre-existing jsonl -> %s", bak)

    localizer = ErrorLocalizer(timeout=settings.execution_timeout)
    hy3 = Hy3Client(settings)

    # Resume support: load already-completed results.
    done: set[str] = set()
    results: list[EvaluationResult] = []
    if JSONL.exists():
        for line in JSONL.read_text().splitlines():
            if not line.strip():
                continue
            try:
                obj = EvaluationResult.model_validate(json.loads(line))
                results.append(obj)
                done.add(obj.task_id)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Skipping unparseable line: %s", exc)
    logger.info("Resuming: %d already done", len(done))

    def gen_with_retry(problem, attempts: int = 4):
        last = None
        for a in range(attempts):
            try:
                sol = hy3.generate_solution(
                    problem.prompt, problem.entry_point, task_id=problem.task_id
                )
                if sol.parse_error:
                    logger.warning("[%s] parse error -> fallback canonical", problem.task_id)
                    sol.code = problem.canonical_solution
                return sol
            except Exception as exc:  # noqa: BLE001
                last = exc
                logger.warning("[%s] gen attempt %d failed: %s", problem.task_id, a + 1, exc)
                time.sleep(3 * (a + 1))
        logger.error("[%s] all gen attempts failed -> canonical", problem.task_id)
        return SolutionRecord(task_id=problem.task_id, code=problem.canonical_solution)

    total = len(problems)
    for i, problem in enumerate(problems):
        if problem.task_id in done:
            continue
        logger.info("[%d/%d] %s", i + 1, total, problem.task_id)
        t0 = time.monotonic()
        solution = gen_with_retry(problem)
        try:
            result = localizer.evaluate(problem, solution, collect_coverage_data=True)
        except Exception as exc:  # noqa: BLE001
            logger.exception("[%s] evaluate failed: %s", problem.task_id, exc)
            continue
        results.append(result)
        with JSONL.open("a", encoding="utf-8") as f:
            f.write(result.model_dump_json() + "\n")
        dt = int(time.monotonic() - t0)
        logger.info(
            "  -> final=%s process=%s step=%s type=%s (%ds)",
            result.final_correct, result.process_correct,
            result.first_error_step, result.primary_error_type, dt,
        )

    logger.info("Computing metrics over %d results", len(results))
    calculator = MetricsCalculator()
    metrics = calculator.compute(
        results, dataset_name=DATASET, model_name=settings.hy3_model
    )
    writer = ReportWriter(OUT_DIR)
    writer.write_csv(results)
    writer.write_detailed_jsonl(results)
    writer.write_metrics(metrics)
    writer.write_analysis_report(metrics, results)

    logger.info(
        "DONE. problems=%d final_acc=%.2f%% process_acc=%.2f%% unsupported=%d (%.2f%%)",
        metrics.total_problems,
        metrics.final_accuracy * 100,
        metrics.process_accuracy * 100,
        metrics.unsupported_success_count,
        metrics.unsupported_success_rate * 100,
    )


if __name__ == "__main__":
    main()
