from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Optional


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


def extract_message_from_obj(obj: Any) -> Optional[dict]:
    if not isinstance(obj, dict):
        return None
    if obj.get("type") == "message":
        return obj
    payload = obj.get("payload")
    if isinstance(payload, dict) and payload.get("type") == "message":
        message = dict(payload)
        timestamp = obj.get("timestamp")
        if timestamp is not None and "timestamp" not in message:
            message["timestamp"] = timestamp
        response_id = obj.get("id")
        if response_id and "response_id" not in message:
            message["response_id"] = response_id
        return message
    return None


def iter_messages(path: Path) -> Iterable[dict]:
    for obj in iter_jsonl(path):
        message = extract_message_from_obj(obj)
        if message:
            yield message


def list_sessions(sessions_dir: Path, limit: Optional[int] = None) -> list[Path]:
    files = sorted(
        (p for p in sessions_dir.rglob("*.jsonl") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return files[:limit] if limit else files


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
    count = 0

    if to_stdout:
        for message in iter_messages(input_path):
            print(json.dumps(message, ensure_ascii=False))
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
        for message in iter_messages(input_path):
            f.write(json.dumps(message, ensure_ascii=False) + "\n")
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
        base_label = str(sessions_dir)
        if files:
            print(f"Sessions under {base_label}")
        else:
            print(f"No session files found under {base_label}")
        entries = []
        for i, p in enumerate(files, start=1):
            try:
                st = p.stat()
                size = st.st_size
            except OSError:
                size = 0
            try:
                relative = p.relative_to(sessions_dir)
                display_path = relative.as_posix()
            except ValueError:
                display_path = str(p)
            size_str = f"{size:,}".replace(",", " ")
            cwd = extract_cwd_from_session(p)
            cwd_display = cwd if cwd else "?"
            prefix = f"{i:3d}. {display_path}"
            entries.append((prefix, size_str, cwd_display))

        if entries:
            prefix_width = max(len(prefix) for prefix, _, _ in entries)
            size_width = max(len(size_str) for _, size_str, _ in entries)
            for prefix, size_str, cwd_display in entries:
                print(
                    f"{prefix.ljust(prefix_width)}  {size_str.rjust(size_width)} B  cwd: {cwd_display}"
                )
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
