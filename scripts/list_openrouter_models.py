#!/usr/bin/env python3
"""
List available models on OpenRouter, optionally filtering for free/low-cost options.

Usage:
    python scripts/list_openrouter_models.py [--free] [--paid] [--limit N]

Examples:
    # Show all free models (zero-cost)
    python scripts/list_openrouter_models.py --free

    # Show all models (both free and paid)
    python scripts/list_openrouter_models.py

    # Show first 5 free models
    python scripts/list_openrouter_models.py --free --limit 5
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import httpx
except ImportError:
    print("ERROR: httpx is required. Install with: pip install httpx")
    sys.exit(1)


def load_api_key() -> str:
    """Load OpenRouter API key from env var or config file."""
    import os

    # Try environment variable first
    env_key = os.getenv("OPENROUTER_API_KEY")
    if env_key and env_key.strip():
        return env_key.strip()

    # Try config file
    config_path = Path("~/.config/openrouter/key").expanduser()
    if config_path.exists():
        try:
            return config_path.read_text(encoding="utf-8").strip()
        except OSError:
            pass

    raise RuntimeError(
        "OpenRouter API key not found.\n"
        "  Set OPENROUTER_API_KEY environment variable, or\n"
        "  Place your key in ~/.config/openrouter/key"
    )


def fetch_models(api_key: str) -> list[dict]:
    """Fetch all models from OpenRouter API."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "codex-summarize-session/list-models",
    }

    resp = httpx.get(
        "https://openrouter.ai/api/v1/models", headers=headers, timeout=15.0
    )
    resp.raise_for_status()
    return resp.json().get("data", [])


def format_model(model: dict) -> str:
    """Format a single model entry for display."""
    model_id = model.get("id", "unknown")
    name = model.get("name", "")
    pricing = model.get("pricing", {})
    prompt_cost = float(pricing.get("prompt", 0))
    completion_cost = float(pricing.get("completion", 0))
    context = model.get("context_length")

    # Cost indicator
    if prompt_cost == 0 and completion_cost == 0:
        cost_str = "FREE"
    else:
        cost_str = f"${prompt_cost:.2e}/${completion_cost:.2e}"

    # Context window
    context_str = f"{context:,} tokens" if context else "unknown"

    return f"{model_id:<50} | {cost_str:<15} | {context_str:<15} | {name}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="List models available on OpenRouter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--free",
        action="store_true",
        help="Show only free models (zero prompt/completion cost)",
    )
    parser.add_argument(
        "--paid",
        action="store_true",
        help="Show only models with non-zero pricing",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of results (default: show all)",
    )
    args = parser.parse_args()

    try:
        print("Fetching OpenRouter models...", file=sys.stderr)
        api_key = load_api_key()
        models = fetch_models(api_key)

        # Filter
        filtered = []
        for model in models:
            pricing = model.get("pricing", {})
            prompt_cost = float(pricing.get("prompt", 0))
            completion_cost = float(pricing.get("completion", 0))
            is_free = prompt_cost == 0 and completion_cost == 0

            if args.free and not is_free:
                continue
            if args.paid and is_free:
                continue

            filtered.append(model)

        if not filtered:
            print("No models found matching criteria.", file=sys.stderr)
            sys.exit(1)

        # Limit
        if args.limit:
            filtered = filtered[: args.limit]

        # Print header
        print(
            f"{'Model ID':<50} | {'Cost':<15} | {'Context':<15} | Name",
            file=sys.stderr,
        )
        print(
            "-" * 50 + "+" + "-" * 17 + "+" + "-" * 17 + "+" + "-" * 50,
            file=sys.stderr,
        )

        # Print models
        for model in filtered:
            print(format_model(model))

        print(f"\nTotal: {len(filtered)} model(s)", file=sys.stderr)

    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
