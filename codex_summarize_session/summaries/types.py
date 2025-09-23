"""Dataclasses shared across the summaries feature."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional


@dataclass(frozen=True)
class SummaryRequest:
    """Immutable request payload used by both CLI and TUI callers."""

    session_path: Path
    prompt_variant: str
    model: str
    prompt_path: Optional[Path] = None
    reasoning_effort: Optional[str] = "medium"
    refresh: bool = False
    strip_metadata: bool = False


@dataclass
class SummaryRecord:
    """Normalized representation of a stored summary and its metadata."""

    body: str
    cache_path: Path
    metadata: Dict[str, object] = field(default_factory=dict)
    cached: bool = False
