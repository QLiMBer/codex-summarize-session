# Session Summaries Feature

## Goals
- Allow users to request AI-generated summaries of one or more extracted Codex sessions from both the CLI and TUI.
- Share summary generation logic so both CLI commands and the TUI browser call the same summary service.
- Default to OpenRouter’s Grok 4 Fast free tier (`x-ai/grok-4-fast:free`) while letting users pick any available model.
- Cache summaries and surface metadata so repeat runs avoid duplicate API spend.

## Feature Outline
- Introduce a CLI entry point for summarizing selected session JSONL files (single or batched).
- Extend the TUI browser to invoke the shared summary command for a highlighted session.
- Store generated summaries to avoid repeat API costs and enable quick retrieval on subsequent runs.

## TUI Integration Requirements
- Display a header row in the browse table so the meaning of each column (age, duration, byte size, cwd, summaries) stays obvious even after we streamline labels within rows.
- Remove inline `B` and `cwd:` prefixes inside data rows and rely on the header for clarity, improving horizontal space for the session title.
- Surface a new `Summaries` column that reflects how many cached variants exist for each session, using the shared storage resolver to guarantee counts stay accurate after generation.
- Expand the detail pane to include expected summary paths, cache freshness, and the most recent cost estimate so users understand why a cache hit or miss happened.
- Provide summary actions directly in the TUI via keybindings: `s` to view a cached summary, `g` to generate or view if one already exists, and `G` to force a regeneration.
- Initialize `SummaryService` and the `OpenRouterClient` lazily inside the TUI so missing API keys raise a friendly message instead of aborting startup.
- Render summaries with `pydoc.pager` (or equivalent non-nested terminal pager) to avoid re-entering the running asyncio event loop while still presenting Markdown cleanly.
- Guard all summary commands with clear error states for missing keys, network failures, or background exceptions, leaving the application responsive.

## Configuration & Flags
- Extend `python -m codex_summarize_session.cli browse` with summary-centric flags (`--summaries-dir`, `--summary-prompt`, `--summary-model`, `--summary-max-tokens`, `--summary-temperature`, `--summary-reasoning-effort`) mirroring the CLI `summaries generate` options.
- Ensure defaults align with the CLI command so users can switch between modes without re-specifying configuration.
- Validate flag combinations on demand when the summary workflow is first invoked, keeping startup fast and avoiding errors before a user requests a summary.

## Artifact Locations
- Original session JSONL logs remain under `~/.codex/sessions` (current default exposed by `--sessions-dir`).
- Extracted message JSONL files default to the same `~/.codex/summaries/<relative-source>` directory as summaries (with filenames ending in `.messages.jsonl`) unless `--output-dir` is supplied; the CLI still honors explicit paths for users who prefer staging them elsewhere.
- Summaries will default to a new `~/.codex/summaries` tree, mirroring the relative structure of the source session to keep associations obvious. Users can override the location via CLI/TUI flags or config.

- `~/.codex` persists across `pip uninstall`/`pipx uninstall`; users must delete it manually if they want to remove stored sessions or summaries. Call this out in user guidance so accidental uninstalls do not drop data.

## Summary Storage
- Default layout: `~/.codex/summaries/<relative-source>/<variant>/summary.md`, where `<relative-source>` mirrors the session's path beneath `~/.codex/sessions` (hashed when the source lives elsewhere).
- A sibling `summary.messages.jsonl` (no prompt/variant suffix) stores the cleaned message-only transcript used to generate the summary.
- Model choices are tracked in the summary metadata instead of dedicated subdirectories so cache paths stay stable across re-runs.
- Summary files are Markdown documents with YAML front matter capturing metadata (`source_path`, `model`, `prompt_path`, `reasoning`, token usage, cost estimate, timestamps, message count). This keeps the summary human-readable while keeping metadata close by.
- Maintain an optional lightweight index (JSONL) in each directory listing available variants for quick lookup; avoid a global database until we need cross-session queries.
- External session sources (outside the configured sessions root) are stored under `external/<hash>-<slug>` so we avoid leaking full filesystem paths while keeping the cache human-readable.
- Model metadata fetched from OpenRouter is cached in-memory with an optional JSON file on disk so repeated runs estimate cost without re-hitting the API.
- Default prompts can reference placeholders like `{{session_path}}`, `{{summary_path}}`, `{{messages_path}}`, and `{{prompt_variant}}`; the service raises a clear error when templates omit required placeholders.

