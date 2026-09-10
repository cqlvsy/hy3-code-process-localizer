#!/usr/bin/env python3
"""Generate a <=2min demo GIF showing one full solve + process-evaluation flow.

Uses a REAL cached example (Mbpp/771) from results/validation/sample_evaluations.jsonl
so that NO API call is required. The example demonstrates the system catching an
edge-case failure (EDGE_CASE_FAILURE @ S7) that simple test-passing would miss.
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "results" / "validation" / "sample_evaluations.jsonl"
OUT = ROOT / "demo" / "process_eval_demo.gif"

# ---------- theme (dark) ----------
BG = (15, 20, 25)
PANEL = (26, 34, 46)
PANEL2 = (32, 42, 56)
ACCENT = (74, 168, 255)
GREEN = (63, 185, 80)
RED = (248, 81, 73)
AMBER = (210, 153, 34)
TEXT = (230, 237, 243)
MUTED = (139, 148, 158)
WHITE = (255, 255, 255)

W, H = 1000, 640


def load_font(paths, size, index=0):
    for p in paths:
        try:
            return ImageFont.truetype(p, size, index=index)
        except Exception:
            continue
    return ImageFont.load_default()


MONO = load_font(
    ["/System/Library/Fonts/Menlo.ttc", "/System/Library/Fonts/Monaco.ttf"], 20
)
MONO_SM = load_font(
    ["/System/Library/Fonts/Menlo.ttc", "/System/Library/Fonts/Monaco.ttf"], 17
)
SANS = load_font(
    ["/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Menlo.ttc"], 26
)
SANS_SM = load_font(
    ["/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Menlo.ttc"], 18
)
TITLE = load_font(
    ["/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Menlo.ttc"], 38
)


def wrap(text, font, max_w):
    lines = []
    for para in text.split("\n"):
        if not para:
            lines.append("")
            continue
        cur = ""
        for ch in para:
            test = cur + ch
            if font.getlength(test) > max_w and cur:
                lines.append(cur)
                cur = ch
            else:
                cur = test
        lines.append(cur)
    return lines


def new_canvas():
    img = Image.new("RGB", (W, H), BG)
    return img, ImageDraw.Draw(img)


def panel(d, x, y, w, h, fill=PANEL, radius=14):
    d.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=fill)


def header(d, title, step_no=None):
    panel(d, 40, 36, W - 80, 64, fill=PANEL2, radius=14)
    d.text((64, 56), title, font=SANS, fill=WHITE)
    if step_no:
        d.text((W - 200, 60), step_no, font=SANS_SM, fill=ACCENT)


def footer(d, text):
    d.text((40, H - 36), text, font=SANS_SM, fill=MUTED)


def render(rec):
    frames = []

    steps = rec["steps"]
    step_by_id = {s["id"]: s for s in steps}
    complexity = rec.get("complexity", {})
    evidence = rec.get("evidence", [])
    code = rec.get("code", "")
    prompt = rec["prompt"].strip()

    durations = []

    def frame(draw_fn, duration=1600):
        img, d = new_canvas()
        draw_fn(d)
        footer(d, "Hy3 代码过程评估与错误定位  ·  示例 Mbpp/771  (括号匹配 checker)")
        frames.append(img)
        durations.append(duration)

    # ---- Frame 0: title ----
    def f_title(d):
        d.text((W // 2, 150), "Hy3 代码过程评估与错误定位", font=TITLE, fill=WHITE, anchor="mm")
        d.text((W // 2, 215), "一次完整解题 + 过程评估流程", font=SANS, fill=ACCENT, anchor="mm")
        panel(d, 230, 290, 540, 70, fill=PANEL2, radius=14)
        d.text((W // 2, 325), "Demo · 基于 Tencent Hunyuan Hy3", font=SANS_SM, fill=MUTED, anchor="mm")
        d.text((W // 2, 470), "传统评测只看「测试是否通过」", font=SANS_SM, fill=TEXT, anchor="mm")
        d.text((W // 2, 502), "本系统额外评估推理过程是否成立、定位错误步骤", font=SANS_SM, fill=TEXT, anchor="mm")

    frame(f_title, duration=1800)

    # ---- Frame 1: task ----
    def f_task(d):
        header(d, "① 题目 Task", "S1 输入")
        panel(d, 40, 120, W - 80, 440, fill=PANEL)
        y = 150
        d.text((64, y), "check_expression(expr) -> bool", font=MONO, fill=ACCENT)
        y += 36
        for ln in wrap(prompt, MONO_SM, W - 160):
            d.text((64, y), ln, font=MONO_SM, fill=TEXT)
            y += 26
        y += 14
        d.text((64, y), "要求：判断括号表达式是否平衡，如 {()}[{}] -> True", font=MONO_SM, fill=MUTED)

    frame(f_task, duration=1800)

    # ---- Frame 2: complexity claim ----
    def f_complexity(d):
        header(d, "② 模型自报复杂度 (S5)", "S5 声明")
        panel(d, 40, 120, W - 80, 200, fill=PANEL)
        d.text((64, 160), "Time : O(n)", font=MONO, fill=TEXT)
        d.text((64, 200), "Space: O(n)", font=MONO, fill=TEXT)
        y = 360
        panel(d, 40, y, W - 80, 150, fill=PANEL2)
        d.text((64, y + 20), "过程评估将校验该复杂度声明是否真实成立：", font=MONO_SM, fill=MUTED)
        d.text((64, y + 56), "→ 用 AST 检测真实嵌套循环深度 vs 声明复杂度", font=MONO_SM, fill=ACCENT)
        d.text((64, y + 88), "→ 避免「声称 O(n) 实为 O(n²)」的复杂度误报", font=MONO_SM, fill=ACCENT)

    frame(f_complexity, duration=1800)

    # ---- Frame 3: steps S1-S3 ----
    def f_steps1(d):
        header(d, "③ 解题过程 S1–S7（上）", "S1–S3")
        panel(d, 40, 120, W - 80, 440, fill=PANEL)
        y = 150
        for sid in ["S1", "S2", "S3"]:
            s = step_by_id.get(sid, {})
            d.text((64, y), f"{sid} · {s.get('type','')}", font=MONO_SM, fill=AMBER)
            y += 26
            for ln in wrap(s.get("claim", ""), MONO_SM, W - 160):
                d.text((80, y), ln, font=MONO_SM, fill=TEXT)
                y += 24
            y += 14

    frame(f_steps1, duration=1800)

    # ---- Frame 4: steps S4-S7 ----
    def f_steps2(d):
        header(d, "③ 解题过程 S1–S7（下）", "S4–S7")
        panel(d, 40, 120, W - 80, 440, fill=PANEL)
        y = 150
        for sid in ["S4", "S5", "S6", "S7"]:
            s = step_by_id.get(sid, {})
            d.text((64, y), f"{sid} · {s.get('type','')}", font=MONO_SM, fill=AMBER)
            y += 26
            for ln in wrap(s.get("claim", ""), MONO_SM, W - 160):
                d.text((80, y), ln, font=MONO_SM, fill=TEXT)
                y += 24
            y += 10

    frame(f_steps2, duration=1800)

    # ---- Frame 5: code ----
    def f_code(d):
        header(d, "④ 生成的代码 (S7)", "S7 输出")
        panel(d, 40, 120, W - 80, 440, fill=(18, 24, 33))
        y = 150
        for ln in code.split("\n"):
            d.text((64, y), ln if ln else " ", font=MONO, fill=(180, 220, 180))
            y += 30

    frame(f_code, duration=2000)

    # ---- Frame 6: process evaluation / evidence ----
    def f_eval(d):
        header(d, "⑤ 过程评估 (rule_checker + plus tests)", "定位")
        panel(d, 40, 120, W - 80, 440, fill=PANEL)
        d.text((64, 150), "逐条检查 S1–S7 的声明与代码一致性…", font=MONO_SM, fill=MUTED)
        y = 195
        for ev in evidence:
            color = RED if ev.get("status") == "contradicted" else GREEN
            d.text((64, y), f"[{ev.get('source')}] {ev.get('status')}", font=MONO_SM, fill=color)
            y += 26
            detail = ev.get("detail", "")
            for ln in wrap(detail, MONO_SM, W - 160):
                d.text((80, y), ln, font=MONO_SM, fill=TEXT)
                y += 24
            y += 14
        # highlight
        hy = 470
        panel(d, 40, hy, W - 80, 70, fill=PANEL2)
        d.text((64, hy + 18), "⚠ 边界用例 (plus test) 在 S7 失败 → EDGE_CASE_FAILURE", font=MONO_SM, fill=RED)
        d.text((64, hy + 46), "该缺陷「仅看基准测试通过」无法发现", font=MONO_SM, fill=AMBER)

    frame(f_eval, duration=2200)

    # ---- Frame 7: verdict ----
    def f_verdict(d):
        header(d, "⑥ 评估结论", "结果")
        rows = [
            ("最终答案准确率 Final", "✗ False", RED),
            ("过程正确率 Process", "✗ False", RED),
            ("首错步骤 First Error", "S7", AMBER),
            ("错误类型 Error Type", "EDGE_CASE_FAILURE", AMBER),
            ("是否「伪成功」", "否 (答案与过程均错)", MUTED),
        ]
        y = 150
        for label, val, col in rows:
            panel(d, 40, y, W - 80, 64, fill=PANEL)
            d.text((64, y + 20), label, font=MONO_SM, fill=TEXT)
            d.text((W - 360, y + 20), val, font=MONO_SM, fill=col)
            y += 80
        y += 6
        d.text((64, y), "→ 过程评估把「看起来对」的实现拆到步骤级，暴露边界缺陷", font=MONO_SM, fill=ACCENT)

    frame(f_verdict, duration=2200)

    # ---- Frame 8: closing ----
    def f_close(d):
        d.text((W // 2, 200), "过程评估的价值", font=TITLE, fill=WHITE, anchor="mm")
        d.text((W // 2, 280), "不只问「答案对不对」", font=SANS, fill=TEXT, anchor="mm")
        d.text((W // 2, 320), "更追问「过程成立不成立、错在哪一步」", font=SANS, fill=TEXT, anchor="mm")
        panel(d, 230, 400, 540, 70, fill=PANEL2, radius=14)
        d.text((W // 2, 435), "完整源码 / 报告见 GitHub 仓库 README", font=SANS_SM, fill=MUTED, anchor="mm")

    frame(f_close, duration=2000)

    return frames, durations


def main():
    rec = None
    with open(SRC) as f:
        for line in f:
            r = json.loads(line)
            if r["task_id"] == "Mbpp/771":
                rec = r
                break
    assert rec, "Mbpp/771 not found in sample_evaluations.jsonl"

    frames, durations = render(rec)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        OUT,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )
    print(f"Wrote {OUT} with {len(frames)} frames, size={OUT.stat().st_size/1024:.1f} KB")


if __name__ == "__main__":
    main()
