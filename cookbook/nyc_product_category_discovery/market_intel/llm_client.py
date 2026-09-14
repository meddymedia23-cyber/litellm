from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, TypeVar

from pydantic import BaseModel

from .config import RuntimeSettings

LOGGER = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class ModelStageError(RuntimeError):
    pass


def _redacted_error(exc: Exception, secrets: list[str]) -> str:
    message = str(exc)
    for secret in secrets:
        if secret:
            message = message.replace(secret, "[REDACTED]")
    message = re.sub(
        r"(?i)(api[-_ ]?key|authorization|bearer)([=: ]+)([^\s,;]+)",
        r"\1\2[REDACTED]",
        message,
    )
    return message[:1000]


@dataclass(frozen=True)
class StageResult:
    value: BaseModel
    model: str
    prompt_version: str
    latency_seconds: float
    input_tokens: int | None
    output_tokens: int | None

    def public_metadata(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "prompt_version": self.prompt_version,
            "latency_seconds": round(self.latency_seconds, 4),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }


class StructuredModelClient:
    def __init__(self, settings: RuntimeSettings):
        self.settings = settings

    async def call(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        response_model: type[T],
        prompt_version: str,
        web_search: bool = False,
    ) -> StageResult:
        try:
            from litellm import acompletion
        except ImportError as exc:
            raise ModelStageError(
                "LiteLLM is not importable; run from the repository environment or install litellm"
            ) from exc

        errors: list[str] = []
        secrets = [self.settings.proxy_key.get_secret_value()] if self.settings.proxy_key else []
        for attempt in range(self.settings.retries + 1):
            started = time.perf_counter()
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "response_format": response_model,
                "enable_json_schema_validation": True,
                "timeout": self.settings.timeout_seconds,
            }
            if self.settings.temperature is not None:
                kwargs["temperature"] = self.settings.temperature
            if self.settings.proxy_url:
                kwargs["api_base"] = self.settings.proxy_url
            if self.settings.proxy_key:
                kwargs["api_key"] = self.settings.proxy_key.get_secret_value()
            if web_search:
                kwargs["web_search_options"] = {"search_context_size": "high"}
            try:
                response = await acompletion(**kwargs)
                content = response.choices[0].message.content
                if isinstance(content, dict):
                    value = response_model.model_validate(content)
                elif isinstance(content, str):
                    value = response_model.model_validate_json(content)
                else:
                    raise ModelStageError("model returned empty or unsupported content")
                usage = getattr(response, "usage", None)
                return StageResult(
                    value=value,
                    model=model,
                    prompt_version=prompt_version,
                    latency_seconds=time.perf_counter() - started,
                    input_tokens=getattr(usage, "prompt_tokens", None),
                    output_tokens=getattr(usage, "completion_tokens", None),
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                # Provider exception classes vary across LiteLLM integrations. This boundary
                # lets the retry policy work across providers while preserving the final cause.
                message = f"attempt {attempt + 1}: {type(exc).__name__}: {_redacted_error(exc, secrets)}"
                errors.append(message)
                LOGGER.warning("structured model call failed: %s", message)
                if attempt < self.settings.retries:
                    await asyncio.sleep(min(2**attempt, 8))
        raise ModelStageError(f"stage {prompt_version} failed after {len(errors)} attempt(s): " + " | ".join(errors))
