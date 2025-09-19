# Changelog

All notable changes to this project will be documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
while it remains under the `0.x` line (breaking changes may still occur).

## [Unreleased]


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
