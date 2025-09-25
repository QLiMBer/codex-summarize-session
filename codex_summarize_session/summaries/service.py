"""Shared orchestration layer for generating and caching summaries."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Mapping, Optional, Sequence

from ..messages import write_messages_jsonl
from .openrouter_client import ChatCompletionResult, OpenRouterClient
from .prompts import PromptLoader
from .storage import SummaryPathResolver, load_summary, write_summary
from .types import SummaryRecord, SummaryRequest


class SummaryService:
    """Public facade used by CLI commands and the TUI browser."""

    def __init__(
        self,
        summary_root: Path,
        sessions_root: Optional[Path] = None,
        *,
        openrouter_client: Optional[OpenRouterClient] = None,
        prompt_loader: Optional[PromptLoader] = None,
        path_resolver: Optional[SummaryPathResolver] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.summary_root = Path(summary_root).expanduser()
        self.sessions_root = Path(sessions_root).expanduser() if sessions_root else None
        self._client = openrouter_client
        self._prompt_loader = prompt_loader or PromptLoader()
        self._resolver = path_resolver or SummaryPathResolver(self.summary_root, self.sessions_root)
        self._logger = logger or logging.getLogger(__name__)

    def generate(
        self,
        request: SummaryRequest,
        use_cache: bool = True,
        refresh: bool = False,
        *,
        messages: Optional[Sequence[Mapping[str, object]]] = None,
        extra_payload: Optional[Mapping[str, object]] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
    ) -> SummaryRecord:
        """Return a summary, optionally using or bypassing the cache."""

        session_path = Path(request.session_path).expanduser()
        cache_path = self._resolver.cache_path_for(session_path, request.prompt_variant, request.model)
        messages_path = self._resolver.messages_path_for(session_path)

        if use_cache and not refresh:
            cached = self._try_load_cache(cache_path)
            if cached:
                message_count = self._ensure_messages_file(session_path, messages_path, refresh=False)
                if isinstance(cached.metadata, dict):
                    cached.metadata.setdefault("messages_path", str(messages_path))
                    if message_count is not None:
                        cached.metadata.setdefault("message_count", message_count)
                self._log_debug(
                    "cache-hit",
                    request,
                    {"cache_path": str(cache_path), "messages_path": str(messages_path)},
                )
                return cached

        client = self._require_client()
        prompt = self._load_prompt(request)
        message_count = self._ensure_messages_file(session_path, messages_path, refresh=refresh)
        prepared_messages = messages or self._default_messages(
            prompt.content, cache_path, messages_path, request
        )

        result = client.generate(
            request,
            prepared_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_payload=extra_payload,
        )

        metadata = self._build_metadata(
            request,
            prompt.path,
            messages_path,
            message_count,
            result,
        )
        record = write_summary(cache_path, result.content, metadata)
        record.cached = False
        cost = metadata.get("cost_estimate_usd", {}) if isinstance(metadata, dict) else {}
        self._log_debug(
            "cache-miss",
            request,
            {
                "cache_path": str(cache_path),
                "messages_path": str(messages_path),
                "model": request.model,
                "cost": cost,
            },
        )
        return record

    def get_cached_summary(self, request: SummaryRequest) -> Optional[SummaryRecord]:
        """Return an existing cached summary if one is available."""
        cache_path = self._resolver.cache_path_for(request.session_path, request.prompt_variant, request.model)
        return self._try_load_cache(cache_path)

    def _require_client(self) -> OpenRouterClient:
        if not self._client:
            raise RuntimeError("SummaryService requires an OpenRouterClient to generate summaries")
        return self._client

    def _load_prompt(self, request: SummaryRequest):
        return self._prompt_loader.load(request.prompt_variant)

    def _default_messages(
        self,
        prompt_content: str,
        cache_path: Path,
        messages_path: Path,
        request: SummaryRequest,
    ) -> List[Mapping[str, str]]:
        system_prompt = prompt_content.strip() or prompt_content
        with messages_path.open("r", encoding="utf-8") as messages_file:
            session_text = messages_file.read()
        transcript_body = session_text.rstrip("\n")
        transcript_block = (
            "<session start>\n"
            '"""' + "\n"
            f"{transcript_body}\n"
            '"""' + "\n"
            "</session end>"
        )
        user_message = transcript_block
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

    def _build_metadata(
        self,
        request: SummaryRequest,
        prompt_path: Path,
        messages_path: Path,
        message_count: Optional[int],
        result: ChatCompletionResult,
    ) -> Mapping[str, object]:
        metadata: dict[str, object] = {
            "model": request.model,
            "prompt_variant": request.prompt_variant,
            "prompt_path": str(prompt_path),
            "source_path": str(Path(request.session_path).expanduser()),
            "usage": dict(result.usage),
            "messages_path": str(messages_path),
        }
        if message_count is not None:
            metadata["message_count"] = message_count
        cost = self._client.estimate_cost(request.model, result.usage) if self._client else None
        if cost:
            metadata["cost_estimate_usd"] = cost
        if result.reasoning:
            metadata["reasoning"] = result.reasoning
        if result.finish_reason:
            metadata["finish_reason"] = result.finish_reason
        metadata["raw_response"] = result.raw
        return metadata

    def _try_load_cache(self, cache_path: Path) -> Optional[SummaryRecord]:
        if cache_path.is_file():
            return load_summary(cache_path)
        return None

    def _ensure_messages_file(
        self, session_path: Path, messages_path: Path, refresh: bool
    ) -> Optional[int]:
        if refresh or not messages_path.is_file():
            return write_messages_jsonl(session_path, messages_path)
        return None

    def _log_debug(self, event: str, request: SummaryRequest, extra: Mapping[str, object]) -> None:
        if not self._logger:
            return
        payload = {
            "event": event,
            "session_path": str(request.session_path),
            "prompt_variant": request.prompt_variant,
            "model": request.model,
        }
        payload.update(dict(extra))
        self._logger.debug("summary-service", extra={"summary": payload})
