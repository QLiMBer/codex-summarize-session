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
There is no PyPI package yet—install directly from this repository.

### Install from this repo
1. `git clone git@github.com:QLiMBer/codex-summarize-session.git`
2. `cd codex-summarize-session`
3. Pick your install style:
   - **pip (current environment)**
     - Standard CLI: `pip install .`
     - With interactive browser: `pip install .[browser]`
     - Editable: add `-e`, e.g. `pip install -e .[browser]`
   - **pipx (isolated venv)**
     - Standard CLI: `pipx install .`
     - With interactive browser: `pipx install .[browser]`
     - Editable: `pipx install --editable .[browser]` (use `--force` when refreshing an existing install)

Either approach drops the `codex-summarize-session` entrypoint on your PATH (often `~/.local/bin` or the active virtualenv).

Uninstall
---------
- pipx: `pipx uninstall codex-summarize-session`
- pip: `pip uninstall codex-summarize-session`
  - prompt_toolkit: it is not automatically uninstalled
  - you can manually uninstall it using `pip uninstall prompt_toolkit`

Iterate Without Reinstalling
----------------------------
- Editable installation
  - `pip install -e .[browser]`
  - `pipx install --editable .[browser]`
- Run directly without install:
  - `python codex_summarize_session/cli.py list`
  - `python -m codex_summarize_session.cli extract <session.jsonl>`
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
- If you keep both a pip and pipx install, whichever `codex-summarize-session` appears first on `PATH` wins. Run `which codex-summarize-session` to confirm, or uninstall one copy before testing changes.
- After changing installs, run `hash -r` (or open a new shell) so Bash forgets cached command locations; otherwise it might still call a removed shim.