- CLI/TUI export command will support `--strip-metadata` to output only the Markdown body when users need the raw summary without YAML front matter.

## Prompt Strategy
- Maintain prompt templates as standalone files; the CLI accepts an explicit `--prompt-path` so naming the file doubles as a preset (e.g., `prompts/concise.md`).
- Support multiple prompt variants by name, selectable via CLI/TUI options; default to the standard summary prompt used in prior manual workflows.
- Capture any future prompt experiments or adjustments in this doc for version tracking.
- Ship a `prompts/default.md` template that references `{{session_path}}`, `{{summary_path}}`, and `{{prompt_variant}}` so placeholder validation succeeds out of the box.

## OpenRouter Integration (Analysis Pending)
- Before implementation, perform a focused review of OpenRouter API capabilities, authentication flow, rate limits, and error handling requirements.
- Document findings and integration decisions here (auth storage, timeout behavior, retries, logging), referencing `docs/openrouter-analysis.md` as the source of truth.
- Confirm whether batching multiple sessions into one request is supported or if we must call the API per session.

## Reasoning Tokens
- Default behavior: request `reasoning.effort = "medium"` for models that support it (Grok, OpenAI reasoning, Anthropic). When the target model lacks that knob we omit the field gracefully.
- Reasoning tokens are counted as output tokens; store the reported usage alongside summaries so users understand cost and cache hits.
- Preserve `reasoning`/`reasoning_details` blocks if we later feed the thinking steps into chain-of-thought aware workflows.

## Cost & Rate Limits
- Every completion records prompt/completion token counts and computes an estimated cost using the model's pricing from `GET /api/v1/models`; surface this in CLI/TUI output and embed it in the summary metadata.
- Implement automatic retries with capped exponential backoff for HTTP 429/5xx responses while notifying the user about pauses; provide a fallback message if limits persist.
- When caching summaries, include the cost information so users can gauge savings from cache hits.

## Next Steps
1. Revisit Phase 5 with the refined TUI requirements above, ensuring we validate UI refresh behavior after summary generation before moving on.
2. Capture usability notes during implementation (status messaging, pager ergonomics) and roll them into README/help text updates once the feature stabilizes.
3. Once Phase 5 lands, resume Phase 6 indexing work to expose variant listings in both CLI and TUI.
4. Keep the OpenRouter analysis doc updated with any retry/backoff adjustments discovered while wiring the TUI workflows.

## Implementation Plan

### Phase 0 — Groundwork and Safeguards
- [x] Capture environment configuration expectations in `README.md` (API key discovery, `OPENROUTER_API_KEY` precedence) so developers know how to unlock the feature before code lands.
- [x] Add a lightweight integration checklist to `RELEASE_PLAN.md` so we remember to regenerate documentation and smoke test commands before tagging.
- [x] Create skeleton modules (`codex_summarize_session/summaries/__init__.py`, `storage.py`, `openrouter_client.py`, `service.py`) to keep future diffs focused and make imports predictable for both CLI and TUI.
- [x] Define shared type aliases/dataclasses (e.g., `SummaryRequest`, `SummaryRecord`) so subsequent phases manipulate structured data instead of raw dictionaries.

### Phase 1 — Storage & Prompt Scaffolding
- [x] Implement `SummaryPathResolver` in `storage.py` to derive cache paths given a session file, prompt variant, and model; include hashing fallback for out-of-tree sources.
- [x] Add helpers to read/write summary markdown with YAML front matter, including round-tripping metadata without clobbering user edits.
- [x] Introduce a prompt loader that resolves named presets under `prompts/` and allows raw file paths; include basic validation to warn on missing substitution variables.
- [x] Update `docs/session-summaries.md` with any storage edge cases discovered while coding to keep design and implementation aligned.

