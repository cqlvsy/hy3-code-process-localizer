# Hy3 Code Process Localizer

> **Hy3 代码过程评估与错误定位系统** — 基于 Tencent Hunyuan Hy3 的 Python 代码解题过程评估系统

## 项目简介

本项目基于 **Tencent Hunyuan Hy3** 大语言模型，构建了一个面向 Python 函数编程题的 **过程级代码评估与错误定位系统**。不同于传统评测仅判断测试是否通过，本系统能够：

1. **生成完整解题过程**：通过 Hy3 输出 S1-S7 七步结构化推理过程 + 可执行代码
2. **多层错误定位**：过程步骤定位 → 规格条款定位 → 代码行定位（SBFL/Ochiai）
3. **识别「正确但过程不成立」**：发现最终答案正确但推理无法支撑结论的样本
4. **多源证据融合**：执行测试 + 静态分析（AST/规则）+ LLM 审查 + 覆盖率分析

> ⚠️ **声明**：本项目为个人/活动作品，非腾讯官方发布。不训练、不微调模型，仅通过 Hy3 API 调用模型能力。

## 系统架构

```
EvalPlus MBPP+ / HumanEval+
    │
    ▼
┌─────────────────┐
│  Dataset Adapter │ ──→ ProblemSpec (统一数据格式)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Hy3 Solver    │ ──→ S1-S7 过程步骤 + Python 代码
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Executor     │ ──→ base / plus 测试执行结果
│  (Sandbox)      │
└────────┬────────┘
         │
    ┌────┴────┬──────────┐
    ▼         ▼          ▼
┌────────┐ ┌────────┐ ┌────────────┐
│ AST    │ │ Rule   │ │ Coverage & │
│Checker │ │Checker │ │ SBFL (Ochiai)│
└───┬────┘ └───┬────┘ └─────┬──────┘
    │          │            │
    ▼          ▼            ▼
┌─────────────────────────────┐
│     Evidence Merger         │ ──→ 合并排序、去重
└─────────────┬──────────────┘
              │
              ▼
┌─────────────────────────────┐
│     Error Localizer         │ ──→ EvaluationResult
│  - first_error_step         │
│  - violated_clause          │
│  - primary_error_type       │
│  - unsupported_success      │
│  - suspect_code_lines       │
└─────────────┬──────────────┘
              │
              ▼
┌─────────────────────────────┐
│   Metrics & Report Writer   │ ──→ CSV / JSONL / Markdown 报告
└─────────────────────────────┘
```

## 核心设计

### S1-S7 过程步骤

| 步骤 | 名称 | 内容 |
|------|------|------|
| S1 | 需求理解 | 题目要求什么？输入输出是什么？ |
| S2 | 约束与边界 | 有哪些边界条件？空输入？重复元素？ |
| S3 | 算法选择 | 选择什么算法/方法？为什么？ |
| S4 | 正确性说明 | 为什么这个方法是正确的？证明概要 |
| S5 | 复杂度分析 | 时间/空间复杂度及理由 |
| S6 | 自测计划 | 会用什么测试用例验证正确性？ |
| S7 | 代码实现 | 完整的 Python 函数代码 |

### 三层错误定位

1. **过程步骤定位**：错误最早出现在哪个 S1-S7 步骤
2. **规格条款定位**：违反了题目要求的哪条具体条款（C1, C2, ...）
3. **代码行定位**：基于 coverage.py + Ochiai 公式计算每行代码的可疑度

### 错误类型体系

`FORMAT_ERROR` | `SPEC_MISREAD` | `CONDITION_MISSING` | `UNJUSTIFIED_ASSUMPTION` | `ALGORITHM_INVALID` | `REASONING_GAP` | `COMPLEXITY_MISCLAIM` | `EDGE_CASE_FAILURE` | `PLAN_CODE_MISMATCH` | `PROCESS_RESULT_MISMATCH` | `RUNTIME_ERROR` | `TIMEOUT` | `SECURITY_VIOLATION` | `UNKNOWN`

## 环境要求

- Python >= 3.10
- Hy3 模型服务（vLLM 或 SGLang 部署，提供 OpenAI-compatible API）

### 安装

```bash
# 克隆项目
git clone https://github.com/cqlvsy/hy3-code-process-localizer.git
cd hy3-code-process-localizer

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# 安装依赖
pip install -e ".[dev]"

# 复制环境变量模板
cp .env.example .env
# 编辑 .env，填入你的 Hy3 API 配置
```

### Hy3 配置

编辑 `.env` 文件：

```bash
# Hy3 API 地址（OpenAI 兼容接口）
HY3_BASE_URL=http://127.0.0.1:8000/v1
HY3_API_KEY=your-api-key-here
HY3_MODEL=hy3
HY3_REASONING_EFFORT=high
```

