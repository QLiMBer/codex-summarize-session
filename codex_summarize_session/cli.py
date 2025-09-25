from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence
from dataclasses import dataclass

from .messages import iter_jsonl, iter_messages, write_messages_jsonl
from .summaries import (
    AuthenticationError,
    ClientConfigurationError,
    OpenRouterClient,
    OpenRouterError,
    RateLimitError,
    PromptValidationError,
    SummaryRequest,
    SummaryService,
    TransientError,
)
from .summaries.storage import SummaryPathResolver


def get_default_sessions_dir() -> Path:
    return Path("~/.codex/sessions").expanduser()


def get_default_summaries_dir() -> Path:
    return Path("~/.codex/summaries").expanduser()


def get_openrouter_config_path() -> Path:
    return Path("~/.config/openrouter/key").expanduser()


def load_openrouter_api_key() -> Optional[str]:
    env_key = os.getenv("OPENROUTER_API_KEY")
    if env_key and env_key.strip():
        return env_key.strip()

    config_path = get_openrouter_config_path()
    try:
        contents = config_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return contents or None


def build_openrouter_client(summary_root: Path) -> OpenRouterClient:
    api_key = load_openrouter_api_key()
    if not api_key:
        raise AuthenticationError(
            "OpenRouter API key not found. Set OPENROUTER_API_KEY or place a key in ~/.config/openrouter/key."
        )

    base_url = os.getenv("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1")
    referer = os.getenv("OPENROUTER_REFERER", "https://github.com/QLiMBer/codex-summarize-session") or None
    title = os.getenv("OPENROUTER_TITLE", "codex-summarize-session") or None
    cache_path = (summary_root / "_model_catalog.json")
    return OpenRouterClient(
        api_key=api_key,
        base_url=base_url,
        referer=referer,
        title=title,
        model_cache_path=cache_path,
    )


def normalize_reasoning_effort(value: Optional[str]) -> Optional[str]:
    if value is None:
        return "medium"
    if value.lower() == "none":
        return None
    return value


def create_summary_service(sessions_dir: Path, summaries_dir: Path) -> tuple[SummaryService, OpenRouterClient]:
    summaries_dir = summaries_dir.expanduser()
    sessions_dir = sessions_dir.expanduser()
    client = build_openrouter_client(summaries_dir)
    service = SummaryService(
        summary_root=summaries_dir,
        sessions_root=sessions_dir,
        openrouter_client=client,
    )
    return service, client


def render_cost(cost_data: Any) -> Optional[str]:
    if isinstance(cost_data, dict):
        total = cost_data.get("total")
        if isinstance(total, (int, float)):
            return f"${total:.6f}"
    return None


def handle_summaries_generate(args: argparse.Namespace, parser: argparse.ArgumentParser, sessions_dir: Path) -> int:
    summaries_dir = (args.summaries_dir or get_default_summaries_dir()).expanduser()

    if args.stdout and len(args.sessions) != 1:
        parser.error("--stdout requires exactly one session input.")
    if args.strip_metadata and not args.stdout:
        parser.error("--strip-metadata currently requires --stdout.")

    resolved_sessions: list[Path] = []
    for candidate in args.sessions:
        try:
            resolved_sessions.append(resolve_session_path(candidate, sessions_dir))
        except FileNotFoundError as exc:
            parser.error(str(exc))

    client: Optional[OpenRouterClient] = None
    try:
        service, client = create_summary_service(sessions_dir, summaries_dir)
    except AuthenticationError as exc:
        parser.error(str(exc))
        return 2
    except OpenRouterError as exc:
        parser.error(f"Failed to initialise OpenRouter client: {exc}")
        return 2

    exit_code = 0
    try:
        for session_path in resolved_sessions:
            prompt_variant = args.prompt or "default"
            request = SummaryRequest(
                session_path=session_path,
                prompt_variant=prompt_variant,
                model=args.model,
                reasoning_effort=normalize_reasoning_effort(args.reasoning_effort),
                refresh=args.refresh,
                strip_metadata=args.strip_metadata,
            )
            try:
                record = service.generate(
                    request,
                    use_cache=not args.no_cache,
                    refresh=args.refresh,
                    temperature=args.temperature,
                    max_tokens=args.max_tokens,
                )
            except PromptValidationError as exc:
                parser.error(str(exc))
                return 2
            except FileNotFoundError as exc:
                parser.error(str(exc))
                return 2
            except (AuthenticationError, RateLimitError, TransientError, ClientConfigurationError, OpenRouterError) as exc:
                parser.error(str(exc))
                return 2

            if args.stdout:
                if args.strip_metadata:
                    output_text = record.body
                else:
                    output_text = record.cache_path.read_text(encoding="utf-8")
                sys.stdout.write(output_text)
                if not output_text.endswith("\n"):
                    sys.stdout.write("\n")
                continue

            status = "cached" if record.cached else "generated"
            cost_text = (
                render_cost(record.metadata.get("cost_estimate_usd"))
                if isinstance(record.metadata, dict)
                else None
            )
            message = f"[{status}] {session_path} -> {record.cache_path}"
            if cost_text:
                message += f" (cost {cost_text})"
            print(message)

        return exit_code
    finally:
        if client:
            client.close()