### Phase 2 — OpenRouter Client
- [x] Build a thin client around the OpenRouter `/chat/completions` endpoint that accepts our structured request object, injects optional referer/title headers, and exposes retry/backoff controls from a central place.
- [x] Surface explicit error types (auth, rate-limit, transient) so CLI/TUI layers can give actionable feedback and retry guidance.
- [x] Cache model metadata and pricing locally (in-memory with optional JSON sidecar) to support cost estimation without re-fetching on every summary invocation.

### Phase 3 — Summary Service
- [x] Implement `generate_summary()` in `service.py` that orchestrates prompt selection, cache lookup, OpenRouter calls, YAML front matter population, and cost tracking.
- [x] Add a `get_cached_summary()` helper returning cache hit metadata so callers can short-circuit expensive work when `--use-cache` is enabled (default on).
- [x] Include opt-in `--refresh` logic to bypass cache while still recording previous cost information for transparency.
- [x] Emit structured logs (or debug prints gated by `--verbose`) describing whether a cache hit occurred, which model was used, and total estimated cost.

### Phase 4 - CLI Integration
- [x] Extend `cli.py` with a `summaries` command group that initially ships a `generate` subcommand accepting session paths, prompt variant, model, `--refresh`, `--stdout`, and `--strip-metadata` flags.
- [x] Reuse existing session discovery helpers so `generate` can accept glob patterns and `--sessions-dir` overrides.
- [x] Ensure CLI exit codes distinguish between user errors (invalid prompt path) and provider failures (non-zero to inform shell scripts).
- [x] Update `--help` text and README usage examples, highlighting how cache hits reduce cost, where summaries are stored, and that `summary.messages.jsonl` is generated automatically.

### Phase 5 — TUI Integration
- [ ] Update the session list to include a header row, drop inline `B`/`cwd:` labels, and insert a `Summaries` column that reflects cached variant counts via `SummaryPathResolver`.
- [ ] Populate the detail pane with summary metadata (expected paths, cache timestamp, last run cost) while falling back to hints when no summary exists yet.
- [ ] Wire keybindings (`s`, `g`, `G`) that lazily initialize `SummaryService`/`OpenRouterClient`, invoke generation, and refresh table/detail state after cache mutations.
- [ ] Execute long-running summary generation in background tasks with progress/status messaging so the UI remains responsive and emits success/failure outcomes instead of the misleading "cancelled" message seen in the reverted attempt.
- [ ] Display cached summaries through `pydoc.pager` (or equivalent) to avoid nested event loops while still presenting Markdown cleanly.
- [ ] Surface clear, inline errors for missing API keys, network failures, or OpenRouter issues without crashing the TUI.

### Phase 6 — Indexing & Metadata Surfacing
- [ ] Generate/update per-session index JSONL files after each summary write; expose small helper to list available variants for CLI listing and TUI badges.
- [ ] Add CLI/TUI surface area to show cached variants (e.g., `summaries list <session>`), ensuring the underlying index logic is reused instead of re-scanning the filesystem.
- [ ] Provide cost savings statistics when a cache hit occurs, pulling historical data from the index for user feedback.

### Phase 7 — Verification & Polish
- [ ] Create sample JSONL fixtures (redacted) under `fixtures/` for manual testing without touching real sessions; document usage in README.
- [ ] Perform manual smoke tests: `python -m codex_summarize_session.cli summaries generate ~/.codex/sessions/example.jsonl --limit 1`, `... --refresh`, and TUI interaction.
- [ ] Confirm summaries respect `--output-dir` overrides and that Markdown output renders correctly when piping to `less` or redirecting to files.
- [ ] Update CHANGELOG/ROADMAP entries, highlight new commands, and call out caching behavior before opening the PR.