Hy3 部署请参考：[Tencent-Hunyuan/Hy3](https://github.com/Tencent-Hunyuan/Hy3)

## 使用方式

### 1. 检查 Hy3 连接

```bash
hcp-eval health
```

### 2. 下载数据集样本（可选，用于离线使用）

```bash
hcp-eval download --dataset mbppplus --sample-size 30 --seed 42
```

### 3. 运行完整评估

```bash
# 使用 Hy3 生成解答并评估
hcp-eval run --dataset mbppplus --sample-size 30

# 不调用 Hy3，使用参考答案评估（快速验证）
hcp-eval run --dataset mbppplus --sample-size 30 --no-hy3

# 跳过 SBFL 分析（更快）
hcp-eval run --dataset mbppplus --sample-size 30 --no-sbfl
```

### 4. 使用 HumanEval+ 作为对照实验

```bash
hcp-eval run --dataset humanevalplus --sample-size 30
```

### 5. 查看 Demo（需要 streamlit）

```bash
pip install -e ".[demo]"
streamlit run demo/app.py
```

## 数据集

### 主数据集：EvalPlus MBPP+

- **来源**：[evalplus/mbppplus](https://huggingface.co/datasets/evalplus/mbppplus)
- **规模**：378 题
- **许可证**：Apache-2.0
- **特点**：基于 MBPP 清洗增强，测试数量平均增加约 35 倍

### 对照数据集：EvalPlus HumanEval+

- **来源**：[evalplus/humanevalplus](https://huggingface.co/datasets/evalplus/humanevalplus)
- **规模**：164 题
- **许可证**：Apache-2.0 + MIT（兼容 OpenAI HumanEval）

### 下载方式

```bash
pip install datasets evalplus
```

程序会自动从 HuggingFace 加载，也支持预下载后离线使用。

## 项目结构

```
hy3-code-process-localizer/
├── README.md                  # 项目说明
├── pyproject.toml             # 项目配置与依赖
├── .env.example               # 环境变量模板
├── .gitignore
├── src/
│   └── hcp_eval/
│       ├── __init__.py
│       ├── config.py          # 配置管理
│       ├── schemas.py         # 数据模型定义
│       ├── hy3_client.py      # Hy3 API 客户端
│       ├── prompt_builder.py  # Prompt 模板
│       ├── parser.py          # 响应解析
│       ├── cli.py             # 命令行入口
│       ├── adapters/
│       │   ├── __init__.py
│       │   └── evalplus_adapter.py  # EvalPlus 数据集适配
│       ├── execution/
│       │   ├── __init__.py
│       │   ├── sandbox_runner.py    # 沙盒执行器
│       │   └── sbfl_localizer.py    # SBFL 错误定位
│       └── evaluation/
│           ├── __init__.py
│           ├── ast_checker.py       # AST 静态分析
│           ├── rule_checker.py      # 规则检查器
│           ├── evidence_merger.py   # 证据合并
│           ├── error_localizer.py   # 核心评估逻辑
│           ├── metrics.py           # 指标计算
│           └── report_writer.py     # 报告生成
├── data/                      # 数据集存储
├── results/                   # 评估结果输出
│   ├── eval_results.csv       # 结果表格
│   ├── eval_results.jsonl     # 详细结果
│   ├── metrics.json           # 指标汇总
│   └── analysis_report.md     # 分析报告
├── docs/                      # 文档
├── demo/
│   └── app.py                 # Streamlit Demo
└── tests/                     # 测试
```

## 输出说明

### eval_results.csv

每行一道题的评估结果，包含：
- `final_correct`：是否通过所有测试
- `base_passed` / `plus_passed`：基础/增强测试是否通过
- `process_correct`：推理过程是否成立
- `first_error_step`：最早出错步骤（S1-S7）
- `primary_error_type`：主要错误类型
- `unsupported_success`：是否为「正确但不成立」样本

### metrics.json

聚合指标：
- Final Accuracy / Base Pass Rate / Plus Pass Rate / Process Accuracy
- Error Type Distribution（错误类型分布）
- Difficulty Breakdown（难度分层结果）
- Localization Accuracy / False Positive Rate（如有标注数据）

### analysis_report.md

完整的 Markdown 分析报告，包括总体结果、错误分布、典型案例、能力边界分析。

## 设计原则

1. **执行证据优先**：测试失败是不可否认的事实，LLM 判断不能覆盖
2. **静态规则其次**：AST 和规则检查提供快速、确定性的信号
3. **Hy3 Reviewer 补充语义判断**：仅在语法和执行证据不足时调用
4. **若冲突，以测试为准**

## 安全说明

- 候选代码在受限子进程中执行，有超时保护
- API Key 通过环境变量读取，绝不硬编码或提交到仓库
- 不训练、不微调任何模型

## 许可证

Apache-2.0

## 致谢

- [Tencent Hunyuan Hy3](https://github.com/Tencent-Hunyuan/Hy3) — 底层大语言模型
- [EvalPlus](https://github.com/evalplus/evalplus) — 评测框架与增强数据集
- [coverage.py](https://coverage.readthedocs.io/) — 代码覆盖率工具
