#!/usr/bin/env python3
"""Build an agent-annotation sheet for the §12.3 process-localization validation.

Samples a STRATIFIED subset of the 60 real Hy3 outputs (final correct &
process correct / final correct & process wrong / final wrong), joins each with
its problem prompt + tests, and emits a compact sheet the agent reads to assign
gold labels. This is NOT independent human annotation; it is agent annotation,
explicitly disclosed in the report.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RESULTS = ROOT / "results"


def load_problems(dataset: str) -> dict:
    path = DATA / f"imported_{dataset}_sample.jsonl"
    out = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        out[d["task_id"]] = d
    return out


def main():
    problems = {}
    problems.update(load_problems("mbppplus"))
    problems.update(load_problems("humanevalplus"))

    # Load all 60 real Hy3 evaluation outputs
    outputs = []
    for ds in ("mbppplus", "humanevalplus"):
        p = RESULTS / ds / "eval_results.jsonl"
        for line in p.read_text().splitlines():
            if line.strip():
                outputs.append(json.loads(line))

    # Stratify
    clean, unsupp, fwrong = [], [], []
    for o in outputs:
        fc, pc = o["final_correct"], o["process_correct"]
        if fc and pc:
            clean.append(o)
        elif fc and not pc:
            unsupp.append(o)
        else:
            fwrong.append(o)

    # Deterministic stratified sample
    def take(lst, n):
        if len(lst) <= n:
            return lst
        step = len(lst) / n
        return [lst[int(i * step)] for i in range(n)]

    sample = take(clean, 5) + take(unsupp, 6) + take(fwrong, 3)
    # sample = 14

    sheet = []
    for o in sample:
        tid = o["task_id"]
        prob = problems.get(tid, {})
        # Extract step claims
        steps = []
        for s in (o.get("steps") or []):
            steps.append({
                "id": s.get("id"),
                "claim": (s.get("claim") or "")[:200],
            })
        # Test summary
        ev = o.get("evidence") or []
        fail_tests = [e for e in ev if e.get("source") in ("base_test", "plus_test") and e.get("status") == "contradicted"]
        sheet.append({
            "task_id": tid,
            "dataset": o["dataset"],
            "prompt": (prob.get("prompt") or "")[:400],
            "entry_point": prob.get("entry_point"),
            "final_correct": o["final_correct"],
            "process_correct": o["process_correct"],
            "first_error_step": o["first_error_step"],
            "primary_error_type": o["primary_error_type"],
            "unsupported_success": o["unsupported_success"],
            "failed_tests": [f"{e.get('source')}: {e.get('detail','')[:120]}" for e in fail_tests][:3],
            "steps": steps,
            "code": (o.get("code") or prob.get("canonical_solution") or "")[:600],
        })

    out_path = RESULTS / "validation" / "annotation_sheet.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(sheet, indent=2, ensure_ascii=False))
    print(f"Wrote {len(sheet)} annotation sheets -> {out_path}")
    print(f"  clean={len(clean)} unsupp={len(unsupp)} fwrong={len(fwrong)}")


if __name__ == "__main__":
    main()