def extract_cwd_from_text(text: str) -> Optional[str]:
    start_tag = "<cwd>"
    end_tag = "</cwd>"
    start = text.find(start_tag)
    if start == -1:
        return None
    start += len(start_tag)
    end = text.find(end_tag, start)
    if end == -1:
        return None
    return text[start:end].strip()


def extract_cwd_from_obj(obj: Any) -> Optional[str]:
    stack = [obj]
    while stack:
        current = stack.pop()
        if isinstance(current, str):
            cwd = extract_cwd_from_text(current)
            if cwd:
                return cwd
        elif isinstance(current, dict):
            text = current.get("text")
            if isinstance(text, str):
                cwd = extract_cwd_from_text(text)
                if cwd:
                    return cwd
            for key, value in current.items():
                if key == "text":
                    continue
                stack.append(value)
        elif isinstance(current, (list, tuple)):
            stack.extend(current)
    return None


def extract_cwd_from_session(path: Path, max_lines: int = 200) -> Optional[str]:
    for index, obj in enumerate(iter_jsonl(path)):
        cwd = extract_cwd_from_obj(obj)
        if cwd:
            return cwd
        if index + 1 >= max_lines:
            break
    return None
def list_sessions(sessions_dir: Path, limit: Optional[int] = None) -> list[Path]:
    files = sorted(
        (p for p in sessions_dir.rglob("*.jsonl") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return files[:limit] if limit else files


@dataclass
class SessionEntry:
    index: int
    path: Path
    display_path: str
    size_bytes: int
    cwd: Optional[str]

    @property
    def size_display(self) -> str:
        return f"{self.size_bytes:,}".replace(",", " ")

    @property
    def cwd_display(self) -> str:
        return self.cwd if self.cwd else "?"


@dataclass
class BrowseSummaryOptions:
    summaries_dir: Path
    prompt_variant: str
    model: str
    temperature: float
    max_tokens: Optional[int]
    reasoning_effort: Optional[str]


def build_session_entries(
    paths: Sequence[Path], sessions_dir: Path
) -> list[SessionEntry]:
    entries: list[SessionEntry] = []
    for index, path in enumerate(paths, start=1):
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        try:
            display_path = path.relative_to(sessions_dir).as_posix()
        except ValueError:
            display_path = str(path)
        cwd = extract_cwd_from_session(path)
        entries.append(
            SessionEntry(
                index=index,
                path=path,
                display_path=display_path,
                size_bytes=size,
                cwd=cwd,
            )
        )
    return entries


def format_session_table(
    entries: Sequence[SessionEntry],
    summary_counts: Optional[Mapping[Path, int]] = None,
) -> tuple[str, list[str]]:
    if not entries:
        header = "Idx  Path  Bytes  CWD  Summaries"
        return header, []

    index_width = max(len("Idx"), max(len(str(entry.index)) for entry in entries))
    path_width = max(len("Path"), max(len(entry.display_path) for entry in entries))
    bytes_width = max(len("Bytes"), max(len(entry.size_display) for entry in entries))
    cwd_width = max(len("CWD"), max(len(entry.cwd_display) for entry in entries))

    summary_labels: list[str] = []
    for entry in entries:
        if summary_counts is None:
            summary_labels.append("?")
        else:
            count = summary_counts.get(entry.path, 0)
            summary_labels.append(str(count))
    summaries_width = max(len("Summaries"), max(len(label) for label in summary_labels) if summary_labels else len("Summaries"))

    header = (
        f"{'Idx'.rjust(index_width)}  "
        f"{'Path'.ljust(path_width)}  "
        f"{'Bytes'.rjust(bytes_width)}  "
        f"{'CWD'.ljust(cwd_width)}  "
        f"{'Summaries'.rjust(summaries_width)}"
    )

    lines: list[str] = []
    for entry, summary_label in zip(entries, summary_labels):
        line = (
            f"{str(entry.index).rjust(index_width)}  "
            f"{entry.display_path.ljust(path_width)}  "
            f"{entry.size_display.rjust(bytes_width)}  "
            f"{entry.cwd_display.ljust(cwd_width)}  "
            f"{summary_label.rjust(summaries_width)}"
        )
        lines.append(line)
    return header, lines


def build_summary_counts(
    entries: Sequence[SessionEntry],
    summaries_dir: Path,
    sessions_dir: Path,
) -> dict[Path, int]:
    resolver = SummaryPathResolver(summaries_dir.expanduser(), sessions_dir.expanduser())
    counts: dict[Path, int] = {}
    for entry in entries:
        variants = resolver.cached_variants_for(entry.path)
        counts[entry.path] = len(variants)
    return counts


def resolve_session_path(candidate: str, sessions_dir: Path) -> Path:
    stripped = candidate.strip()
    if stripped.isdigit():
        files = list_sessions(sessions_dir)
        if not files:
            raise FileNotFoundError(f"No session files found under {sessions_dir}")
        index = int(stripped)
        if not 1 <= index <= len(files):
            raise FileNotFoundError(
                f"Session index {index} out of range (1..{len(files)})."
            )
        return files[index - 1]

    p = Path(candidate).expanduser()
    if p.exists():
        return p
    # Try to find by basename within sessions_dir
    matches = [f for f in sessions_dir.rglob("*.jsonl") if f.name == candidate]
    if not matches:
        raise FileNotFoundError(
            f"Session not found: {candidate}. Hint: provide a full path or a filename that exists under {sessions_dir}."
        )
    if len(matches) > 1:
        raise FileNotFoundError(
            f"Ambiguous filename '{candidate}' matched {len(matches)} files. Please provide a full path."
        )
    return matches[0]


def extract_messages(
    input_path: Path,
    out: Optional[Path],
    out_dir: Optional[Path],
    force: bool,
    to_stdout: bool,
) -> int:
    if to_stdout:
        count = 0
        for count, message in enumerate(iter_messages(input_path), start=1):
            print(json.dumps(message, ensure_ascii=False))
        return count

    # Determine output path
    if out is None:
        base_name = input_path.with_suffix("").name + ".messages.jsonl"
        target_dir = out_dir if out_dir is not None else Path.cwd()
        out = target_dir / base_name

    if out.exists() and not force:
        raise FileExistsError(
            f"Refusing to overwrite existing file: {out}. Use --force to overwrite or specify --output."
        )

    return write_messages_jsonl(input_path, out)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="codex-summarize-session",
        description="List Codex sessions and extract message lines from a session JSONL log.",
    )
    p.add_argument(
        "--sessions-dir",
        type=Path,
        default=get_default_sessions_dir(),
        help="Base directory containing session JSONL files (default: ~/.codex/sessions)",
    )

    sub = p.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="List recent session JSONL files")
    p_list.add_argument("--limit", type=int, default=20, help="Limit number of entries (default: 20)")

    p_browse = sub.add_parser("browse", help="Interactively browse session JSONL files")
    p_browse.add_argument("--limit", type=int, default=20, help="Limit number of entries (default: 20)")
    p_browse.add_argument(
        "--summaries-dir",
        type=Path,
        help="Directory to store cached summaries used by browse mode (default: ~/.codex/summaries)",
    )
    p_browse.add_argument(
        "--prompt",
        default="default",
        help="Prompt preset to load when generating summaries interactively (default: default)",
    )
    p_browse.add_argument(
        "--summary-model",
        default="x-ai/grok-4-fast:free",
        help="OpenRouter model identifier to use for interactive summaries (default: x-ai/grok-4-fast:free)",
    )
    p_browse.add_argument(
        "--summary-temperature",
        type=float,
        default=0.2,
        help="Sampling temperature applied when generating summaries (default: 0.2)",
    )
    p_browse.add_argument(
        "--summary-max-tokens",
        type=int,
        help="Optional cap for completion tokens during interactive summarisation",
    )
    p_browse.add_argument(
        "--summary-reasoning-effort",
        choices=["low", "medium", "high", "none"],
        default="medium",
        help="Reasoning effort hint when supported by the chosen model (default: medium)",
    )

    p_extract = sub.add_parser("extract", help="Extract only 'type=message' lines to a JSONL file")
    p_extract.add_argument("input", help="Path or filename of the session JSONL")
    p_extract.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output file path for extracted messages. If omitted, uses <cwd>/<input-basename>.messages.jsonl or --output-dir if provided.",
    )
    p_extract.add_argument(
        "--output-dir",
        type=Path,
        help="Directory to write the extracted file into. Ignored if --output is provided. Default: current working directory.",
    )
    p_extract.add_argument("--stdout", action="store_true", help="Write to stdout instead of a file")
    p_extract.add_argument("-f", "--force", action="store_true", help="Overwrite output if it exists")

    p_summaries = sub.add_parser("summaries", help="Generate and inspect cached summaries")
    summaries_sub = p_summaries.add_subparsers(dest="summaries_cmd", required=True)

    p_generate = summaries_sub.add_parser("generate", help="Generate Markdown summaries for session logs")
    p_generate.add_argument("sessions", nargs="+", help="Session indices, filenames, or paths to summarise")
    p_generate.add_argument(
        "--prompt",
        default="default",
        help="Prompt preset name to load from the prompts directory (default: default)",
    )
    p_generate.add_argument(
        "--model",
        default="x-ai/grok-4-fast:free",
        help="OpenRouter model identifier to use (default: x-ai/grok-4-fast:free)",
    )
    p_generate.add_argument(
        "--summaries-dir",
        type=Path,
        help="Directory to store cached summaries (default: ~/.codex/summaries)",
    )
    p_generate.add_argument(
        "--temperature",
        type=float,
        default=0.2,
        help="Sampling temperature for the completion (default: 0.2)",
    )
    p_generate.add_argument(
        "--max-tokens",
        type=int,
        help="Optional cap for completion tokens",
    )
    p_generate.add_argument(
        "--reasoning-effort",
        choices=["low", "medium", "high", "none"],
        default="medium",
        help="Reasoning effort hint when supported by the chosen model (default: medium)",
    )
    p_generate.add_argument(
        "--refresh",
        action="store_true",
        help="Bypass any cached summary and regenerate it via OpenRouter",
    )
    p_generate.add_argument(
        "--no-cache",
        action="store_true",
        help="Skip reading existing summaries before calling the API",
    )
    p_generate.add_argument(
        "--stdout",
        action="store_true",
        help="Write the resulting summary to stdout instead of the cache (single session only)",
    )
    p_generate.add_argument(
        "--strip-metadata",
        action="store_true",
        help="When used with --stdout, omit YAML front matter and print only the Markdown body",
    )

    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    sessions_dir: Path = args.sessions_dir
    if not sessions_dir.exists():
        parser.error(f"Sessions dir does not exist: {sessions_dir}")

    if args.cmd == "list":
        paths = list_sessions(sessions_dir, limit=args.limit)
        base_label = str(sessions_dir)
        if paths:
            print(f"Sessions under {base_label}")
        else:
            print(f"No session files found under {base_label}")

        entries = build_session_entries(paths, sessions_dir)
        if entries:
            summary_counts = build_summary_counts(
                entries,
                get_default_summaries_dir(),
                sessions_dir,
            )
            header, lines = format_session_table(entries, summary_counts)
            print(header)
            for line in lines:
                print(line)
        return 0

    if args.cmd == "browse":
        paths = list_sessions(sessions_dir, limit=args.limit)
        base_label = str(sessions_dir)
        if not paths:
            print(f"No session files found under {base_label}")
            return 0

        entries = build_session_entries(paths, sessions_dir)
        summary_options = BrowseSummaryOptions(
            summaries_dir=(args.summaries_dir or get_default_summaries_dir()).expanduser(),
            prompt_variant=args.prompt,
            model=args.summary_model,
            temperature=args.summary_temperature,
            max_tokens=args.summary_max_tokens,
            reasoning_effort=normalize_reasoning_effort(args.summary_reasoning_effort),
        )
        try:
            from .browser import browse_sessions
        except ModuleNotFoundError as exc:
            if exc.name == "prompt_toolkit":
                parser.error(
                    "Interactive browsing requires optional dependency 'prompt_toolkit'. "
                    "Install it from the repo with `python -m pip install .[browser]` "
                    "(or `pipx inject codex-summarize-session prompt_toolkit`)."
                )
            raise

        return browse_sessions(entries, sessions_dir, summary_options)

    if args.cmd == "extract":
        if args.output and args.output_dir:
            parser.error("Specify either --output or --output-dir, not both.")
        try:
            input_path = resolve_session_path(args.input, sessions_dir)
        except FileNotFoundError as e:
            parser.error(str(e))
            return 2

        try:
            count = extract_messages(
                input_path=input_path,
                out=args.output,
                out_dir=args.output_dir,
                force=args.force,
                to_stdout=args.stdout,
            )
        except (FileExistsError, OSError) as e:
            parser.error(str(e))
            return 2

        if not args.stdout:
            if args.output is not None:
                out_path = args.output
            else:
                base_name = input_path.with_suffix("").name + ".messages.jsonl"
                target_dir = args.output_dir if args.output_dir else Path.cwd()
                out_path = target_dir / base_name
            print(f"Wrote {count} message lines to {out_path}")
        return 0

    if args.cmd == "summaries":
        if args.summaries_cmd == "generate":
            return handle_summaries_generate(args, parser, sessions_dir)
        parser.error("Unknown summaries subcommand")
        return 2

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
