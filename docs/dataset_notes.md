# Dataset Notes

## EvalPlus MBPP+

### Source
- HuggingFace: [evalplus/mbppplus](https://huggingface.co/datasets/evalplus/mbppplus)
- GitHub Release: [evalplus/mbppplus_release](https://github.com/evalplus/mbppplus_release)
- Original: [Google Research MBPP](https://github.com/google-research/google-research/tree/master/mbpp)

### Statistics
- **Size**: 378 problems (test split)
- **License**: Apache-2.0
- **Test Augmentation**: ~35x increase over original MBPP (3 base tests → ~105+ plus tests)
- **Difficulty Range**: Basic to intermediate Python programming tasks

### Format
Each problem contains:
- `task_id`: Unique identifier (e.g., "Mbpp/123")
- `prompt`: Natural language problem description
- `entry_point`: Function name to implement
- `canonical_solution`: Reference solution
- `base_test_list`: Original test assertions
- `plus_test_list`: Enhanced/augmented test assertions

### Sampling Strategy
For initial experiments:
1. **Smoke test**: 30 problems (seed=42)
2. **Main experiment**: 100 problems (seed=42)
3. **Full run**: All 378 problems

---

## EvalPlus HumanEval+

### Source
- HuggingFace: [evalplus/humanevalplus](https://huggingface.co/datasets/evalplus/humanevalplus)
- GitHub Release: [evalplus/humanevalplus_release](https://github.com/evalplus/humanevalplus_release)
- Original: [OpenAI HumanEval](https://github.com/openai/human-eval)

### Statistics
- **Size**: 164 problems
- **License**: Apache-2.0 (compatible with MIT from original HumanEval)
- **Test Augmentation**: ~80x increase over original HumanEval
- **Difficulty Range**: Intermediate Python programming tasks

### Usage
Used as control experiment to verify the system is not overfitted to MBPP+.
Recommended sample: 30 problems for comparison.

---

## Data Pipeline

```
HuggingFace / GitHub Release
        │
        ▼
  EvalPlus Adapter
        │
        ├─ Load raw records
        ├─ Extract clauses (C1, C2, ...)
        ├─ Normalize field names
        │
        ▼
  ProblemSpec (Unified Format)
        │
        ▼
  Sample (reproducible with seed)
        │
        ▼
  Export to JSONL (optional, for offline use)
```
