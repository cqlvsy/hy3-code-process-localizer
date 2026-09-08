#!/usr/bin/env python3
"""Run the adversarial validation set (§12.4) against the ErrorLocalizer.

Each case in data/adversarial_set.json has a ground-truth label (gold) known
by construction. We run the real evaluation pipeline on each crafted
solution and compare predictions to gold, then report detection accuracy,
first-error-step accuracy, error-type accuracy, false-positive rate, and
unsupported-success recall/precision.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from hcp_eval.schemas import (
    ProblemSpec,
    SolutionRecord,
    ProcessStep,
    ComplexityClaim,
)
from hcp_eval.evaluation.error_localizer import ErrorLocalizer

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "adversarial_set.json"
OUT_DIR = ROOT / "results" / "validation"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_cases():
    return json.loads(DATA.read_text())


def run_one(case: dict):
    sol = case["solution"]
    steps = [
        ProcessStep(
            id=s["id"], type=s["type"], claim=s["claim"],
            related_clauses=s.get("related_clauses", []),
        )
        for s in sol["steps"]
    ]
    solution = SolutionRecord(
        task_id=case["case_id"],
        steps=steps,
        complexity=ComplexityClaim(
            time=sol["complexity"].get("time", "unknown"),
            space=sol["complexity"].get("space", "unknown"),
        ),
        code=sol["code"],
    )
    problem = ProblemSpec(
        task_id=case["case_id"],
        dataset="adversarial",
        prompt=case["problem"]["prompt"],
        entry_point=case["problem"]["entry_point"],
        canonical_solution=case["problem"]["canonical_solution"],
        base_tests=case["base_tests"],
        plus_tests=[],
        clauses=[],
    )
    el = ErrorLocalizer(timeout=30)
    res = el.evaluate(problem, solution, collect_coverage_data=False)
    return res


def main():
    cases = load_cases()
    rows = []
    for case in cases:
        res = run_one(case)
        gold = case["gold"]
        pred = {
            "final_correct": res.final_correct,
            "process_correct": res.process_correct,
            "first_error_step": res.first_error_step,
            "primary_error_type": res.primary_error_type.value,
            "unsupported_success": res.unsupported_success,
        }
        # Build per-evidence summary for the report
        ev_summary = [
            {"source": e.source, "status": e.status, "target_step": e.target_step,
             "error_type": e.error_type.value if e.error_type else None,
             "detail": e.detail[:160]}
            for e in res.evidence
        ]
        rows.append({
            "case_id": case["case_id"],
            "category": case["category"],
            "flaw": case["flaw"],
            "gold": gold,
            "pred": pred,
            "evidence": ev_summary,
        })

    # ---- Metrics ----
    n = len(rows)
    process_match = sum(1 for r in rows if r["pred"]["process_correct"] == r["gold"]["process_correct"])
    # First-error-step accuracy (only where gold step is not None)
    fes_cases = [r for r in rows if r["gold"]["first_error_step"] is not None]
    fes_match = sum(1 for r in fes_cases if r["pred"]["first_error_step"] == r["gold"]["first_error_step"])
    # Error-type accuracy (only where gold type != UNKNOWN)
    et_cases = [r for r in rows if r["gold"]["primary_error_type"] != "UNKNOWN"]
    et_match = sum(1 for r in et_cases if r["pred"]["primary_error_type"] == r["gold"]["primary_error_type"])
    # FPR over negatives (gold: process_correct True AND unsupported False)
    negatives = [r for r in rows if r["gold"]["process_correct"] and not r["gold"]["unsupported_success"]]
    fp = sum(1 for r in negatives if not r["pred"]["process_correct"])
    fpr = fp / len(negatives) if negatives else 0.0
    # Unsupported-success recall / precision
    us_gold_pos = [r for r in rows if r["gold"]["unsupported_success"]]
    us_pred_pos = [r for r in rows if r["pred"]["unsupported_success"]]
    us_recall = sum(1 for r in us_gold_pos if r["pred"]["unsupported_success"]) / len(us_gold_pos) if us_gold_pos else 0.0
    us_precision = sum(1 for r in us_pred_pos if r["gold"]["unsupported_success"]) / len(us_pred_pos) if us_pred_pos else 0.0

    metrics = {
        "n_cases": n,
        "process_error_detection_accuracy": process_match / n,
        "first_error_step_accuracy": fes_match / len(fes_cases) if fes_cases else None,
        "error_type_accuracy": et_match / len(et_cases) if et_cases else None,
        "false_positive_rate": fpr,
        "unsupported_success_recall": us_recall,
        "unsupported_success_precision": us_precision,
        "breakdown": {
            "first_error_step": {"matched": fes_match, "total": len(fes_cases)},
            "error_type": {"matched": et_match, "total": len(et_cases)},
            "negatives": {"fp": fp, "total": len(negatives)},
        },
    }

    out = {"metrics": metrics, "cases": rows}
    (OUT_DIR / "adversarial_results.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))

    # ---- Markdown report ----
    lines = []
    lines.append("# §12.4 对抗验证报告 (Adversarial Validation)\n")
    lines.append("> 金标准由样本构造时确定（已知答案），用于验证错误定位逻辑本身。\n")
    lines.append("## 总体指标\n")
    lines.append(f"- 样本数: **{n}** (5 正向检测 + 3 负向控制)")
    lines.append(f"- 过程错误检测准确率 (process error detection accuracy): **{process_match}/{n} = {metrics['process_error_detection_accuracy']:.2%}**")
    lines.append(f"- 首错步准确率 (first-error-step accuracy): **{fes_match}/{len(fes_cases)} = {metrics['first_error_step_accuracy']:.2%}**")
    lines.append(f"- 错误类型准确率 (error-type accuracy): **{et_match}/{len(et_cases)} = {metrics['error_type_accuracy']:.2%}**")
    lines.append(f"- 误报率 (false positive rate, 负样本): **{fp}/{len(negatives)} = {fpr:.2%}**")
    lines.append(f"- 伪成功召回 (unsupported-success recall): **{us_recall:.2%}**")
    lines.append(f"- 伪成功精确率 (unsupported-success precision): **{us_precision:.2%}**\n")
    lines.append("## 逐例明细\n")
    for r in rows:
        g, p = r["gold"], r["pred"]
        ok = (p["process_correct"] == g["process_correct"]
              and (g["first_error_step"] is None or p["first_error_step"] == g["first_error_step"])
              and (g["primary_error_type"] == "UNKNOWN" or p["primary_error_type"] == g["primary_error_type"]))
        verdict = "✅ 命中" if ok else "❌ 偏差"
        lines.append(f"### {r['case_id']} · {r['category']} — {verdict}\n")
        lines.append(f"- 注入缺陷: {r['flaw']}")
        lines.append(f"- 金标准: final={g['final_correct']}, process={g['process_correct']}, "
                     f"first_step={g['first_error_step']}, type={g['primary_error_type']}, unsupported={g['unsupported_success']}")
        lines.append(f"- 系统预测: final={p['final_correct']}, process={p['process_correct']}, "
                     f"first_step={p['first_error_step']}, type={p['primary_error_type']}, unsupported={p['unsupported_success']}")
        lines.append("\n<details><summary>证据 (evidence)</summary>\n")
        for e in r["evidence"]:
            lines.append(f"- `[{e['source']}]` {e['status']} → step={e['target_step']}, type={e['error_type']}: {e['detail']}")
        lines.append("\n</details>\n")

    (OUT_DIR / "adversarial_report.md").write_text("\n".join(lines))
    print(json.dumps(metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
