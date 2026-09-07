"""Sandbox-based code execution for candidate solutions."""

from __future__ import annotations

import io
import logging
import sys
import tempfile
import traceback
from contextlib import redirect_stderr, redirect_stdout
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ExecutionResult:
    """Result of executing a single test case."""

    def __init__(
        self,
        test_code: str,
        passed: bool,
        error: Optional[str] = None,
        output: str = "",
        timeout: bool = False,
        duration_ms: float = 0.0,
    ):
        self.test_code = test_code
        self.passed = passed
        self.error = error
        self.output = output
        self.timeout = timeout
        self.duration_ms = duration_ms


class SandboxRunner:
    """Execute Python code in an isolated environment."""

    def __init__(self, timeout: int = 30):
        """
        Args:
            timeout: Maximum execution time per test in seconds.
        """
        self.timeout = timeout

    def execute_function(
        self,
        function_code: str,
        test_code: str,
        function_name: str = "solution",
    ) -> ExecutionResult:
        """
        Execute a test against a candidate function.

        Args:
            function_code: The candidate function source code.
            test_code: The test assertion(s) to run.
            function_name: The name of the function being tested.

        Returns:
            ExecutionResult with pass/fail status and details.
        """
        import signal
        import time

        # Build complete executable script
        full_code = f"{function_code}\n\n{test_code}"

        start_time = time.monotonic()
        output_buffer = io.StringIO()
        error_buffer = io.StringIO()

        # Timeout handler
        timed_out = [False]

        def timeout_handler(signum, frame):
            timed_out[0] = True
            raise TimeoutError(f"Execution exceeded {self.timeout}s limit")

        # Set up execution namespace
        exec_namespace: dict[str, Any] = {"__builtins__": __builtins__}

        try:
            # Set timeout (Unix only)
            try:
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(self.timeout)
            except (ValueError, AttributeError):
                # Windows or main thread doesn't support SIGALRM
                pass

            with redirect_stdout(output_buffer), redirect_stderr(error_buffer):
                exec(compile(full_code, "<sandbox>", "exec"), exec_namespace)

            duration_ms = (time.monotonic() - start_time) * 1000
            return ExecutionResult(
                test_code=test_code,
                passed=True,
                output=output_buffer.getvalue(),
                duration_ms=duration_ms,
            )

        except TimeoutError:
            duration_ms = (time.monotonic() - start_time) * 1000
            return ExecutionResult(
                test_code=test_code,
                passed=False,
                error=f"Timeout after {self.timeout}s",
                timeout=True,
                duration_ms=duration_ms,
            )
        except AssertionError as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            return ExecutionResult(
                test_code=test_code,
                passed=False,
                error=f"Assertion failed: {e}",
                output=output_buffer.getvalue(),
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            tb = traceback.format_exc()
            return ExecutionResult(
                test_code=test_code,
                passed=False,
                error=f"{type(e).__name__}: {e}\n{tb}",
                output=output_buffer.getvalue(),
                duration_ms=duration_ms,
            )
        finally:
            try:
                signal.alarm(0)
            except (ValueError, AttributeError):
                pass

    def run_all_tests(
        self,
        function_code: str,
        tests: list[str],
        function_name: str = "solution",
    ) -> list[ExecutionResult]:
        """Run a list of tests against the candidate function."""
        results = []
        for test in tests:
            result = self.execute_function(function_code, test, function_name)
            results.append(result)
        return results
