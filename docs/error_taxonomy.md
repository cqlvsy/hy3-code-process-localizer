# Error Taxonomy

## Complete Error Type Definitions

| Error Type | When It Applies | Typical Source Step | Detectable By |
|------------|-----------------|---------------------|---------------|
| `FORMAT_ERROR` | Output format doesn't match spec (wrong type, missing fields) | S7 | static_check, test |
| `SPEC_MISREAD` | Problem statement fundamentally misunderstood | S1 | hy3_review |
| `CONDITION_MISSING` | Edge case, boundary condition, or constraint not handled | S2 | plus_test, rule_checker |
| `UNJUSTIFIED_ASSUMPTION` | Assumption made without evidence or basis | S3-S4 | hy3_review, rule_checker |
| `ALGORITHM_INVALID` | Chosen algorithm is wrong for this problem type | S3 | plus_test, hy3_review |
| `REASONING_GAP` | Logical jump without connecting reasoning | S4 | hy3_review |
| `COMPLEXITY_MISCLAIM` | Stated complexity doesn't match implementation | S5 | rule_checker |
| `EDGE_CASE_FAILURE` | Code fails on specific edge/boundary inputs | S2, S7 | plus_test, sbfl |
| `PLAN_CODE_MISMATCH` | Implementation doesn't match described approach | S7 | rule_checker, ast_checker |
| `PROCESS_RESULT_MISMATCH` | Correct final answer but through flawed reasoning | Any | evidence_merger |
| `RUNTIME_ERROR` | Code raises exception during execution | S7 | test (base/plus) |
| `TIMEOUT` | Code exceeds execution time limit | S7 | test (base/plus) |
| `SECURITY_VIOLATION` | Dangerous pattern detected (eval, exec, etc.) | S7 | ast_checker |
| `UNKNOWN` | Error couldn't be classified | - | fallback |

## Step-to-Error Mapping Heuristics

- **S1 errors** → Usually SPEC_MISREAD
- **S2 errors** → Usually CONDITION_MISSING or EDGE_CASE_FAILURE
- **S3 errors** → Usually ALGORITHM_INVALID or UNJUSTIFIED_ASSUMPTION
- **S4 errors** → Usually REASONING_GAP
- **S5 errors** → Usually COMPLEXITY_MISCLAIM
- **S6 errors** → Usually CONDITION_MISSING (incomplete test plan)
- **S7 errors** → FORMAT_ERROR, RUNTIME_ERROR, PLAN_CODE_MISMATCH, EDGE_CASE_FAILURE
