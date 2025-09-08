from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Iterable, Optional


def get_default_sessions_dir() -> Path:
    return Path("~/.codex/sessions").expanduser()


def iter_jsonl(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                # Skip malformed lines instead of failing the whole run
                continue


def list_sessions(sessions_dir: Path, limit: Optional[int] = None) -> list[Path]:
    files = sorted(
        (p for p in sessions_dir.rglob("*.jsonl") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return files[:limit] if limit else files


def resolve_session_path(candidate: str, sessions_dir: Path) -> Path:
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
    count = 0

    if to_stdout:
        for obj in iter_jsonl(input_path):
            if obj.get("type") == "message":
                print(json.dumps(obj, ensure_ascii=False))
                count += 1
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

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for obj in iter_jsonl(input_path):
            if obj.get("type") == "message":
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")
                count += 1
    return count


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

    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    sessions_dir: Path = args.sessions_dir
    if not sessions_dir.exists():
        parser.error(f"Sessions dir does not exist: {sessions_dir}")

    if args.cmd == "list":
        files = list_sessions(sessions_dir, limit=args.limit)
        for i, p in enumerate(files, start=1):
            # Show size and mtime briefly
            try:
                st = p.stat()
                size = st.st_size
            except OSError:
                size = 0
            print(f"{i:3d}. {p} ({size} bytes)")
        return 0

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

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
