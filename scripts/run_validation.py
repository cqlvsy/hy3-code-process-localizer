#!/usr/bin/env python3
"""Compute §12.3 process-localization validation metrics.

Compares the system's prediction (results/validation/sample_evaluations.jsonl)
against agent-assigned gold labels (results/validation/gold_annotations.json).

Metrics (per the implementation doc §12.3):
  - process detection accuracy
  - first-error-step accuracy   (over process-wrong cases, gold step not None)
  - error-type accuracy         (over process-wrong cases, gold type != UNKNOWN)
  - false positive rate         (over gold-clean cases)
  - unsupported-success recall / precision
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VAL = ROOT / "results" / "validation"


def load(path: Path):
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def main():
    preds = {r["task_id"]: r for r in load(VAL / "sample_evaluations.jsonl")}
    golds = {g["task_id"]: g for g in load(VAL / "gold_annotations.json")}

    rows = []
    for tid, g in golds.items():
        p = preds.get(tid)
        if not p:
            continue
        rows.append((tid, g, p))

    n = len(rows)
    proc_match = sum(1 for _, g, p in rows if g["process_correct"] == p["process_correct"])

    fes_cases = [(g, p) for _, g, p in rows if g.get("first_error_step") is not None]
    fes_match = sum(1 for g, p in fes_cases if g["first_error_step"] == p["first_error_step"])

    et_cases = [(g, p) for _, g, p in rows if g.get("primary_error_type") != "UNKNOWN"]
    et_match = sum(1 for g, p in et_cases if g["primary_error_type"] == p["primary_error_type"])

    negatives = [(g, p) for _, g, p in rows if g["process_correct"] and not g["unsupported_success"]]
    fp = sum(1 for g, p in negatives if not p["process_correct"])
    fpr = fp / len(negatives) if negatives else None

    us_gold = [(g, p) for _, g, p in rows if g["unsupported_success"]]
    us_pred = [(g, p) for _, g, p in rows if p["unsupported_success"]]
    us_recall = sum(1 for g, p in us_gold if p["unsupported_success"]) / len(us_gold) if us_gold else None
    us_prec = sum(1 for g, p in us_pred if g["unsupported_success"]) / len(us_pred) if us_pred else None

    # Per-case detail
    details = []
    for tid, g, p in rows:
        ok = (g["process_correct"] == p["process_correct"]
              and (g.get("first_error_step") is None or g["first_error_step"] == p["first_error_step"])
              and (g.get("primary_error_type") == "UNKNOWN" or g["primary_error_type"] == p["primary_error_type"]))
        details.append({
            "task_id": tid,
            "gold": g, "pred": {"process_correct": p["process_correct"],
                                "first_error_step": p["first_error_step"],
                                "primary_error_type": p["primary_error_type"],
                                "unsupported_success": p["unsupported_success"]},
            "match": ok,
        })

    metrics = {
        "n": n,
        "process_detection_accuracy": proc_match / n,
        "first_error_step_accuracy": fes_match / len(fes_cases) if fes_cases else None,
        "error_type_accuracy": et_match / len(et_cases) if et_cases else None,
        "false_positive_rate": fpr,
        "unsupported_success_recall": us_recall,
        "unsupported_success_precision": us_prec,
        "breakdown": {
            "first_error_step": {"matched": fes_match, "total": len(fes_cases)},
            "error_type": {"matched": et_match, "total": len(et_cases)},
            "negatives": {"fp": fp, "total": len(negatives)},
        },
    }
    (VAL / "validation_metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False))

    lines = ["# §12.3 过程定位验证集 (Process-Localization Validation)\n",
             "> 金标准由 agent 对 13 道真实 Hy3 输出逐题标注（非独立人类核验，详见正文说明）。\n",
             "## 总体指标\n",
             f"- 样本数 N = **{n}** (干净 {sum(1 for _,g,p in rows if g['process_correct'])} / 伪成功候选 {sum(1 for _,g,p in rows if g['unsupported_success'])} / 真错 {sum(1 for _,g,p in rows if not p['final_correct'])})",
             f"- 过程错误检测准确率: **{proc_match}/{n} = {metrics['process_detection_accuracy']:.2%}**",
             f"- 首错步准确率: **{fes_match}/{len(fes_cases)} = {metrics['first_error_step_accuracy']:.2%}**",
             f"- 错误类型准确率: **{et_match}/{len(et_cases)} = {metrics['error_type_accuracy']:.2%}**",
             f"- 误报率 (FPR): **{fp}/{len(negatives)} = {metrics['false_positive_rate']:.2%}**",
             f"- 伪成功召回: **{us_recall:.2%}** | 精确率: **{us_prec:.2%}**\n" if us_recall is not None and us_prec is not None else "- 伪成功召回: **N/A** (金标准中无伪成功样本)\n",
             "## 逐例明细\n"]
    for d in details:
        g, p = d["gold"], d["pred"]
        verdict = "✅" if d["match"] else "❌"
        lines.append(f"- {verdict} **{d['task_id']}**  gold[proc={g['process_correct']},step={g.get('first_error_step')},type={g.get('primary_error_type')},uns={g['unsupported_success']}]  "
                     f"pred[proc={p['process_correct']},step={p['first_error_step']},type={p['primary_error_type']},uns={p['unsupported_success']}]")
    (VAL / "validation_report.md").write_text("\n".join(lines))
    print(json.dumps(metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
