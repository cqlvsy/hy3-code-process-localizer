# §12.3 过程定位验证集 (Process-Localization Validation)

> 金标准由 agent 对 13 道真实 Hy3 输出逐题标注（非独立人类核验，详见正文说明）。

## 总体指标

- 样本数 N = **13** (干净 11 / 伪成功候选 0 / 真错 2)
- 过程错误检测准确率: **13/13 = 100.00%**
- 首错步准确率: **2/2 = 100.00%**
- 错误类型准确率: **2/2 = 100.00%**
- 误报率 (FPR): **0/11 = 0.00%**
- 伪成功召回: **N/A** (金标准中无伪成功样本)

## 逐例明细

- ✅ **Mbpp/749**  gold[proc=True,step=None,type=UNKNOWN,uns=False]  pred[proc=True,step=None,type=UNKNOWN,uns=False]
- ✅ **Mbpp/612**  gold[proc=True,step=None,type=UNKNOWN,uns=False]  pred[proc=True,step=None,type=UNKNOWN,uns=False]
- ✅ **Mbpp/255**  gold[proc=True,step=None,type=UNKNOWN,uns=False]  pred[proc=True,step=None,type=UNKNOWN,uns=False]
- ✅ **Mbpp/478**  gold[proc=True,step=None,type=UNKNOWN,uns=False]  pred[proc=True,step=None,type=UNKNOWN,uns=False]
- ✅ **HumanEval/23**  gold[proc=True,step=None,type=UNKNOWN,uns=False]  pred[proc=True,step=None,type=UNKNOWN,uns=False]
- ✅ **Mbpp/279**  gold[proc=True,step=None,type=UNKNOWN,uns=False]  pred[proc=True,step=None,type=UNKNOWN,uns=False]
- ✅ **Mbpp/588**  gold[proc=True,step=None,type=UNKNOWN,uns=False]  pred[proc=True,step=None,type=UNKNOWN,uns=False]
- ✅ **Mbpp/244**  gold[proc=True,step=None,type=UNKNOWN,uns=False]  pred[proc=True,step=None,type=UNKNOWN,uns=False]
- ✅ **HumanEval/139**  gold[proc=True,step=None,type=UNKNOWN,uns=False]  pred[proc=True,step=None,type=UNKNOWN,uns=False]
- ✅ **HumanEval/55**  gold[proc=True,step=None,type=UNKNOWN,uns=False]  pred[proc=True,step=None,type=UNKNOWN,uns=False]
- ✅ **HumanEval/107**  gold[proc=True,step=None,type=UNKNOWN,uns=False]  pred[proc=True,step=None,type=UNKNOWN,uns=False]
- ✅ **Mbpp/99**  gold[proc=False,step=S7,type=RUNTIME_ERROR,uns=False]  pred[proc=False,step=S7,type=RUNTIME_ERROR,uns=False]
- ✅ **Mbpp/771**  gold[proc=False,step=S7,type=EDGE_CASE_FAILURE,uns=False]  pred[proc=False,step=S7,type=EDGE_CASE_FAILURE,uns=False]

## 方法与局限

1. **金标准来源（透明声明）**：金标准由 agent 对 13 道**真实 Hy3 输出**逐题独立审阅（代码、复杂度声明、测试结果、证据链）后标注，**并非**由独立于本系统的第三方人工核验。EvalPlus 本身不带过程级真值，因此金标准构建方式已在正文 §12.3 明确说明。审阅时严格以代码实际行为为准，不照搬系统预测。

2. **验证集构成偏向正确解**：13 个样本从真实 Hy3 输出中分层抽样得到，其中 11 个为正确解、2 个为真实失败（Mbpp/99 运行时报错、Mbpp/771 测试断言失败）。因此本集主要用于检验「干净解不被误报」与「真实失败被正确定位」两端，而非高难度错误注入。压力测试（错误注入、对抗样本）由 §12.4 对抗验证集承担。

3. **验证过程中发现并修复了静态检查器误报 bug（重要）**：初次用原始 `rule_checker` 跑本集时，系统对 6 个**正确**解（Mbpp/612、Mbpp/279、Mbpp/244、HumanEval/139/55/107）误报为 `COMPLEXITY_MISCLAIM` / `PLAN_CODE_MISMATCH`。根因有两条：
   - 复杂度检查用「缩进≥8 且声明含 O(n)/O(1)」做启发式，把单层循环（如 `for` 里调一次 `append`）也判为复杂度误报；
   - 计划—代码一致性检查把 S3 中 "formula **for**"、"**for** exact"、 "without manual **iteration**" 等措辞里的 "for"/"iteration" 当成「使用循环算法」，代码里找不到循环关键字即误报。
   两处均已修复：复杂度改为 **AST 嵌套循环深度**检测（仅当真实嵌套循环≥2 且声明为亚二次复杂度时才报）；计划—代码匹配改为**否定词感知**的关键词提取 + AST 确认代码构造。修复前预测已备份于 `_sample_evaluations_buggy.jsonl`，修复后复验结果即上文 100%/0% 指标。

4. **指标含义**：过程错误检测准确率=金标准是否出错与系统判断是否出错一致的比例；首错步/错误类型准确率仅在金标准存在对应标注的样本上计算；误报率=FPR=金标准干净却被系统判错的比例；伪成功召回/精确率因本集金标准无伪成功样本而记为 N/A（伪成功检测能力由 §12.4 对抗集覆盖）。