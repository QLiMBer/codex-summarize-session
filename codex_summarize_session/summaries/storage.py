"""Filesystem helpers for locating and persisting summary artifacts."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, Optional, Tuple

import yaml

from .types import SummaryRecord

_FRONT_MATTER_DELIMITER = "---"
_DEFAULT_SUMMARY_FILENAME = "summary.md"
_SUMMARY_MESSAGES_FILENAME = "summary.messages.jsonl"
_INDEX_FILENAME = "index.jsonl"


class SummaryPathResolver:
    """Determines where summaries and indexes live on disk."""

    def __init__(self, summary_root: Path, sessions_root: Optional[Path] = None) -> None:
        self.summary_root = summary_root.expanduser().resolve()
        self.sessions_root = sessions_root.expanduser().resolve() if sessions_root else None

    def cache_path_for(self, session_path: Path, prompt_variant: str, model: str) -> Path:
        """Return the markdown path where the summary should live."""
        session_path = Path(session_path).expanduser().resolve()
        relative_dir = self._relative_source_dir(session_path)
        prompt_slug = _slugify(prompt_variant)
        _ = model  # retained for signature compatibility; model tracked via metadata.
        return self.summary_root / relative_dir / prompt_slug / _DEFAULT_SUMMARY_FILENAME

    def summary_dir_for(self, session_path: Path) -> Path:
        """Return the directory containing cached summaries for the session."""
        session_path = Path(session_path).expanduser().resolve()
        relative_dir = self._relative_source_dir(session_path)
        return self.summary_root / relative_dir

    def cached_variants_for(self, session_path: Path) -> Dict[str, Path]:
        """Return a mapping of cached prompt variants to their markdown paths."""
        summary_dir = self.summary_dir_for(session_path)
        variants: Dict[str, Path] = {}
        if not summary_dir.is_dir():
            return variants
        for child in sorted(summary_dir.iterdir(), key=lambda p: p.name):
            if not child.is_dir():
                continue
            summary_path = child / _DEFAULT_SUMMARY_FILENAME
            if summary_path.is_file():
                variants[child.name] = summary_path
        return variants

    def index_path_for(self, session_path: Path) -> Path:
        """Return the JSONL index path used to list cached variants."""
        session_path = Path(session_path).expanduser().resolve()
        relative_dir = self._relative_source_dir(session_path)
        return self.summary_root / relative_dir / _INDEX_FILENAME

    def messages_path_for(self, session_path: Path) -> Path:
        session_path = Path(session_path).expanduser().resolve()
        relative_dir = self._relative_source_dir(session_path)
        return self.summary_root / relative_dir / _SUMMARY_MESSAGES_FILENAME

    def _relative_source_dir(self, session_path: Path) -> Path:
        if self.sessions_root:
            try:
                return session_path.relative_to(self.sessions_root)
            except ValueError:
                pass

        digest = hashlib.sha1(str(session_path).encode("utf-8")).hexdigest()[:12]
        external_label = _slugify(session_path.stem)
        return Path("external") / f"{digest}-{external_label}"


def load_summary(markdown_path: Path) -> SummaryRecord:
    """Read a summary markdown file and return a normalized record."""
    markdown_path = Path(markdown_path)
    raw_text = markdown_path.read_text(encoding="utf-8")
    metadata, body = _split_front_matter(raw_text)
    return SummaryRecord(
        body=body,
        cache_path=markdown_path,
        metadata=metadata,
        cached=True,
    )


def write_summary(markdown_path: Path, body: str, metadata: Dict[str, object]) -> SummaryRecord:
    """Persist summary markdown with YAML front matter and return the record."""
    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict):
        raise TypeError("metadata must be a mapping")
    serialized_metadata = dict(metadata)
    front_matter = yaml.safe_dump(serialized_metadata, sort_keys=True, allow_unicode=False).strip()
    sections = [
        f"{_FRONT_MATTER_DELIMITER}\n{front_matter}\n{_FRONT_MATTER_DELIMITER}"
    ] if serialized_metadata else []
    body = body if body.endswith("\n") else f"{body}\n"
    if sections:
        sections.append("")  # blank line between metadata and body
    sections.append(body)
    markdown_path.write_text("\n".join(sections), encoding="utf-8")
    return SummaryRecord(body=body, cache_path=markdown_path, metadata=serialized_metadata, cached=True)


def _slugify(value: str) -> str:
    normalized = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    parts = [part for part in normalized.split("-") if part]
    slug = "-".join(parts)
    return slug or "default"


def _split_front_matter(content: str) -> Tuple[Dict[str, object], str]:
    lines = content.splitlines()
    if not lines or lines[0].strip() != _FRONT_MATTER_DELIMITER:
        return {}, content

    for idx in range(1, len(lines)):
        if lines[idx].strip() == _FRONT_MATTER_DELIMITER:
            front_matter_lines = lines[1:idx]
            body_lines = lines[idx + 1 :]
            front_matter_text = "\n".join(front_matter_lines).strip()
            metadata = yaml.safe_load(front_matter_text) if front_matter_text else {}
            if metadata is None:
                metadata = {}
            if not isinstance(metadata, dict):
                raise ValueError(
                    "Summary front matter must deserialize to a mapping"
                )
            body = "\n".join(body_lines)
            if body and not body.endswith("\n"):
                body = f"{body}\n"
            return metadata, body

    # No closing delimiter found; treat entire file as body to avoid data loss.
    return {}, content if content.endswith("\n") else f"{content}\n"
