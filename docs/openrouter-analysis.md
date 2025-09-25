# OpenRouter Integration Notes

## TL;DR
- Grok 4 Fast free tier is available today as `x-ai/grok-4-fast:free` (2M-token context, $0 pricing); confirm availability before each release.
- OpenRouter exposes a single OpenAI-compatible endpoint at `https://openrouter.ai/api/v1` covering chat/text completions plus supporting endpoints for models, usage, and key management.
- Authenticate with `Authorization: Bearer <key>` and prefer adding `HTTP-Referer`/`X-Title` headers so requests are attributed to this CLI.
- Request payloads mirror OpenAI’s schema, so we can reuse existing client patterns (messages array, temperature, streaming).
- Use `GET /api/v1/models` and `GET /api/v1/key` to surface model metadata, pricing, and remaining credits inside the UX.
- Advanced routing features (ordered `models` fallbacks, provider allow/deny lists, message `transforms`) give us levers to trade cost vs. reliability once summaries ship.

## Core Endpoints
- `POST /v1/chat/completions`: primary chat interface (messages array with role/content). Supports streaming via `"stream": true` and returns standard `choices` + `usage` payloads.
- `POST /v1/completions`: legacy text-completion form (not immediately needed, but shares parameter surface with chat).
- `GET /api/v1/models` (cached at edge) or `GET /v1/models`: enumerate available models, pricing, context length, and supported parameters.
- `GET /api/v1/key`: retrieve credit usage, hard limits, and free-tier status for the current API key.
- API key provisioning endpoints (`/api/v1/keys`, `POST/DELETE/PATCH`) exist but are likely overkill for this CLI; we only need a user-managed key.

## Authentication & Headers
- Required: `Authorization: Bearer <OPENROUTER_API_KEY>`, `Content-Type: application/json`.
- Recommended: `HTTP-Referer: <app-url-or-repo>` and `X-Title: <display name>` to register the CLI with OpenRouter’s ranking/analytics (per docs/api-reference/overview).
- Store the key out of the repo (env var or config file). For the CLI, read from `OPENROUTER_API_KEY` or a user config file under `~/.codex/`.

## Request Payload Highlights
- Shared fields with OpenAI SDK: `model`, `messages`, `temperature`, `top_p`, `max_tokens`, `presence_penalty`, `frequency_penalty`, `logit_bias`, `stop`, etc.
- Provider routing block (optional):
  ```json
  {
    "provider": {
      "only": ["azure"],
      "exclude": ["hyperbolic"],
      "order": ["openai", "azure"]
    }
  }
  ```
- Ordered fallback models via `models: ["anthropic/claude-3.5-sonnet", "gryphe/mythomax-l2-13b"]` ensure continuity when a primary model is throttled or offline.
- Message transforms (e.g., `transforms: ["middle-out"]`) truncate long prompts to fit model context limits—handy for huge session transcripts.

## Response Schema & Telemetry
- Matches OpenAI’s `chat.completion` format: each choice includes `message.role`, `message.content`, and `finish_reason`.
- Reasoning-capable models return `reasoning` or `reasoning_details` arrays alongside content; retain them when chaining requests or tool outputs.
- `usage` object reports `prompt_tokens`, `completion_tokens`, and `total_tokens`; some providers also surface `reasoning_tokens`.
- When streaming, responses arrive as SSE events with incremental `delta` payloads—compatible with existing OpenAI stream parsers.


## Reasoning Tokens
- Enable or tune reasoning via the `reasoning` object (supports `enabled`, `effort`, `max_tokens`, `exclude`). Grok models accept `effort` levels (`low`/`medium`/`high`), while Anthropic and other providers map the same payload to their native knobs.
- Reasoning tokens count as output tokens; budget accordingly and expose usage to the user if possible.
- When reasoning is returned, it appears in `message.reasoning` or `reasoning_details`; preserve blocks if you plan to feed them back into follow-up calls or tool interactions.

## Rate Limits & Billing
- `GET /api/v1/key` → `{ label, usage, limit, is_free_tier }`. We can expose this in diagnostics to help users understand credit status.
- Rate-limit headers follow HTTP 429 semantics; retry with exponential backoff. If the key is on the free tier, expect tighter quotas.
- Pricing per model is available in the models list (prompt/completion cost). We should log total token usage per summary and surface it to the user when possible.

## Model Selection Guidance
- Grok 4 Fast (free tier) is exposed as `x-ai/grok-4-fast:free` with a 2M-token context window and zero-cost prompt/completion tokens today; reasoning can be enabled via the unified `reasoning` payload.
- Model IDs are namespaced, e.g., `x-ai/grok-2`, `openai/gpt-4o`, `google/gemini-2.5-pro-preview`.
- Each `Model` record indicates supported parameters, context window, moderation status, and provider metadata—useful for validation (e.g., reject `max_tokens` when a model forbids it).
- Track pricing/availability for `x-ai/grok-4-fast:free`; if the free tier ends, fall back to the paid Grok variant or another summarization-friendly model.

## Security & Storage Considerations
- Never log the API key; scrub it from debug output. Offer a helper command to verify key validity without exposing it (`codex-summarize-session summaries auth-check`).
- Consider storing user configuration (model default, prompt variant, referer/title values) in `~/.codex/config.toml` or similar.
- Handle HTTP 401/403 with clear remediation steps (check env var, referer header, or account status).

## Integration TODOs
1. Monitor availability of `x-ai/grok-4-fast:free` via `GET /api/v1/models` and keep fallbacks ready in case the free tier is withdrawn.
2. Decide on default `HTTP-Referer` (project README URL?) and let users override via CLI flag/env.
3. Build a small OpenRouter client wrapper that hides header assembly, retries 429/500 with jitter, and surfaces usage metrics from the response.
4. Document manual setup: obtaining an API key, setting env var, running a `summaries test` command to validate connectivity.
5. Evaluate streaming vs. non-streaming flows for the CLI (streaming improves perceived latency but complicates output capture for cached summaries).
6. Capture OpenRouter API doc snapshot references in `docs/session-summaries.md` once we finalize the integration approach.

## Open Questions
- Does OpenRouter expose batch endpoints for summarizing multiple transcripts in one call, or should we send requests serially? (Docs focus on single chat calls.)
- What retry policy does OpenRouter recommend for 429/5xx responses? (Need to check broader docs or community guidance.)
- Any provider-specific quirks we should guard against (e.g., models requiring system prompts, moderation callbacks)?
- Should we allow users to opt into OpenRouter’s automatic routing (`models` array) or keep it simple with a single explicit model?
