#!/usr/bin/env python3
"""
Diagnose summary generation failures by invoking the summaries service and
printing full exception tracebacks.

Usage:
  python scripts/diagnose_summary.py /path/to/session.jsonl [--model MODEL]

The script reads the OpenRouter API key from `OPENROUTER_API_KEY` or
`~/.config/openrouter/key` (same as the CLI). It will attempt to generate a
summary for the provided session and print any errors including full tracebacks
to help debugging whether the failure is the provider (model) or input format.
"""
from __future__ import annotations

import argparse
import traceback
from pathlib import Path
import sys

from codex_summarize_session.cli import build_openrouter_client
from codex_summarize_session.summaries.service import SummaryService
from codex_summarize_session.summaries.types import SummaryRequest


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose summarization failures")
    parser.add_argument("session", help="Path to the session JSONL file")
    parser.add_argument("--model", help="OpenRouter model id to test", default=None)
    parser.add_argument("--max-tokens", type=int, help="Optional cap for completion tokens to request from the provider", default=None)
    parser.add_argument("--summaries-dir", help="Local summaries cache root", default="~/.codex/summaries")
    args = parser.parse_args()

    session_path = Path(args.session).expanduser()
    if not session_path.is_file():
        print(f"ERROR: session file not found: {session_path}")
        return 2

    try:
        summaries_root = Path(args.summaries_dir).expanduser()
        client = build_openrouter_client(summary_root=summaries_root)
    except Exception as exc:
        print("ERROR: failed to construct OpenRouter client:")
        traceback.print_exc()
        return 3

    service = SummaryService(summary_root=Path(args.summaries_dir), openrouter_client=client)

    request = SummaryRequest(session_path=session_path, prompt_variant="default", model=args.model or "meta-llama/llama-3.3-70b-instruct:free")

    print("Attempting to generate summary (this will contact OpenRouter)...")
    try:
        record = service.generate(request, use_cache=False, refresh=True, max_tokens=args.max_tokens)
    except Exception as exc:
        print("Summary generation failed with exception:")
        traceback.print_exc()
        # If the client returned a structured response (rare here), try to show it
        return 1
    else:
        print("Summary generated successfully:")
        print(record.cache_path)
        print("--- Summary preview ---")
        print(record.body[:1000])
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
