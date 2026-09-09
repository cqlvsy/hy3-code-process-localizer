"""Hy3 API client supporting OpenAI-compatible and Tencent Cloud backends."""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from .config import get_settings
from .schemas import SolutionRecord

logger = logging.getLogger(__name__)


class Hy3Client:
    """Client for interacting with Hy3.

    Supports two backends selected by ``settings.hy3_provider``:

    * ``"openai"``       -> OpenAI-compatible endpoint (HY3_BASE_URL + HY3_API_KEY)
    * ``"tencentcloud"`` -> Tencent Cloud Hunyuan service
                            (TENCENTCLOUD_SECRET_ID / TENCENTCLOUD_SECRET_KEY)

    Only the Tencent Cloud path is used when live cloud credentials are
    supplied; the OpenAI path remains for self-hosted vLLM/SGLang deployments.
    """

    def __init__(self, settings: Optional[Any] = None):
        self.settings = settings or get_settings()
        self._backend = self.settings.hy3_provider
        if self._backend == "tencentcloud":
            self._init_tencentcloud()
        else:
            self._init_openai()

    # ------------------------------------------------------------------
    # Backend initialisation
    # ------------------------------------------------------------------
    def _init_openai(self) -> None:
        from openai import OpenAI

        self._openai = OpenAI(
            base_url=self.settings.hy3_base_url,
            api_key=self.settings.hy3_api_key,
            timeout=self.settings.hy3_timeout,
        )

    def _init_tencentcloud(self) -> None:
        from tencentcloud.common import credential
        from tencentcloud.common.profile.client_profile import ClientProfile
        from tencentcloud.common.profile.http_profile import HttpProfile
        from tencentcloud.hunyuan.v20230901 import hunyuan_client

        secret_id = self.settings.tencentcloud_secret_id
        secret_key = self.settings.tencentcloud_secret_key
        if not secret_id or not secret_key:
            raise ValueError(
                "TENCENTCLOUD_SECRET_ID and TENCENTCLOUD_SECRET_KEY must be set "
                "when HY3_PROVIDER=tencentcloud"
            )
        cred = credential.Credential(secret_id, secret_key)
        http_profile = HttpProfile()
        http_profile.endpoint = "hunyuan.tencentcloudapi.com"
        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile
        self._tc_client = hunyuan_client.HunyuanClient(cred, "", client_profile)

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> tuple[str, int]:
        """Send a generation request. Returns (response_text, latency_ms)."""
        start = time.monotonic()
        content = self._generate_raw(system_prompt, user_prompt, temperature, max_tokens)
        latency_ms = int((time.monotonic() - start) * 1000)
        return content, latency_ms

    def _generate_raw(self, system_prompt, user_prompt, temperature, max_tokens) -> str:
        if self._backend == "tencentcloud":
            return self._generate_tencentcloud(
                system_prompt, user_prompt, temperature, max_tokens
            )
        return self._generate_openai(system_prompt, user_prompt, temperature, max_tokens)

    def _generate_openai(self, system_prompt, user_prompt, temperature, max_tokens) -> str:
        import httpx  # type: ignore

        last_err: Exception | None = None
        for attempt in range(self.settings.hy3_max_retries + 1):
            try:
                response = self._openai.chat.completions.create(
                    model=self.settings.hy3_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=temperature or self.settings.hy3_temperature,
                    max_tokens=max_tokens or self.settings.hy3_max_tokens,
                    extra_body={"reasoning_effort": self.settings.hy3_reasoning_effort},
                    timeout=self.settings.hy3_request_timeout,
                )
                return response.choices[0].message.content or ""
            except (httpx.TimeoutException, httpx.HTTPStatusError, Exception) as e:  # noqa: BLE001
                last_err = e
                if attempt < self.settings.hy3_max_retries:
                    # Exponential backoff for rate limits / transient errors.
                    sleep_s = min(2 ** attempt, 30)
                    logger.warning(
                        "Hy3 OpenAI call attempt %d failed (%s); retrying in %.0fs",
                        attempt + 1, type(e).__name__, sleep_s,
                    )
                    time.sleep(sleep_s)
                else:
                    raise
        # Should be unreachable; keep mypy happy.
        assert last_err is not None
        raise last_err

    def _generate_tencentcloud(self, system_prompt, user_prompt, temperature, max_tokens) -> str:
        from tencentcloud.hunyuan.v20230901 import models

        req = models.ChatCompletionsRequest()
        req.Model = self.settings.hy3_model

        sys_msg = models.Message()
        sys_msg.Role = "system"
        sys_msg.Content = system_prompt
        user_msg = models.Message()
        user_msg.Role = "user"
        user_msg.Content = user_prompt
        req.Messages = [sys_msg, user_msg]

        if temperature is not None:
            req.Temperature = float(temperature)
        # NOTE: this Hunyuan API version has no MaxTokens field; max_tokens is
        # intentionally ignored here.

        resp = self._tc_client.ChatCompletions(req)
        if not resp.Choices:
            return ""
        return resp.Choices[0].Message.Content or ""

    # ------------------------------------------------------------------
    # High-level helpers
    # ------------------------------------------------------------------
    def generate_solution(
        self, problem_prompt: str, entry_point: str, task_id: str = "unknown"
    ) -> SolutionRecord:
        """Generate a complete S1-S7 solution for a coding problem."""
        from .prompt_builder import build_solver_prompt

        system_prompt, user_prompt = build_solver_prompt(problem_prompt, entry_point)

        raw_response, latency_ms = self.generate(system_prompt, user_prompt)

        from .parser import parse_solution_response

        solution = parse_solution_response(raw_response, task_id=task_id)
        solution.raw_response = raw_response
        solution.generation_time_ms = latency_ms

        return solution

    def review_solution(
        self,
        problem: Any,
        solution: SolutionRecord,
        eval_result: Any,
        evidence: list,
    ) -> list:
        """Use Hy3 to review a solution's process quality.

        Returns a list of EvidenceRecord objects.
        """
        from .parser import parse_reviewer_response
        from .prompt_builder import build_reviewer_prompt

        system_prompt, user_prompt = build_reviewer_prompt(
            problem=problem,
            solution=solution,
            eval_result=eval_result,
            existing_evidence=evidence,
        )

        raw_response, _latency = self.generate(system_prompt, user_prompt)

        return parse_reviewer_response(raw_response)

    def health_check(self) -> bool:
        """Check if Hy3 API is reachable with a minimal call.

        Note: hy3 with ``reasoning_effort`` enabled consumes reasoning tokens
        before producing final content, so we must leave a generous token
        budget — a tiny ``max_tokens`` would return empty content even on a
        successful call.
        """
        try:
            text, _ = self.generate(
                "You are a helpful coding assistant.",
                "Reply with exactly the single word: OK",
                temperature=0,
                max_tokens=512,
            )
            return bool(text and text.strip())
        except Exception as e:  # noqa: BLE001
            logger.warning("Hy3 health check failed: %s", e)
            return False
