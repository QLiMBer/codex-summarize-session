"""Shared exports for the session summaries feature."""
from __future__ import annotations

from .openrouter_client import (
    AuthenticationError,
    ChatCompletionResult,
    ClientConfigurationError,
    OpenRouterClient,
    OpenRouterError,
    RateLimitError,
    TransientError,
)
from .prompts import PromptDocument, PromptLoader, PromptValidationError
from .service import SummaryService
from .storage import SummaryPathResolver, load_summary, write_summary
from .types import SummaryRecord, SummaryRequest


__all__ = [
    "SummaryRequest",
    "SummaryRecord",
    "SummaryPathResolver",
    "PromptLoader",
    "PromptDocument",
    "PromptValidationError",
    "load_summary",
    "write_summary",
    "OpenRouterClient",
    "ChatCompletionResult",
    "OpenRouterError",
    "AuthenticationError",
    "RateLimitError",
    "TransientError",
    "ClientConfigurationError",
    "SummaryService",
]
