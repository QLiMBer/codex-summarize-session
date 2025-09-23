"""Prompt template helpers for the summaries feature."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence


class PromptValidationError(ValueError):
    """Raised when a prompt template fails validation checks."""


@dataclass(frozen=True)
class PromptDocument:
    """Represents a loaded prompt template and its source path."""

    content: str
    path: Path


class PromptLoader:
    """Resolve prompt names to files and apply lightweight validation."""

    def __init__(
        self,
        prompts_dir: Optional[Path] = None,
        extra_search_dirs: Optional[Sequence[Path]] = None,
    ) -> None:
        default_dir = Path(__file__).resolve().parent / "prompts"
        self._search_dirs = [default_dir]
        if prompts_dir:
            self._search_dirs.insert(0, Path(prompts_dir).expanduser())
        if extra_search_dirs:
            for directory in extra_search_dirs:
                expanded = Path(directory).expanduser()
                if expanded not in self._search_dirs:
                    self._search_dirs.append(expanded)

    def resolve(self, prompt: str) -> Path:
        candidate_path = Path(prompt).expanduser()
        if candidate_path.is_file():
            return candidate_path

        for directory in self._search_dirs:
            for variant in self._variant_candidates(directory, prompt):
                if variant.is_file():
                    return variant

        search_roots = ", ".join(str(d) for d in self._search_dirs)
        raise FileNotFoundError(
            f"Prompt '{prompt}' was not found. Checked {candidate_path} and search dirs: {search_roots}."
        )

    def load(self, prompt: str) -> PromptDocument:
        path = self.resolve(prompt)
        content = path.read_text(encoding="utf-8")
        self._validate(content, path)
        return PromptDocument(content=content, path=path)

    def _variant_candidates(self, base_dir: Path, prompt: str) -> Iterable[Path]:
        name = prompt if "." in prompt else f"{prompt}.md"
        yield base_dir / name
        if not name.endswith(".txt"):
            yield base_dir / f"{prompt}.txt"

    def _validate(self, content: str, path: Path) -> None:
        open_tokens = content.count("{{")
        close_tokens = content.count("}}")
        if open_tokens != close_tokens:
            raise PromptValidationError(
                f"Prompt '{path}' has mismatched template braces: {open_tokens} '{{{{' vs {close_tokens} '}}}}'."
            )
        if "{{" not in content:
            raise PromptValidationError(
                f"Prompt '{path}' does not include any template placeholders; expected at least one '{{{{...}}}}'."
            )
