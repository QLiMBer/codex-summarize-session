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

## Artifact Locations
- Original session JSONL logs remain under `~/.codex/sessions` (current default exposed by `--sessions-dir`).
- Extracted message JSONL files default to the same `~/.codex/summaries/<relative-source>` directory as summaries (with filenames ending in `.messages.jsonl`) unless `--output-dir` is supplied; the CLI still honors explicit paths for users who prefer staging them elsewhere.
- Summaries will default to a new `~/.codex/summaries` tree, mirroring the relative structure of the source session to keep associations obvious. Users can override the location via CLI/TUI flags or config.

- `~/.codex` persists across `pip uninstall`/`pipx uninstall`; users must delete it manually if they want to remove stored sessions or summaries. Call this out in user guidance so accidental uninstalls do not drop data.

## Summary Storage
- Default layout: `~/.codex/summaries/<relative-source>/<variant>/summary.md`, where `<relative-source>` mirrors the session's path beneath `~/.codex/sessions` (hashed when the source lives elsewhere).
- Summary files are Markdown documents with YAML front matter capturing metadata (`source_path`, `model`, `prompt_path`, `reasoning`, token usage, cost estimate, timestamps). This keeps the summary human-readable while keeping metadata close by.
- Maintain an optional lightweight index (JSONL) in each directory listing available variants for quick lookup; avoid a global database until we need cross-session queries.

- CLI/TUI export command will support `--strip-metadata` to output only the Markdown body when users need the raw summary without YAML front matter.

## Prompt Strategy
- Maintain prompt templates as standalone files; the CLI accepts an explicit `--prompt-path` so naming the file doubles as a preset (e.g., `prompts/concise.md`).
- Support multiple prompt variants by name, selectable via CLI/TUI options; default to the standard summary prompt used in prior manual workflows.
- Capture any future prompt experiments or adjustments in this doc for version tracking.

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
1. Keep the OpenRouter analysis doc in sync as we discover retry recommendations or provider quirks.
2. Implement helpers that mirror session paths into the summary directory, hashing external sources gracefully, and surface the active summary root in CLI/TUI status outputs.
3. Design CLI flags/subcommands and TUI interactions (naming, confirmation flows).
4. Implement shared summary service module consumed by both CLI and browser entry points.
5. Prototype cached-summary awareness in the shared listing view (e.g., additional column or badge).
