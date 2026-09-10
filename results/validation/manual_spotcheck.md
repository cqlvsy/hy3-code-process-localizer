# §12.3 人工抽检记录表 (Manual Spot-Check Record)

> **用途**：按任务要求「误报率 = 在答案正确的样本上，被评估器判定为过程存在问题的样本，经人工抽检确认其中属于真实问题与属于误报的比例」，提供规范化的抽检记录。
>
> **说明**：本表由系统自动预填「系统判定」与「agent 标注」两列，供**人工逐例复核**后在「人工确认」列勾选并签字。当前金标准为 agent 依据代码实际行为标注（非独立人工核验），详见 `validation_report.md` 的「方法与局限」。

## 抽检口径

- 抽检范围：§12.3 验证集 13 例（11 个正确解 + 2 个真实失败）。
- 误报抽检对象 = 系统判定「过程存在问题（process=False）」的**正确解**样本。
- 误报比例 = 其中经人工确认为误报的样本数 / 被判定有问题的正确解样本数。

## 记录表

| # | 样本 | 系统判定 (过程 / 首错步 / 类型) | agent 标注 | 判定一致性 | 人工确认(是/否) | 备注 |
|---|------|--------------------------------|-----------|-----------|----------------|------|
| 1 | Mbpp/749 | True / - / UNKNOWN | True / - / UNKNOWN | 一致 | ☐ | 干净解，未被误报 |
| 2 | Mbpp/612 | True / - / UNKNOWN | True / - / UNKNOWN | 一致 | ☐ | 干净解，未被误报 |
| 3 | Mbpp/255 | True / - / UNKNOWN | True / - / UNKNOWN | 一致 | ☐ | 干净解，未被误报 |
| 4 | Mbpp/478 | True / - / UNKNOWN | True / - / UNKNOWN | 一致 | ☐ | 干净解，未被误报 |
| 5 | HumanEval/23 | True / - / UNKNOWN | True / - / UNKNOWN | 一致 | ☐ | 干净解，未被误报 |
| 6 | Mbpp/279 | True / - / UNKNOWN | True / - / UNKNOWN | 一致 | ☐ | 干净解，未被误报 |
| 7 | Mbpp/588 | True / - / UNKNOWN | True / - / UNKNOWN | 一致 | ☐ | 干净解，未被误报 |
| 8 | Mbpp/244 | True / - / UNKNOWN | True / - / UNKNOWN | 一致 | ☐ | 干净解，未被误报 |
| 9 | HumanEval/139 | True / - / UNKNOWN | True / - / UNKNOWN | 一致 | ☐ | 干净解，未被误报 |
| 10 | HumanEval/55 | True / - / UNKNOWN | True / - / UNKNOWN | 一致 | ☐ | 干净解，未被误报 |
| 11 | HumanEval/107 | True / - / UNKNOWN | True / - / UNKNOWN | 一致 | ☐ | 干净解，未被误报 |
| 12 | Mbpp/99 | False / S7 / RUNTIME_ERROR | False / S7 / RUNTIME_ERROR | 一致 | ☐ | 真实失败，定位正确 |
| 13 | Mbpp/771 | False / S7 / EDGE_CASE_FAILURE | False / S7 / EDGE_CASE_FAILURE | 一致 | ☐ | 真实失败，定位正确 |

## 抽检结论

- 系统判定「过程存在问题」的**正确解**样本数：**0**（11 个正确解全部判为干净）
  → **无可抽检的误报样本**，误报比例记为 0（等价于 FPR = 0/11 = 0.00%）。
- 系统判定与标注**一致率**：**13/13 = 100%**。
- 说明：本记录的「人工确认」列需由人工（作者 / 评审）逐例复核后勾选签字，方视为完整的独立人工抽检记录；在此之前，抽检结论基于 agent 标注。

## 签字

- 抽检人：＿＿＿＿＿＿＿＿　　日期：＿＿＿＿＿＿＿＿
- 复核人：＿＿＿＿＿＿＿＿　　日期：＿＿＿＿＿＿＿＿
