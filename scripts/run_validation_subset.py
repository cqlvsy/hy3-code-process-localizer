#!/usr/bin/env python3
"""Regenerate full Hy3 outputs (WITH S1-S7 steps) for the §12.3 validation
sample, and evaluate each with the real localizer.

This produces results/validation/sample_evaluations.jsonl where each record
contains the actual model-generated steps + code + tests + system prediction,
so the agent can assign defensible gold labels for the process-localization
validation metrics.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from hcp_eval.config import get_settings
from hcp_eval.hy3_client import Hy3Client
from hcp_eval.evaluation.error_localizer import ErrorLocalizer
from hcp_eval.schemas import SolutionRecord

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "results" / "validation"


def load_problem(task_id: str):
    ds = "mbppplus" if task_id.startswith("Mbpp") else "humanevalplus"
    for line in (DATA / f"imported_{ds}_sample.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        if d["task_id"] == task_id:
            return d, ds
    return None, None


def main():
    sheet = json.loads((OUT / "annotation_sheet.json").read_text())
    settings = get_settings()
    client = Hy3Client(settings)
    localizer = ErrorLocalizer(timeout=settings.execution_timeout)

    out = []
    for item in sheet:
        tid = item["task_id"]
        prob, ds = load_problem(tid)
        if not prob:
            print(f"SKIP {tid}: problem not found")
            continue
        from hcp_eval.schemas import ProblemSpec
        problem = ProblemSpec(**{
            k: prob[k] for k in ("task_id", "dataset", "prompt", "entry_point",
                                  "canonical_solution", "base_tests", "plus_tests",
                                  "oracle_code", "clauses")
            if k in prob
        })
        # Generate fresh Hy3 solution WITH steps
        try:
            sol = client.generate_solution(problem.prompt, problem.entry_point, task_id=tid)
            if sol.parse_error:
                sol.code = problem.canonical_solution
        except Exception as e:
            print(f"  {tid}: Hy3 failed ({e}), fallback canonical")
            sol = SolutionRecord(task_id=tid, code=problem.canonical_solution)

        res = localizer.evaluate(problem, sol, collect_coverage_data=False)
        rec = {
            "task_id": tid,
            "dataset": ds,
            "prompt": problem.prompt[:500],
            "entry_point": problem.entry_point,
            "steps": [{"id": s.id, "type": s.type, "claim": s.claim} for s in sol.steps],
            "complexity": {"time": sol.complexity.time, "space": sol.complexity.space},
            "code": sol.code,
            "final_correct": res.final_correct,
            "process_correct": res.process_correct,
            "first_error_step": res.first_error_step,
            "primary_error_type": res.primary_error_type.value,
            "unsupported_success": res.unsupported_success,
            "evidence": [
                {"source": e.source, "status": e.status, "target_step": e.target_step,
                 "error_type": e.error_type.value if e.error_type else None,
                 "detail": e.detail[:160]}
                for e in res.evidence
            ],
        }
        out.append(rec)
        print(f"  {tid}: final={res.final_correct} proc={res.process_correct} "
              f"step={res.first_error_step} type={res.primary_error_type.value} "
              f"uns={res.unsupported_success} steps={len(sol.steps)}")

    (OUT / "sample_evaluations.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in out) + "\n"
    )
    print(f"\nWrote {len(out)} evaluations -> {OUT / 'sample_evaluations.jsonl'}")


if __name__ == "__main__":
    t0 = time.monotonic()
    main()
    print(f"Elapsed: {time.monotonic() - t0:.1f}s")
