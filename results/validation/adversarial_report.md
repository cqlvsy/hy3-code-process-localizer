# §12.4 对抗验证报告 (Adversarial Validation)

> 金标准由样本构造时确定（已知答案），用于验证错误定位逻辑本身。

## 总体指标

- 样本数: **8** (5 正向检测 + 3 负向控制)
- 过程错误检测准确率 (process error detection accuracy): **7/8 = 87.50%**
- 首错步准确率 (first-error-step accuracy): **4/5 = 80.00%**
- 错误类型准确率 (error-type accuracy): **4/5 = 80.00%**
- 误报率 (false positive rate, 负样本): **0/3 = 0.00%**
- 伪成功召回 (unsupported-success recall): **100.00%**
- 伪成功精确率 (unsupported-success precision): **100.00%**

## 逐例明细

### ADV-01 · COMPLEXITY_MISCLAIM — ✅ 命中

- 注入缺陷: 代码用双层嵌套循环（真实 O(n^2)），但 S5 声称时间复杂度 O(n)。正确答案，过程在 S5 复杂度声明处不成立。
- 金标准: final=True, process=False, first_step=S5, type=COMPLEXITY_MISCLAIM, unsupported=True
- 系统预测: final=True, process=False, first_step=S5, type=COMPLEXITY_MISCLAIM, unsupported=True

<details><summary>证据 (evidence)</summary>

- `[static_check]` contradicted → step=S5, type=COMPLEXITY_MISCLAIM: Code has deep nesting (max indent=16) but claims time complexity O(n)

</details>

### ADV-02 · REASONING_GAP_MISSING_STEP — ✅ 命中

- 注入缺陷: 解题过程缺失 S4（正确性论证）。其余步骤正常、代码正确。过程在 S4 不成立，属伪成功。
- 金标准: final=True, process=False, first_step=S4, type=REASONING_GAP, unsupported=True
- 系统预测: final=True, process=False, first_step=S4, type=REASONING_GAP, unsupported=True

<details><summary>证据 (evidence)</summary>

- `[static_check]` contradicted → step=S4, type=REASONING_GAP: Missing required step S4
- `[static_check]` contradicted → step=S5, type=COMPLEXITY_MISCLAIM: Code has deep nesting (max indent=12) but claims time complexity O(n)

</details>

### ADV-03 · PLAN_CODE_MISMATCH — ❌ 偏差

- 注入缺陷: S3 声称用哈希表（dict）统计频次，但 S7 代码用普通循环计数（无 dict/hash），计划与实现不一致。代码正确，过程错，但不属于伪成功（错误在 S7）。
- 金标准: final=True, process=False, first_step=S7, type=PLAN_CODE_MISMATCH, unsupported=False
- 系统预测: final=True, process=True, first_step=None, type=UNKNOWN, unsupported=False

<details><summary>证据 (evidence)</summary>


</details>

### ADV-04 · RUNTIME_ERROR_EDGE — ✅ 命中

- 注入缺陷: 代码直接索引 lst[0]，未处理空列表，触发 IndexError。最终答案错误，定位到 S7。
- 金标准: final=False, process=False, first_step=S7, type=RUNTIME_ERROR, unsupported=False
- 系统预测: final=False, process=False, first_step=S7, type=RUNTIME_ERROR, unsupported=False

<details><summary>证据 (evidence)</summary>

- `[base_test]` contradicted → step=S7, type=RUNTIME_ERROR: Base test 2 failed: IndexError: list index out of range
Traceback (most recent call last):
  File "/Users/cq/WorkBuddy/2026-09-07-12-24-04/src/hcp_eval/executio
- `[static_check]` warning → step=S5, type=REASONING_GAP: Step S5 has minimal content (5 chars)

</details>

### ADV-05 · EDGE_CASE_FAILURE_ASSERT — ✅ 命中

- 注入缺陷: 代码返回 max(nums) 而非 min(nums)，在常规输入上即产生错误答案（断言失败）。最终错误，定位到 S7。
- 金标准: final=False, process=False, first_step=S7, type=EDGE_CASE_FAILURE, unsupported=False
- 系统预测: final=False, process=False, first_step=S7, type=EDGE_CASE_FAILURE, unsupported=False

<details><summary>证据 (evidence)</summary>

- `[base_test]` contradicted → step=S7, type=EDGE_CASE_FAILURE: Base test 1 failed: Assertion failed: 
- `[static_check]` warning → step=S5, type=REASONING_GAP: Step S5 has minimal content (5 chars)

</details>

### ADV-06 · NEGATIVE_CONTROL — ✅ 命中

- 注入缺陷: 完整正确的解题过程与代码，无任何缺陷。应判定 final/process 均正确、无伪成功。
- 金标准: final=True, process=True, first_step=None, type=UNKNOWN, unsupported=False
- 系统预测: final=True, process=True, first_step=None, type=UNKNOWN, unsupported=False

<details><summary>证据 (evidence)</summary>

- `[static_check]` warning → step=S5, type=REASONING_GAP: Step S5 has minimal content (5 chars)

</details>

### ADV-07 · NEGATIVE_CONTROL — ✅ 命中

- 注入缺陷: 完整正确的解题过程与代码（含空列表边界说明）。应判定全部正确。
- 金标准: final=True, process=True, first_step=None, type=UNKNOWN, unsupported=False
- 系统预测: final=True, process=True, first_step=None, type=UNKNOWN, unsupported=False

<details><summary>证据 (evidence)</summary>

- `[static_check]` warning → step=S5, type=REASONING_GAP: Step S5 has minimal content (5 chars)

</details>

### ADV-08 · NEGATIVE_CONTROL_SOFT_WARNING — ✅ 命中

- 注入缺陷: 代码正确、测试通过，但 S2 未显式提及边界关键词（仅软警告，非矛盾）。应判定 final/process 正确、无伪成功，仅产生软警告。
- 金标准: final=True, process=True, first_step=None, type=UNKNOWN, unsupported=False
- 系统预测: final=True, process=True, first_step=None, type=UNKNOWN, unsupported=False

<details><summary>证据 (evidence)</summary>

- `[static_check]` warning → step=S5, type=REASONING_GAP: Step S5 has minimal content (5 chars)

</details>
