codex-summarize-session
=======================

Small CLI to help browse Codex CLI session logs and extract user/assistant messages from JSONL files for later summarization.

Features
--------
- List recent sessions under `~/.codex/sessions` (or a custom dir).
- Extract only lines where `"type":"message"` into a new JSONL.
- Stream to stdout or write to a file.
- Default output path is the current working directory (not the script location).
- Accept either a full path or just the filename present under the sessions dir.

What Is a CLI?
--------------
- Command-Line Interface: Programs run from a terminal with commands, args, and flags (e.g., `codex-summarize-session extract file.jsonl`).
- Behavior: Parses args, does work, prints output, and returns an exit code (0 = success).
- Entry point: Packaging maps a command name to a Python function; installers create a small launcher script that calls that function.

pipx vs pip
------------
- pipx: Installs each app into its own virtual environment and exposes a single command on your PATH. Great for CLIs; avoids dependency conflicts; easy uninstall.
- pip: Installs into the current environment (system Python, `--user`, or a virtualenv you activated). Prefer a virtualenv or `--user`; avoid system-wide with `sudo`.

Install
-------
1. Ensure Python 3.8+ is available.
2. Systemwide-style (recommended for CLIs) using pipx:
   - `pipx install .`
3. User-local with pip (no separate venv):
   - `python3 -m pip install --user .`

This installs the executable `codex-summarize-session` into a bin directory on your PATH (commonly `~/.local/bin`).

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
  - pipx: `pipx install --editable .`
  - pip in a venv: `python -m venv .venv && source .venv/bin/activate && pip install -e .`
- Ad-hoc run (no permanent install): `pipx run --spec . codex-summarize-session list`

Usage
-----
- List latest sessions (most recent first):

  - `codex-summarize-session list`
  - `codex-summarize-session list --limit 50`

- Extract message lines to a file in the current directory (default):

  - `codex-summarize-session extract /home/mirek/.codex/sessions/2025/09/07/rollout-2025-09-07T23-41-39-...jsonl`

- Extract by filename (searched under the sessions dir):

  - `codex-summarize-session extract rollout-2025-09-07T23-41-39-...jsonl`

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
