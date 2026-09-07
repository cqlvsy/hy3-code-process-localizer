# Method Documentation

## Process Evaluation Methodology

### Overview

The Hy3 Code Process Localizer evaluates AI-generated code at the process level,
going beyond simple pass/fail test results to understand WHERE and WHY errors occur.

### Evaluation Pipeline

#### Phase 1: Solution Generation (Hy3 Solver)
- Sends problem to Hy3 with structured prompt requiring S1-S7 output
- Parses JSON response into SolutionRecord
- Validates all 7 steps are present

#### Phase 2: Execution
- Runs candidate code against base tests (original dataset tests)
- Runs candidate code against plus tests (EvalPlus augmented tests)
- Records pass/fail for each test with error messages

#### Phase 3: Static Analysis
- **AST Checker**: Parses code, checks for syntax errors, missing functions,
  dangerous patterns (eval, exec), structural issues
- **Rule Checker**: Validates process completeness, edge case mentions in S2,
  complexity consistency between S5 claim and actual code, plan-code alignment

#### Phase 4: Coverage-Based Fault Localization (SBFL)
- Uses coverage.py to collect per-test line coverage
- Applies Ochiai formula:
  ```
  score(line) = failed_cover(line) / sqrt(total_failed * (failed_cover + passed_cover))
  ```
- Ranks lines by suspiciousness

#### Phase 5: Evidence Merging
- Combines evidence from all sources with priority ordering:
  1. plus_test (100) - highest authority
  2. base_test (90)
  3. sbfl (80)
  4. static_check (60)
  5. hy3_review (50) - supplementary
- Deduplicates by (target_step, error_type, source)
- Determines first_error_step from earliest contradicted step

#### Phase 6: Final Determination
- final_correct = base_passed AND plus_passed
- process_correct = no contradicted evidence in any step
- unsupported_success = final_correct AND process_has_issues

### Error Localization Layers

1. **Process Step (S1-S7)**: Which reasoning step failed first
2. **Specification Clause (C1, C2, ...)**: Which requirement was violated
3. **Code Line**: Which line(s) are most suspicious (Ochiai score)

### Validation Approach

For validation, we construct annotated sets with:
- expected_final_correct
- expected_process_correct
- expected_first_error_step
- expected_error_type
- expected_unsupported_success

Then compute:
- Localization Accuracy = correct_first_error / total_with_errors
- False Positive Rate = false_process_errors / total_actually_correct
- Error Type Accuracy = correct_type_classifications / total_classifications
