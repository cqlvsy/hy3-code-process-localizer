"""Robust, resumable HumanEval+ evaluation runner (mirrors run_mbpp100.py).

Uses the FIXED rule_checker (post-complexity/plan-code-mismatch bug fix) so the
process metrics are consistent with the MBPP+100 run. Writes each result
incrementally and supports resume.
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
logger = logging.getLogger("humaneval30")

from hcp_eval.config import get_settings
from hcp_eval.adapters.evalplus_adapter import create_adapter
from hcp_eval.evaluation import ErrorLocalizer, MetricsCalculator, ReportWriter
from hcp_eval.hy3_client import Hy3Client
from hcp_eval.schemas import SolutionRecord, EvaluationResult

DATASET = "humanevalplus"
SAMPLE = 30
SEED = 42
OUT_DIR = Path("results/humanevalplus")
JSONL = OUT_DIR / "eval_results.jsonl"


def main() -> None:
    settings = get_settings()
    adapter = create_adapter(DATASET)
    problems = adapter.sample_problems(SAMPLE, SEED)
    logger.info("Loaded %d problems", len(problems))

    if JSONL.exists() and JSONL.stat().st_size > 0:
        bak = OUT_DIR / "eval_results_before_rerun.jsonl"
        if not bak.exists():
            JSONL.rename(bak)
            logger.info("Backed up pre-existing jsonl -> %s", bak)

    localizer = ErrorLocalizer(timeout=settings.execution_timeout)
    settings.hy3_request_timeout = 180
    settings.hy3_max_retries = 8
    hy3 = Hy3Client(settings)

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

    def gen_with_retry(problem, attempts: int = 8):
        last = None
        for a in range(attempts):
            try:
                sol = hy3.generate_solution(
                    problem.prompt, problem.entry_point, task_id=problem.task_id
                )
                if sol.parse_error:
                    logger.warning("[%s] parse error (attempt %d), retrying", problem.task_id, a + 1)
                    last = ValueError("parse_error")
                    time.sleep(2 * (a + 1))
                    continue
                return sol
            except Exception as exc:  # noqa: BLE001
                last = exc
                logger.warning("[%s] gen attempt %d failed: %s", problem.task_id, a + 1, exc)
                time.sleep(3 * (a + 1))
        logger.error("[%s] all gen attempts failed -> SKIP (will resume later)", problem.task_id)
        return None

    total = len(problems)
    for i, problem in enumerate(problems):
        if problem.task_id in done:
            continue
        logger.info("[%d/%d] %s", i + 1, total, problem.task_id)
        t0 = time.monotonic()
        solution = gen_with_retry(problem)
        if solution is None:
            logger.warning("[%s] generation failed, skipping (not written)", problem.task_id)
            continue
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
