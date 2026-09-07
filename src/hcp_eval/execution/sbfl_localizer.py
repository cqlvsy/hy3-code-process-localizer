"""Coverage collection and SBFL (Ochiai) fault localization."""

from __future__ import annotations

import json
import logging
import math
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ..schemas import EvidenceRecord, SuspectCodeLine

logger = logging.getLogger(__name__)


@dataclass
class CoverageData:
    """Coverage information for a single test execution."""

    test_id: str
    passed: bool
    covered_lines: set[int] = field(default_factory=set)


def collect_coverage(
    function_code: str,
    test_code: str,
    function_name: str = "solution",
    work_dir: Optional[Path] = None,
) -> CoverageData:
    """
    Run a single test with coverage.py and return which lines were executed.

    Returns CoverageData with covered line numbers.
    """
    # Create a temporary script that runs coverage
    script = f"""
import coverage
cov = coverage.Coverage(source=["{function_name}"], branch=False)
cov.start()

{function_code}

{test_code}

cov.stop()
cov.save()
import json
data = cov.get_data()
# Get lines executed in the current file
lines = set()
for filename in data.measured_files():
    lines.update(data.lines(filename) or [])
print(json.dumps({{"covered": sorted(lines)}}))
"""

    work_dir = work_dir or Path(tempfile.mkdtemp())
    script_path = work_dir / "_coverage_run.py"

    try:
        script_path.write_text(script)

        result = subprocess.run(
            ["python3", str(script_path)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(work_dir),
        )

        covered = set()
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout.strip())
                covered = set(data.get("covered", []))
            except (json.JSONDecodeError, ValueError):
                pass

        # Determine if test passed based on exit code
        passed = result.returncode == 0

        return CoverageData(
            test_id=f"test_{id(test_code)}",
            passed=passed,
            covered_lines=covered,
        )

    except subprocess.TimeoutExpired:
        return CoverageData(test_id="timeout", passed=False, covered_lines=set())
    except Exception as e:
        logger.debug("Coverage collection error: %s", e)
        return CoverageData(test_id="error", passed=False, covered_lines=set())
    finally:
        # Cleanup
        if script_path.exists():
            script_path.unlink(missing_ok=True)
        for f in work_dir.glob(".coverage*"):
            f.unlink(missing_ok=True)


def compute_ochiai(
    coverage_data: list[CoverageData],
    all_line_numbers: set[int],
) -> list[SuspectCodeLine]:
    """
    Compute Ochiai suspiciousness scores for each code line.

    Ochiai formula:
        score(line) = failed_cover(line) / sqrt(total_failed * (failed_cover(line) + passed_cover(line)))

    Args:
        coverage_data: List of coverage results for each test.
        all_line_numbers: All line numbers in the code.

    Returns:
        List of SuspectCodeLine sorted by descending suspiciousness.
    """
    # Separate passing and failing tests
    failing_tests = [c for c in coverage_data if not c.passed]
    passing_tests = [c for c in coverage_data if c.passed]

    total_failed = len(failing_tests)
    if total_failed == 0:
        # All tests passed - no suspicious lines
        return []

    suspect_lines: list[SuspectCodeLine] = []

    for line_num in sorted(all_line_numbers):
        # Count how many failing and passing tests cover this line
        failed_cover = sum(1 for t in failing_tests if line_num in t.covered_lines)
        passed_cover = sum(1 for t in passing_tests if line_num in t.covered_lines)

        # Ochiai formula
        denominator = math.sqrt(total_failed * (failed_cover + passed_cover))
        if denominator > 0:
            score = failed_cover / denominator
        else:
            score = 0.0

        if score > 0.01:  # Only include lines with meaningful scores
            reason = (
                f"covered by {failed_cover} failing test(s) and "
                f"{passed_cover} passing test(s)"
            )
            suspect_lines.append(
                SuspectCodeLine(
                    line=line_num,
                    score=round(score, 4),
                    reason=reason,
                )
            )

    # Sort by score descending
    suspect_lines.sort(key=lambda x: x.score, reverse=True)
    return suspect_lines


def run_sbfl_analysis(
    function_code: str,
    base_tests: list[str],
    plus_tests: list[str],
    base_results: list[Any],
    plus_results: list[Any],
    function_name: str = "solution",
) -> tuple[list[SuspectCodeLine], list[EvidenceRecord]]:
    """
    Run full SBFL analysis combining base and plus test results.

    Returns:
        Tuple of (suspect_lines, evidence_records)
    """
    evidence: list[EvidenceRecord] = []

    # Combine all tests and results
    all_tests = base_tests + plus_tests
    all_results = base_results + plus_results

    # Collect coverage for each test
    coverage_data: list[CoverageData] = []
    work_dir = Path(tempfile.mkdtemp())

    for i, (test, result) in enumerate(zip(all_tests, all_results)):
        cd = collect_coverage(function_code, test, function_name, work_dir)
        cd.passed = getattr(result, "passed", True)
        cd.test_id = f"{'base' if i < len(base_tests) else 'plus'}_{i}"
        coverage_data.append(cd)

    # Determine all line numbers in the code
    all_lines = set(range(1, len(function_code.splitlines()) + 1))

    # Compute Ochiai scores
    suspect_lines = compute_ochiai(coverage_data, all_lines)

    # Generate SBFL evidence
    if suspect_lines:
        top_suspect = suspect_lines[0]
        evidence.append(
            EvidenceRecord(
                source="sbfl",
                status="contradicted" if any(not c.passed for c in coverage_data) else "verified",
                detail=(
                    f"SBFL (Ochiai) identified {len(suspect_lines)} suspicious line(s). "
                    f"Most suspicious: line {top_suspect.line} (score={top_suspect.score:.3f}), "
                    f"{top_suspect.reason}"
                ),
                target_step="S7",  # Code-level issues map to S7
                confidence=top_suspect.score,
                metadata={"total_suspect_lines": len(suspect_lines)},
            )
        )

    # Cleanup
    import shutil
    try:
        shutil.rmtree(work_dir, ignore_errors=True)
    except Exception:
        pass

    return suspect_lines, evidence
