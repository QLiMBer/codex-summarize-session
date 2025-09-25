"""Thin OpenRouter API wrapper used by the summaries service."""
from __future__ import annotations

import json
import math
import random
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Mapping, MutableMapping, Optional, Sequence

import httpx

if TYPE_CHECKING:
    from .types import SummaryRequest


class OpenRouterError(RuntimeError):
    """Base error raised for OpenRouter failures."""


class AuthenticationError(OpenRouterError):
    """Raised when the API key is missing or invalid."""


class RateLimitError(OpenRouterError):
    """Raised when OpenRouter returns HTTP 429 after retries."""


class TransientError(OpenRouterError):
    """Raised for recoverable HTTP 5xx errors exceeding retry limits."""


class ClientConfigurationError(OpenRouterError):
    """Raised when the client receives an unexpected payload."""


@dataclass
class ChatCompletionResult:
    """Simplified view of a chat completion response."""

    content: str
    usage: Mapping[str, Any]
    raw: Mapping[str, Any]
    reasoning: Optional[Mapping[str, Any]] = None
    finish_reason: Optional[str] = None


class OpenRouterClient:
    """Co-ordinates requests to OpenRouter's chat completions endpoint."""

    _DEFAULT_TIMEOUT = 60.0
    _DEFAULT_MAX_RETRIES = 3
    _RETRY_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}
    _MODEL_CACHE_TTL = timedelta(hours=1)

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        *,
        referer: Optional[str] = None,
        title: Optional[str] = None,
        timeout: float = _DEFAULT_TIMEOUT,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        model_cache_path: Optional[Path] = None,
    ) -> None:
        if not api_key:
            raise AuthenticationError("OpenRouter API key is required")

        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max(0, max_retries)
        self._model_cache_path = model_cache_path
        self._model_cache: Optional[Dict[str, Any]] = None
        self._model_cache_timestamp: Optional[datetime] = None

        if self._model_cache_path and self._model_cache_path.is_file():
            self._load_model_cache()

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if referer:
            headers["HTTP-Referer"] = referer
        if title:
            headers["X-Title"] = title

        self._client = httpx.Client(base_url=self.base_url, headers=headers, timeout=self.timeout)

    def close(self) -> None:
        self._client.close()

    # ------------------------------
    # Chat completions
    # ------------------------------
    def generate(
        self,
        request: "SummaryRequest",
        messages: Sequence[Mapping[str, Any]],
        *,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        reasoning: Optional[Mapping[str, Any]] = None,
        extra_payload: Optional[Mapping[str, Any]] = None,
    ) -> ChatCompletionResult:
        """Submit a summary request and return the normalized response payload."""

        payload: Dict[str, Any] = {
            "model": request.model,
            "messages": list(messages),
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if reasoning is not None:
            payload["reasoning"] = dict(reasoning)
        elif request.reasoning_effort:
            payload["reasoning"] = {"effort": request.reasoning_effort}

        if extra_payload:
            payload.update(extra_payload)

        response_data = self._post_with_retries("/chat/completions", payload)
        return self._parse_chat_completion(response_data)

    # ------------------------------
    # Model metadata
    # ------------------------------
    def model_catalog(self, *, force_refresh: bool = False) -> Mapping[str, Any]:
        """Return cached model metadata, refreshing from the API when needed."""

        if not force_refresh and self._model_cache and self._model_cache_timestamp:
            if datetime.now(timezone.utc) - self._model_cache_timestamp < self._MODEL_CACHE_TTL:
                return self._model_cache

        response_data = self._get_with_retries("/models")
        models = response_data.get("data")
        if not isinstance(models, list):
            raise ClientConfigurationError("OpenRouter models endpoint returned unexpected payload")

        indexed = {model.get("id"): model for model in models if isinstance(model, dict) and model.get("id")}
        self._model_cache = indexed
        self._model_cache_timestamp = datetime.now(timezone.utc)

        if self._model_cache_path:
            self._write_model_cache({"timestamp": self._model_cache_timestamp.isoformat(), "data": models})

        return indexed

    def estimate_cost(self, model: str, usage: Mapping[str, Any]) -> Optional[Dict[str, float]]:
        """Estimate USD pricing for a completion using cached model metadata."""

        catalog = self.model_catalog()
        model_info = catalog.get(model)
        if not model_info:
            return None

        pricing = model_info.get("pricing")
        if not isinstance(pricing, Mapping):
            return None

        prompt_cost = _cost_component(pricing.get("prompt"), usage.get("prompt_tokens"))
        completion_cost = _cost_component(pricing.get("completion"), usage.get("completion_tokens"))

        if prompt_cost is None and completion_cost is None:
            return None

        total = 0.0
        components = {}
        if prompt_cost is not None:
            components["prompt"] = prompt_cost
            total += prompt_cost
        if completion_cost is not None:
            components["completion"] = completion_cost
            total += completion_cost
        components["total"] = total
        return components

    # ------------------------------
    # HTTP helpers
    # ------------------------------
    def _post_with_retries(self, path: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return self._request_with_retries("POST", path, json=payload)

    def _get_with_retries(self, path: str) -> Mapping[str, Any]:
        return self._request_with_retries("GET", path)

    def _request_with_retries(self, method: str, path: str, **kwargs: Any) -> Mapping[str, Any]:
        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self._client.request(method, path, **kwargs)
            except httpx.HTTPError as exc:  # network issues
                last_error = exc
                sleep_for = self._backoff_seconds(attempt)
                time.sleep(sleep_for)
                continue

            if response.status_code == 401:
                raise AuthenticationError("OpenRouter rejected the API key (401)")
            if response.status_code == 403:
                raise AuthenticationError("OpenRouter denied access (403)")

            if response.status_code in self._RETRY_STATUS_CODES and attempt < self.max_retries:
                sleep_for = self._backoff_seconds(attempt, response)
                time.sleep(sleep_for)
                continue

            if response.status_code >= 400:
                body = self._safe_json(response)
                message = body.get("error", {}).get("message") if isinstance(body, dict) else response.text
                if response.status_code == 429:
                    raise RateLimitError(message or "OpenRouter rate limit exceeded (429)")
                if response.status_code >= 500:
                    raise TransientError(message or f"OpenRouter server error ({response.status_code})")
                raise OpenRouterError(message or f"OpenRouter request failed ({response.status_code})")

            return self._safe_json(response)

        # Retries exhausted
        if isinstance(last_error, httpx.TimeoutException):
            raise TransientError("OpenRouter request timed out after retries") from last_error
        raise TransientError("OpenRouter request failed after retries") from last_error

    def _safe_json(self, response: httpx.Response) -> Mapping[str, Any]:
        try:
            data = response.json()
        except ValueError as exc:
            raise ClientConfigurationError("OpenRouter returned a non-JSON response") from exc
        if not isinstance(data, Mapping):
            raise ClientConfigurationError("OpenRouter response was not a JSON object")
        return data

    def _backoff_seconds(self, attempt: int, response: Optional[httpx.Response] = None) -> float:
        base = min(2 ** attempt, 16)
        jitter = random.uniform(0.5, 1.5)
        retry_after = 0.0
        if response is not None:
            retry_after_header = response.headers.get("Retry-After")
            if retry_after_header:
                try:
                    retry_after = float(retry_after_header)
                except ValueError:
                    pass
        return max(0.5, base * jitter + retry_after)

    def _parse_chat_completion(self, data: Mapping[str, Any]) -> ChatCompletionResult:
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ClientConfigurationError("OpenRouter chat response missing choices")

        first_choice = choices[0]
        message = first_choice.get("message")
        if not isinstance(message, Mapping):
            raise ClientConfigurationError("OpenRouter chat response missing message content")

        content = message.get("content")
        if not isinstance(content, str):
            raise ClientConfigurationError("OpenRouter chat response missing text content")

        usage = data.get("usage", {})
        if not isinstance(usage, MutableMapping):
            usage = dict(usage) if isinstance(usage, Mapping) else {}

        reasoning = message.get("reasoning") or first_choice.get("reasoning") or data.get("reasoning")
        finish_reason = first_choice.get("finish_reason")

        return ChatCompletionResult(
            content=content,
            usage=usage,
            reasoning=reasoning if isinstance(reasoning, Mapping) else None,
            finish_reason=finish_reason if isinstance(finish_reason, str) else None,
            raw=data,
        )

    # ------------------------------
    # Model cache persistence helpers
    # ------------------------------
    def _load_model_cache(self) -> None:
        try:
            payload = json.loads(self._model_cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return

        timestamp_str = payload.get("timestamp")
        data = payload.get("data")
        if not timestamp_str or not isinstance(data, list):
            return
        try:
            timestamp = datetime.fromisoformat(timestamp_str)
        except ValueError:
            return

        indexed = {model.get("id"): model for model in data if isinstance(model, dict) and model.get("id")}
        if indexed:
            self._model_cache = indexed
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            self._model_cache_timestamp = timestamp

    def _write_model_cache(self, payload: Mapping[str, Any]) -> None:
        if not self._model_cache_path:
            return
        try:
            self._model_cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._model_cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError:
            # Non-fatal; caching is best effort.
            pass


def _cost_component(price_per_1k: Any, tokens: Any) -> Optional[float]:
    try:
        price = float(price_per_1k)
        token_count = float(tokens)
    except (TypeError, ValueError):
        return None
    if math.isinf(price) or math.isnan(price) or math.isinf(token_count) or math.isnan(token_count):
        return None
    return round((price / 1000.0) * token_count, 6)
