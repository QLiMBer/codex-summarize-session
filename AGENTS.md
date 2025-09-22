# Repository Guidelines

## Project Structure & Module Organization
- `codex_summarize_session/` holds the CLI implementation; `cli.py` defines the argument parsing, session listing, and extraction helpers.
- `pyproject.toml` configures packaging via `setuptools`; `README.md` documents user-facing usage.
- Session JSONL fixtures live outside the repo; the tool reads from `~/.codex/sessions` or a user-supplied directory at runtime.

## Build, Test, and Development Commands
- Install locally from the repo (no PyPI package yet):
  - Users: `python -m pip install .` or include the interactive extra with `python -m pip install .[browser]`.
  - Developers: `python -m pip install -e .[browser]` for editable work, or `pipx install --editable .` followed by `pipx inject codex-summarize-session prompt_toolkit`.
- Run the CLI without installing: `python -m codex_summarize_session.cli list` or add extra args (`extract`, `--sessions-dir`, etc.).
- No dedicated test suite yet; prefer manual smoke runs of `list`, `extract`, and `browse` after changes.
- After switching between pip/pipx installs, run `hash -r` so Bash refreshes cached command paths before re-testing.

## Coding Style & Naming Conventions
- Python 3.8+ code; follow PEP 8 with 4-space indentation and descriptive, lowercase variable names.
- Keep helper functions in `cli.py` focused and pure when possible; add docstrings or short comments only when logic is non-obvious.
- Avoid adding non-ASCII characters unless already required by existing files.

## Testing Guidelines
- Until automated tests are introduced, validate changes by running representative commands such as:
  - `codex-summarize-session list --limit 5`
  - `codex-summarize-session extract <session.jsonl> --stdout`
- When adding new parsing logic, create ad-hoc sample JSONL snippets to verify edge cases (e.g., nested `response_item` payloads).

## Commit & Pull Request Guidelines
- Use Conventional Commit prefixes (e.g., `feat:`, `fix:`, `docs:`) to summarize intent, as seen in the existing history.
- Keep commits focused; include context in the body if behavior changes or new flags are introduced.
- For PRs, describe the motivation, show sample CLI output for UX tweaks, and reference related issues when applicable. Ensure README or help text stays in sync with new functionality.

## Security & Configuration Tips
- The CLI should never modify files under `~/.codex/sessions`; treat session logs as read-only.
- Avoid bundling real session data in the repository. If examples are needed, redact sensitive fields and store them under clearly marked fixture directories.
