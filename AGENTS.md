# Repository Guidelines

## Project Structure & Module Organization
The CLI lives under `codex_summarize_session/`; `cli.py` contains entrypoints and helpers for listing, extracting, and browsing session logs. Packaging metadata sits in `pyproject.toml`, while `README.md`, `ROADMAP.md`, and `RELEASE_PLAN.md` track user docs and future work. Build artifacts land in `build/` and `dist/` during packaging runs—treat them as disposable. Session JSONL fixtures are not committed; the tool reads from `~/.codex/sessions` or a user-supplied directory at runtime.

## Build, Test, and Development Commands
Install for development with `python -m pip install -e .[browser]` or `pipx install --editable .` followed by `pipx inject codex-summarize-session prompt_toolkit`. Run the CLI directly via `python -m codex_summarize_session.cli list --limit 5` or the installed `codex-summarize-session` script. After switching between pip and pipx, run `hash -r` so Bash refreshes command paths.

## Coding Style & Naming Conventions
Target Python 3.8+ with PEP 8 formatting: four-space indents, descriptive lowercase names, and snake_case functions. Keep helpers focused and prefer pure functions where practical. Add docstrings or concise comments only when behavior is non-obvious. Avoid introducing non-ASCII characters unless already present.

## Testing Guidelines
There is no automated suite yet; perform manual smoke checks of `list`, `extract`, and `browse` commands against sample JSONL files. When updating parsing logic, craft temporary JSONL snippets to exercise edge cases such as nested `response_item` payloads. Remove ad-hoc fixtures before committing.

## Commit & Pull Request Guidelines
Use Conventional Commit prefixes (`feat:`, `fix:`, `docs:`, etc.) and keep commits focused. Include motivation and sample CLI output in commit bodies or PR descriptions when behavior changes. PRs should describe the change, note any follow-up work, reference relevant issues, and confirm manual test coverage. Squash merge once CI-equivalent checks pass and reviewers approve.

## Security & Configuration Tips
Treat `~/.codex/sessions` as read-only user data—never modify or bundle real sessions in the repo. If you introduce example logs, redact sensitive content and store them in clearly labelled fixture directories. Confirm that generated artifacts, caches, or virtual environments stay out of source control.
