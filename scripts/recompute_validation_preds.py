"""Recompute §12.3 validation predictions with the (fixed) static/rule checkers.

The 13 validation samples were generated earlier with a buggy static checker
that over-fired COMPLEXITY_MISCLAIM / PLAN_CODE_MISMATCH on clean solutions.
Because the bug lives entirely in the static/rule layer (no Hy3 call or test
execution is involved), we can recompute predictions by:

  1. rebuilding each SolutionRecord from the *stored* code / steps / complexity;
  2. re-running ASTChecker + RuleChecker (now fixed) to obtain fresh evidence;
  3. merging that with the *stored* test evidence (plus_test / base_test / sbfl);
  4. re-deriving process_correct / first_error_step / primary_error_type /
     unsupported_success via the EvidenceMerger.

No API calls are made, so this is fast and deterministic.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from hcp_eval.schemas import (
    ComplexityClaim,
    EvaluationResult,
    EvidenceRecord,
    ProcessStep,
    SolutionRecord,
)
from hcp_eval.evaluation import ASTChecker, RuleChecker, EvidenceMerger

VAL = Path("results/validation")
SRC = VAL / "sample_evaluations.jsonl"


def main() -> None:
    # Keep the buggy predictions around for transparency.
    buggy = VAL / "_sample_evaluations_buggy.jsonl"
    if not buggy.exists():
        shutil.copy(SRC, buggy)
        print(f"backed up buggy predictions -> {buggy}")

    recs = [json.loads(l) for l in SRC.read_text().splitlines() if l.strip()]

    ast_chk = ASTChecker()
    rule_chk = RuleChecker()
    merger = EvidenceMerger()

    out = []
    for rec in recs:
        sol = SolutionRecord(
            task_id=rec["task_id"],
            steps=[
                ProcessStep(id=s["id"], type=s["type"], claim=s["claim"])
                for s in rec.get("steps", [])
            ],
            complexity=ComplexityClaim(
                time=rec.get("complexity", {}).get("time", "unknown"),
                space=rec.get("complexity", {}).get("space", "unknown"),
            ),
            code=rec["code"],
        )

        fresh: list[EvidenceRecord] = []
        fresh += ast_chk.check(sol.code, rec.get("entry_point") or "f")
        fresh += rule_chk.run_all_checks(sol)

        # Preserve the stored NON-static evidence (test / sbfl results).
        stored_nonstatic = [
            EvidenceRecord(**e)
            for e in rec.get("evidence", [])
            if e.get("source") != "static_check"
        ]

        merged = merger.merge([fresh, stored_nonstatic])
        first_step = merger.determine_first_error_step(merged)
        ptype = merger.determine_primary_error_type(merged)
        temp = EvaluationResult(
            task_id=rec["task_id"],
            dataset=rec["dataset"],
            final_correct=rec["final_correct"],
        )
        unsup = merger.detect_unsupported_success(temp, merged)
        process_correct = first_step is None

        new_rec = dict(rec)
        new_rec["process_correct"] = process_correct
        new_rec["first_error_step"] = first_step
        new_rec["primary_error_type"] = ptype.value if ptype else "UNKNOWN"
        new_rec["unsupported_success"] = unsup
        new_rec["evidence"] = [e.model_dump() for e in merged]
        out.append(new_rec)

        print(
            f"{rec['task_id']:18s} final={rec['final_correct']!s:5s} "
            f"process={process_correct!s:5s} step={first_step} "
            f"type={new_rec['primary_error_type']} unsup={unsup}"
        )

    SRC.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in out) + "\n")
    print(f"\nwrote {len(out)} recomputed predictions -> {SRC}")


if __name__ == "__main__":
    main()
