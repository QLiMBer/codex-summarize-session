codex-summarize-session
=======================

Small CLI to help browse Codex CLI session logs and extract user/assistant messages from JSONL files for later summarization.

Current version: `0.2.0` (see `CHANGELOG.md` for details).

Features
--------
- List recent sessions under `~/.codex/sessions` (or a custom dir).
- Show each session's working directory (parsed from the log) directly in the list output.
- Extract only lines where `"type":"message"` into a new JSONL.
- Stream to stdout or write to a file.
- Default output path is the current working directory (not the script location).
- Accept either a full path or just the filename present under the sessions dir.
- Jump straight from `list` to `extract` by passing the numeric row shown in the listing.
- Optional interactive browser (`browse` subcommand) with arrow-key navigation.

Install
-------
1. Ensure Python 3.8+ is available.
2. Pick the installation style that fits your workflow:
   - **pipx (recommended for CLIs)**
     - `pipx install .`
     - Keeps each CLI in its own isolated virtual environment, exposes the command on your PATH, and makes uninstalling low-risk.
   - **pip (inside a venv or with `--user`)**
     - `python3 -m pip install --user .`
     - Installs into the active environment. Use `--user` or an activated virtualenv to avoid needing `sudo` and to prevent dependency conflicts.

3. Want the interactive browser? Install the optional extra that pulls in `prompt_toolkit`:
   - PyPI/package install: `python -m pip install codex-summarize-session[browser]`
   - From a local checkout: `python -m pip install .[browser]`
   - pipx users can inject the dependency after installing the CLI: `pipx inject codex-summarize-session prompt_toolkit`

Either option installs the `codex-summarize-session` executable to a bin directory on your PATH (commonly `~/.local/bin`).

Uninstall
---------
- pipx: `pipx uninstall codex-summarize-session`
- pip: `pip uninstall codex-summarize-session`

Iterate Without Reinstalling
----------------------------
- Run directly without install:
  - `python codex_summarize_session/cli.py list`
  - `python -m codex_summarize_session.cli extract <session.jsonl>`
- Editable/dev install (picks up code changes):
  - pipx: `pipx install --editable . --force` (use `--force` when you need to refresh an existing pipx venv)
  - pip in a venv: `python -m venv .venv && source .venv/bin/activate && pip install -e .`
- Ad-hoc run (no permanent install): `pipx run --spec . codex-summarize-session list`

Usage
-----
- List latest sessions (most recent first):

  - `codex-summarize-session list`
  - `codex-summarize-session list --limit 50`

- Browse interactively (requires the optional `[browser]` extra):

  - `codex-summarize-session browse`
  - `codex-summarize-session browse --limit 50`

- Extract by filepath:

  - `codex-summarize-session extract /home/user/.codex/sessions/2025/09/07/rollout-2025-09-07T23-41-39-...jsonl`

- Extract by filename (searched under the sessions dir):

  - `codex-summarize-session extract rollout-2025-09-07T23-41-39-...jsonl`

- Extract by list index (uses the same ordering as `list`):

  - `codex-summarize-session extract 3`

- Stream extracted lines to stdout:

  - `codex-summarize-session extract --stdout <session.jsonl>`

- Choose a specific output directory (filename is auto-chosen as `<input-basename>.messages.jsonl`):

  - `codex-summarize-session extract --output-dir ~/notes/summaries <session.jsonl>`

- Choose an exact output file path:

  - `codex-summarize-session extract --output ~/notes/summaries/my-session.messages.jsonl <session.jsonl>`

- Choose a different sessions dir:

  - `codex-summarize-session --sessions-dir ~/.codex/sessions extract <session.jsonl>`

Notes
-----
- Default output location is your current working directory at runtime, not the directory where the script is installed (e.g., not `~/.local/bin`).
- If you pass `--output-dir`, the file is written there using the default filename `<input-basename>.messages.jsonl`.
- If you pass `--output`, that exact file path is used.
- Use `--force` to overwrite an existing output file.
- Malformed JSON lines are skipped instead of aborting the extraction.
- A future `summarize` command can be added to call an LLM API or a local model.
- Extraction normalizes entries where messages are wrapped in `response_item` payloads and preserves timestamps when present.
- The `browse` command will prompt for a destination path (pre-filled with a sensible default). Press `Ctrl+C` to cancel.
- When `prompt_toolkit` is missing, the CLI suggests installing the optional `[browser]` extra before launching the interactive mode.

Development Notes
-----------------
- Test both dependency setups when iterating on the browser: run once with `prompt_toolkit` installed (`python -m pip install .[browser]` or `pipx inject codex-summarize-session prompt_toolkit`) and again after uninstalling it (`python -m pip uninstall prompt_toolkit`) to ensure the CLI’s guidance for missing extras stays accurate.
