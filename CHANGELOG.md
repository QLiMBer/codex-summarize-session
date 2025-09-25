# Changelog

All notable changes to this project will be documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
while it remains under the `0.x` line (breaking changes may still occur).

## [0.4.0] - 2025-09-25
### Added
- `codex-summarize-session summaries generate` CLI command that orchestrates OpenRouter calls, caches Markdown summaries, and emits cost metadata.
- Shared summary service and storage layer that mirror session paths, manage Markdown/YAML front matter, and reuse cleaned transcripts.
- TUI browse shortcuts (`s`, `g`, `G`) to view, generate, and refresh summaries without leaving the session list, including a detail pane with cache/cost status.

### Changed
- Simplified prompt handling: prompts are plain Markdown, passed as the system message, while transcripts are wrapped between `<session start>` markers for the user message.
- Unified prompt selection behind a single `--prompt` flag for both CLI and TUI and removed Python-format placeholders from templates.

### Documentation
- Captured the session-summary plan, OpenRouter analysis notes, and prompt workflow updates in `docs/session-summaries.md` and `README.md`.
- Recorded lessons learned from the initial session-summary experiments for future iterations.

## [0.3.0] - 2024-09-22
### Added
- Optional `[browser]` extra that provides `prompt_toolkit` support for the new interactive session browser.
- `codex-summarize-session browse` command with arrow-key navigation and in-place message extraction.

### Documentation
- Describe the interactive browser workflow and optional dependency in `README.md`.
- Clarify pip/pipx install flows, editable modes, and dependency messaging for the interactive browser.

## [0.2.0] - 2024-09-19
### Added
- Display each session's captured `cwd` when listing sessions.
- Allow `codex-summarize-session extract` to accept the numeric index shown by `list`.

### Fixed
- Repair invalid `[build-system]` table in `pyproject.toml` so editable installs succeed.
- Ensure `extract` emits messages when they are wrapped in `response_item` payloads (adds timestamps when present).

### Documentation
- Document new `list` output and index-based extraction in `README.md`.

## [0.1.0] - 2024-09-08
### Added
- Initial CLI capable of listing session JSONL files and extracting `type="message"` lines to a new file or stdout.
