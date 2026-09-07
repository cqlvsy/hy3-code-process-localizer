"""Streamlit demo app for interactive visualization."""

import json
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import streamlit as st

from hcp_eval.schemas import EvaluationResult, MetricsSummary


def main():
    st.set_page_config(
        page_title="Hy3 Code Process Localizer",
        page_icon="🔍",
        layout="wide",
    )

    st.title("🔍 Hy3 Code Process Localizer")
    st.subtitle("Process-Level Evaluation & Error Localization for Hy3-Generated Code")
    st.markdown("---")

    # Sidebar navigation
    st.sidebar.header("Navigation")
    page = st.sidebar.radio(
        "Go to",
        ["Overview", "Results", "Analysis", "Error Taxonomy"],
    )

    # Load data
    results_dir = Path("results")
    results_file = results_dir / "eval_results.jsonl"
    metrics_file = results_dir / "metrics.json"

    results = []
    if results_file.exists():
        with open(results_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        results.append(EvaluationResult.model_validate_json(line))
                    except Exception:
                        pass

    metrics = None
    if metrics_file.exists():
        with open(metrics_file) as f:
            try:
                metrics = MetricsSummary.model_validate_json(f.read())
            except Exception:
                pass

    if page == "Overview":
        st.header("Project Overview")
        st.markdown("""
        This system evaluates **Tencent Hunyuan Hy3** generated Python code solutions
        at the **process level**, not just checking test pass/fail.

        ### Key Capabilities
        - **S1-S7 Process Step Tracking**: Requirement understanding through code implementation
        - **Three-Layer Error Localization**:
          1. Process step localization (which S1-S7 step failed first)
          2. Specification clause localization (which requirement was violated)
          3. Code line localization (SBFL/Ochiai suspiciousness scoring)
        - **Unsupported Success Detection**: Catches correct answers from flawed reasoning
        - **Multi-Source Evidence Merging**: Tests + static analysis + LLM review + SBFL

        ### Datasets
        - **Primary**: EvalPlus MBPP+ (378 problems, ~35x test augmentation)
        - **Control**: EvalPlus HumanEval+ (164 problems)

        ### Error Types Tracked
        """)
        error_types = [
            ("FORMAT_ERROR", "Output format mismatch"),
            ("SPEC_MISREAD", "Problem specification misunderstood"),
            ("CONDITION_MISSING", "Edge case or condition not handled"),
            ("UNJUSTIFIED_ASSUMPTION", "Assumption without basis"),
            ("ALGORITHM_INVALID", "Algorithm fundamentally wrong"),
            ("REASONING_GAP", "Logical gap in reasoning"),
            ("COMPLEXITY_MISCLAIM", "Complexity claim contradicts code"),
            ("EDGE_CASE_FAILURE", "Failure on edge/boundary inputs"),
            ("PLAN_CODE_MISMATCH", "Implementation doesn't match plan"),
            ("PROCESS_RESULT_MISMATCH", "Correct result, flawed process"),
            ("RUNTIME_ERROR", "Code raises exception"),
            ("TIMEOUT", "Code exceeds time limit"),
            ("SECURITY_VIOLATION", "Security issue in code"),
        ]
        for et, desc in error_types:
            st.markdown(f"- **`{et[0]}`**: {et[1]}")

    elif page == "Results":
        st.header("Evaluation Results")

        if not results:
            st.warning("No results found. Run `hcp-eval run` first.")
            return

        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        if metrics:
            col1.metric("Final Accuracy", f"{metrics.final_accuracy:.1%}")
            col2.metric("Base Pass Rate", f"{metrics.base_pass_rate:.1%}")
            col3.metric("Plus Pass Rate", f"{metrics.plus_pass_rate:.1%}")
            col4.metric("Process Accuracy", f"{metrics.process_accuracy:.1%}")

        st.markdown("---")

        # Results table
        st.subheader(f"All Results ({len(results)} problems)")

        # Filter options
        col_filter1, col_filter2 = st.columns(2)
        show_only_failures = col_filter1.checkbox("Show only failures", value=False)
        filter_dataset = col_filter2.multiselect(
            "Filter by dataset",
            list(set(r.dataset for r in results)),
            default=list(set(r.dataset for r in results)),
        )

        filtered_results = results
        if show_only_failures:
            filtered_results = [r for r in filtered_results if not r.final_correct]
        filtered_results = [r for r in filtered_results if r.dataset in filter_dataset]

        for r in filtered_results[:50]:  # Limit display
            with st.expander(f"`{r.task_id}` — {'✅ PASS' if r.final_correct else '❌ FAIL'}"):
                cols = st.columns(3)
                cols[0].markdown(f"**Base:** {'✅' if r.base_passed else '❌'}")
                cols[1].markdown(f"**Plus:** {'✅' if r.plus_passed else '❌'}")
                cols[2].markdown(f"**Process:** {'✅' if r.process_correct else f'❌ @{r.first_error_step}'}")

                st.markdown(f"**Error Type:** `{r.primary_error_type.value}`")
                st.markdown(f"**Violated Clause:** `{r.violated_clause or 'N/A'}`")
                st.markdown(f"**Tests:** {r.passed_tests}/{r.total_tests} passed")

                if r.unsupported_success:
                    st.error("⚠️ UNSUPPORTED SUCCESS: Correct answer but flawed process!")

                if r.suspect_code_lines:
                    st.markdown("**Suspicious Code Lines (SBFL):**")
                    for sl in r.suspect_code_lines[:5]:
                        st.markdown(f"  - Line {sl.line}: score={sl.score:.3f} — {sl.reason}")

                if r.evidence:
                    with st.details("Show Evidence"):
                        for ev in r.evidence[:10]:
                            status_emoji = "🔴" if ev.status == "contradicted" else "🟡" if ev.status == "warning" else "🟢"
                            st.markdown(f"{status_emoji} [`ev.source`] {ev.detail}")

    elif page == "Analysis":
        st.header("Analysis & Insights")

        if not metrics:
            st.warning("No metrics found. Run evaluation first.")
            return

        # Error type distribution
        st.subheader("Error Type Distribution")
        if metrics.error_type_distribution:
            chart_data = {
                "error_type": list(metrics.error_type_distribution.keys()),
                "count": list(metrics.error_type_distribution.values()),
            }
            st.bar_chart(chart_data, x="error_type", y="count")
        else:
            st.info("No errors recorded.")

        # Difficulty breakdown
        st.subheader("Difficulty Breakdown")
        if metrics.difficulty_breakdown:
            for diff, data in metrics.difficulty_breakdown.items():
                with st.expander(f"{diff.title()} (n={data['count']})"):
                    col_a, col_b = st.columns(2)
                    col_a.metric("Final Accuracy", f"{data['final_accuracy']:.1%}")
                    col_b.metric("Process Accuracy", f"{data['process_accuracy']:.1%}")

                    if data.get("common_errors"):
                        st.markdown("**Common Errors:**")
                        for err in data["common_errors"]:
                            st.markdown(f"- `{err['error_type']}`: {err['count']} times")

        # First error step distribution
        step_errors = {}
        step_names = {
            "S1": "Requirement Understanding",
            "S2": "Constraints & Edge Cases",
            "S3": "Algorithm Choice",
            "S4": "Correctness Argument",
            "S5": "Complexity Analysis",
            "S6": "Self-Test Plan",
            "S7": "Code Implementation",
        }
        for r in results:
            if r.first_error_step:
                step_errors[r.first_error_step] = step_errors.get(r.first_error_step, 0) + 1

        if step_errors:
            st.subheader("First Error Step Distribution")
            step_chart = {
                "step": [f"{s} ({step_names.get(s, '')})" for s in step_errors.keys()],
                "count": list(step_errors.values()),
            }
            st.bar_chart(step_chart, x="step", y="count")

    elif page == "Error Taxonomy":
        st.header("Error Type Taxonomy")
        st.markdown("""
        The system uses a standardized error classification system:

        | Error Type | Description | Typical Step |
        |------------|-------------|--------------|
        | `FORMAT_ERROR` | Output doesn't match required format | S7 |
        | `SPEC_MISREAD` | Problem statement misunderstood | S1 |
        | `CONDITION_MISSING` | Edge case or condition not handled | S2 |
        | `UNJUSTIFIED_ASSUMPTION` | Assumption made without evidence | S3-S4 |
        | `ALGORITHM_INVALID` | Chosen algorithm is wrong for the problem | S3 |
        | `REASONING_GAP` | Logical jump without justification | S4 |
        | `COMPLEXITY_MISCLAIM` | Stated complexity doesn't match code | S5 |
        | `EDGE_CASE_FAILURE` | Fails on boundary inputs | S2, S7 |
        | `PLAN_CODE_MISMATCH` | Code doesn't implement the plan | S7 |
        | `PROCESS_RESULT_MISMATCH` | Right answer, wrong reasoning | Any |
        | `RUNTIME_ERROR` | Code throws an exception | S7 |
        | `TIMEOUT` | Execution exceeded time limit | S7 |
        | `SECURITY_VIOLATION` | Dangerous code pattern detected | S7 |

        ### Step Definitions
        """)

        steps = [
            ("S1", "Requirement Understanding", "What does the problem ask? What are inputs/outputs?"),
            ("S2", "Constraints & Edge Cases", "What boundaries, empty inputs, duplicates exist?"),
            ("S3", "Algorithm Choice", "What approach/algorithm and why?"),
            ("S4", "Correctness Argument", "Why is this approach correct? Proof sketch."),
            ("S5", "Complexity Analysis", "Time and space complexity with justification."),
            ("S6", "Self-Test Plan", "What test cases would verify correctness?"),
            ("S7", "Code Implementation", "The complete Python function."),
        ]

        for sid, name, desc in steps:
            st.markdown(f"**{sid} — {name}**: {desc}")

        st.markdown("---")
        st.caption("Built for the Rhino Bird Open Source Program - Hunyuan LLM Project.")


if __name__ == "__main__":
    main()
