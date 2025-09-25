"""Shared helpers for working with Codex session JSONL logs."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Optional


def iter_jsonl(path: Path) -> Iterable[dict]:
    """Yield JSON objects from a JSON Lines file, skipping malformed rows."""
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


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


def write_messages_jsonl(source: Path, target: Path) -> int:
    """Write only message entries from ``source`` to ``target``; return count."""
    target.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with target.open("w", encoding="utf-8") as handle:
        for message in iter_messages(source):
            handle.write(json.dumps(message, ensure_ascii=False) + "\n")
            count += 1
    return count
