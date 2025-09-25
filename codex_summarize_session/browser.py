from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Dict, Optional, Sequence, TYPE_CHECKING

import pydoc
from prompt_toolkit.application import Application, run_in_terminal
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, Window, ScrollOffsets
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.data_structures import Point
from prompt_toolkit.layout.dimension import D
from prompt_toolkit.styles import Style

from .summaries import (
    AuthenticationError,
    ClientConfigurationError,
    OpenRouterError,
    PromptValidationError,
    RateLimitError,
    SummaryRequest,
    SummaryService,
    TransientError,
)
from .summaries.storage import SummaryPathResolver, load_summary

if TYPE_CHECKING:
    from .cli import BrowseSummaryOptions, SessionEntry
    from .summaries import OpenRouterClient


@dataclass
class ExtractionRequest:
    destination: Path
    force: bool


@dataclass
class SummaryDetailState:
    cache_path: Path
    cache_exists: bool
    variants: Dict[str, Path]
    messages_path: Path
    messages_exists: bool
    metadata: Optional[Dict[str, object]]
    metadata_error: Optional[str]
    cost_text: Optional[str]
    message_count: Optional[int]
    modified_at: Optional[datetime]


def _render_cost(cost_data: Optional[Dict[str, object]]) -> Optional[str]:
    if isinstance(cost_data, dict):
        total = cost_data.get("total")
        if isinstance(total, (int, float)):
            return f"${total:.6f}"
    return None


class SessionBrowser:
    """Interactive browser backed by prompt_toolkit."""

    PAGE_JUMP = 10

    def __init__(
        self,
        entries: Sequence["SessionEntry"],
        sessions_dir: Path,
        summary_options: "BrowseSummaryOptions",
    ) -> None:
        self.entries = list(entries)
        self.sessions_dir = sessions_dir
        self.summary_options = summary_options
        self.selected_index = 0
        session_count = len(self.entries)
        noun = "session" if session_count == 1 else "sessions"
        self.status: str = f"{session_count} {noun} under {self.sessions_dir}"
        self._app: Optional[Application] = None
        self._body_window: Optional[Window] = None
        self._header_window: Optional[Window] = None
        self._detail_window: Optional[Window] = None
        self._active_task: Optional[asyncio.Task[None]] = None
        self._summary_service: Optional[SummaryService] = None
        self._summary_client: Optional["OpenRouterClient"] = None
        self._summary_error: Optional[str] = None
        self._detail_cache: Dict[Path, dict] = {}

        self.summary_resolver = SummaryPathResolver(
            summary_options.summaries_dir, sessions_dir
        )
        self.summary_counts: Dict[Path, int] = {
            entry.path: len(self.summary_resolver.cached_variants_for(entry.path))
            for entry in self.entries
        }
        self._update_table_cache()

    def _get_detail_state(self, entry: "SessionEntry") -> SummaryDetailState:
        state = self._detail_cache.get(entry.path)
        if state:
            return state

        cache_path = self.summary_resolver.cache_path_for(
            entry.path,
            self.summary_options.prompt_variant,
            self.summary_options.model,
        )
        messages_path = self.summary_resolver.messages_path_for(entry.path)
        variants = self.summary_resolver.cached_variants_for(entry.path)

        metadata: Optional[Dict[str, object]] = None
        metadata_error: Optional[str] = None
        cost_text: Optional[str] = None
        message_count: Optional[int] = None
        modified_at: Optional[datetime] = None
        if cache_path.is_file():
            try:
                record = load_summary(cache_path)
                metadata = record.metadata
                if isinstance(metadata, dict):
                    cost_text = _render_cost(metadata.get("cost_estimate_usd"))
                    raw_count = metadata.get("message_count")
                    if isinstance(raw_count, int):
                        message_count = raw_count
                modified_at = datetime.fromtimestamp(cache_path.stat().st_mtime)
            except Exception as exc:  # pragma: no cover - defensive
                metadata_error = str(exc)

        state = SummaryDetailState(
            cache_path=cache_path,
            cache_exists=cache_path.is_file(),
            variants=variants,
            messages_path=messages_path,
            messages_exists=messages_path.is_file(),
            metadata=metadata,
            metadata_error=metadata_error,
            cost_text=cost_text,
            message_count=message_count,
            modified_at=modified_at,
        )
        self._detail_cache[entry.path] = state
        return state

    def _invalidate_detail_cache(self, entry_path: Path) -> None:
        self._detail_cache.pop(entry_path, None)

    def _update_table_cache(self) -> None:
        from .cli import format_session_table

        header, rows = format_session_table(self.entries, self.summary_counts)
        self._table_header = header
        self._table_rows = rows

    def _current_entry(self) -> Optional["SessionEntry"]:
        if not self.entries:
            return None
        index = min(max(self.selected_index, 0), len(self.entries) - 1)
        return self.entries[index]

    def _refresh_summary_counts(self, entry: "SessionEntry") -> None:
        self.summary_counts[entry.path] = len(
            self.summary_resolver.cached_variants_for(entry.path)
        )
        self._update_table_cache()

    def _ensure_summary_service(self) -> Optional[SummaryService]:
        if self._summary_service is not None:
            return self._summary_service
        if self._summary_error:
            return None

        from .cli import create_summary_service

        try:
            service, client = create_summary_service(
                self.sessions_dir,
                self.summary_options.summaries_dir,
            )
        except AuthenticationError as exc:
            message = str(exc)
        except (OpenRouterError, ClientConfigurationError) as exc:
            message = f"Failed to initialise summaries: {exc}"
        except Exception as exc:  # pragma: no cover - defensive
            message = f"Unexpected error initialising summaries: {exc}"
        else:
            self._summary_service = service
            self._summary_client = client
            self._summary_error = None
            return service

        self._summary_error = message
        self.status = message
        if self._app:
            self._app.invalidate()
        return None

    def _show_summary(self, cache_path: Path) -> None:
        try:
            text = cache_path.read_text(encoding="utf-8")
        except OSError as exc:
            self.status = f"Failed to read summary: {exc}"
            if self._app:
                self._app.invalidate()
            return

        def display() -> None:  # pragma: no cover - interactive
            pydoc.pager(text)

        run_in_terminal(display)
        self.status = f"Displayed summary -> {cache_path}"
        if self._app:
            self._app.invalidate()

    # ---- Layout helpers -------------------------------------------------
    def _entry_fragments(self) -> list[tuple[str, str]]:
        fragments: list[tuple[str, str]] = []
        for idx, line in enumerate(self._table_rows):
            style = "class:session-list.selected" if idx == self.selected_index else "class:session-list"
            fragments.append((style, line))
            if idx != len(self._table_rows) - 1:
                fragments.append(("", "\n"))
        return fragments

    def _header_fragment(self) -> list[tuple[str, str]]:
        return [("class:session-list.header", self._table_header)]

    def _detail_fragments(self) -> list[tuple[str, str]]:
        entry = self._current_entry()
        if entry is None:
            text = "No session selected."
            return [("class:detail", text)]

        state = self._get_detail_state(entry)
        variant_names = ", ".join(state.variants.keys()) if state.variants else "none"
        count = len(state.variants)
        lines = [
            f"Session {entry.index}: {entry.display_path}",
            f"Bytes: {entry.size_display} | CWD: {entry.cwd_display}",
            f"Cached variants: {count} ({variant_names})",
        ]

        default_status = "cached" if state.cache_exists else "missing"
        lines.append(
            f"Default summary ({self.summary_options.prompt_variant}): {default_status} -> {state.cache_path}"
        )
        if state.cost_text:
            lines.append(f"Last cost: {state.cost_text}")
        if state.modified_at:
            lines.append(
                f"Modified: {state.modified_at.isoformat(timespec='seconds')}"
            )
        if state.metadata_error:
            lines.append(f"Metadata error: {state.metadata_error}")

        message_status = "cached" if state.messages_exists else "missing"
        if state.message_count is not None:
            lines.append(
                f"Messages ({message_status}): {state.message_count} lines -> {state.messages_path}"
            )
        else:
            lines.append(f"Messages ({message_status}): {state.messages_path}")

        if self._summary_error:
            lines.append(f"Summary service unavailable: {self._summary_error}")

        text = "\n".join(lines)
        return [("class:detail", text)]

    def _handle_view_summary(self) -> None:
        entry = self._current_entry()
        if entry is None:
            self.status = "No session selected."
            if self._app:
                self._app.invalidate()
            return

        state = self._get_detail_state(entry)
        if not state.cache_exists:
            self.status = (
                f"No cached summary for {entry.display_path} ({self.summary_options.prompt_variant})."
            )
            if self._app:
                self._app.invalidate()
            return

        self._show_summary(state.cache_path)

    def _handle_generate_or_view(self, refresh: bool) -> None:
        entry = self._current_entry()
        if entry is None:
            self.status = "No session selected."
            if self._app:
                self._app.invalidate()
            return

        if not refresh:
            state = self._get_detail_state(entry)
            if state.cache_exists:
                self._show_summary(state.cache_path)
                return

        self._start_summary_task(entry, refresh=refresh)

    def _start_summary_task(self, entry: "SessionEntry", refresh: bool) -> None:
        service = self._ensure_summary_service()
        if service is None:
            return

        if self._active_task and not self._active_task.done():
            self.status = "Summary generation already in progress."
            if self._app:
                self._app.invalidate()
            return

        request = SummaryRequest(
            session_path=entry.path,
            prompt_variant=self.summary_options.prompt_variant,
            model=self.summary_options.model,
            reasoning_effort=self.summary_options.reasoning_effort,
            refresh=refresh,
        )

        action = "Regenerating" if refresh else "Generating"
        self.status = f"{action} summary for {entry.display_path}..."
        if self._app:
            self._app.invalidate()

        async def worker() -> None:
            try:
                loop = asyncio.get_running_loop()
                record = await loop.run_in_executor(
                    None,
                    partial(
                        service.generate,
                        request,
                        use_cache=not refresh,
                        refresh=refresh,
                        temperature=self.summary_options.temperature,
                        max_tokens=self.summary_options.max_tokens,
                    ),
                )
            except (
                PromptValidationError,
                AuthenticationError,
                RateLimitError,
                TransientError,
                ClientConfigurationError,
                OpenRouterError,
            ) as exc:
                self.status = f"Summary failed: {exc}"
            except Exception as exc:  # pragma: no cover - defensive
                self.status = f"Summary failed: {exc}"
            else:
                self._invalidate_detail_cache(entry.path)
                self._refresh_summary_counts(entry)
                verb = "Regenerated" if refresh else "Generated"
                self.status = f"{verb} summary -> {record.cache_path}"
            finally:
                self._active_task = None
                if self._app:
                    self._app.invalidate()

        if self._app is None:  # pragma: no cover - defensive
            return
        self._active_task = self._app.create_background_task(worker())

    def _cleanup(self) -> None:
        if self._active_task and not self._active_task.done():
            self._active_task.cancel()
        if self._summary_client is not None:
            try:
                self._summary_client.close()
            except Exception:  # pragma: no cover - defensive
                pass
            self._summary_client = None

    def _instructions_fragment(self) -> list[tuple[str, str]]:
        text = (
            "Up/Down navigate | PgUp/PgDn jump | Home/End | Enter extract | "
            "s view | g generate/view | G regenerate | q quit"
        )
        return [("class:instructions", text)]

    def _status_fragment(self) -> list[tuple[str, str]]:
        return [("class:status", self.status)]

    # ---- Key bindings ---------------------------------------------------
    def _build_key_bindings(self) -> KeyBindings:
        kb = KeyBindings()

        @kb.add("up")
        def _(event) -> None:  # pragma: no cover - interactive behaviour
            self._move_selection(-1)

        @kb.add("down")
        def _(event) -> None:  # pragma: no cover - interactive behaviour
            self._move_selection(1)

        @kb.add("pageup")
        def _(event) -> None:  # pragma: no cover - interactive behaviour
            self._move_selection(-self.PAGE_JUMP)

        @kb.add("pagedown")
        def _(event) -> None:  # pragma: no cover - interactive behaviour
            self._move_selection(self.PAGE_JUMP)

        @kb.add("home")
        def _(event) -> None:  # pragma: no cover - interactive behaviour
            self._set_selection(0)

        @kb.add("end")
        def _(event) -> None:  # pragma: no cover - interactive behaviour
            if self.entries:
                self._set_selection(len(self.entries) - 1)

        @kb.add("enter")
        def _(event) -> None:  # pragma: no cover - interactive behaviour
            self._handle_extract()

        @kb.add("s")
        def _(event) -> None:  # pragma: no cover - interactive behaviour
            self._handle_view_summary()

        @kb.add("g")
        def _(event) -> None:  # pragma: no cover - interactive behaviour
            self._handle_generate_or_view(refresh=False)

        @kb.add("G")
        def _(event) -> None:  # pragma: no cover - interactive behaviour
            self._handle_generate_or_view(refresh=True)

        @kb.add("q")
        @kb.add("Q")
        @kb.add("escape")
        @kb.add("c-c")
        def _(event) -> None:  # pragma: no cover - interactive behaviour
            event.app.exit(result=0)

        return kb

    # ---- Selection helpers ----------------------------------------------
    def _move_selection(self, delta: int) -> None:
        if not self.entries:
            return
        new_index = max(0, min(len(self.entries) - 1, self.selected_index + delta))
        self._set_selection(new_index)

    def _set_selection(self, index: int) -> None:
        if not self.entries:
            return
        if index == self.selected_index:
            return
        self.selected_index = index
        if self._app is not None:
            self._app.invalidate()

    # ---- Extraction handling -------------------------------------------
    def _handle_extract(self) -> None:
        if not self.entries:
            return
        entry = self.entries[self.selected_index]

        def task() -> None:
            request = self._prompt_destination(entry)
            if request is None:
                self.status = "Extraction cancelled."
                return
            from .cli import extract_messages

            try:
                count = extract_messages(
                    input_path=entry.path,
                    out=request.destination,
                    out_dir=None,
                    force=request.force,
                    to_stdout=False,
                )
            except FileExistsError:
                self.status = f"Refused to overwrite existing file: {request.destination}"
            except OSError as exc:
                self.status = f"Failed to write {request.destination}: {exc}"
            else:
                self.status = f"Wrote {count} messages -> {request.destination}"

        run_in_terminal(task)
        if self._app is not None:
            self._app.invalidate()

    def _prompt_destination(self, entry: "SessionEntry") -> Optional[ExtractionRequest]:
        default_name = entry.path.with_suffix("").name + ".messages.jsonl"
        default_path = Path.cwd() / default_name
        current_default = default_path

        while True:
            try:
                response = input(f"Destination path [{current_default}]: ")
            except (KeyboardInterrupt, EOFError):
                return None

            text = response.strip()
            if not text:
                text = str(current_default)
            dest = Path(text).expanduser()
            if dest.is_dir():
                dest = dest / default_name

            if dest.exists():
                try:
                    confirm = input(f"{dest} exists. Overwrite? [y/N]: ")
                except (KeyboardInterrupt, EOFError):
                    return None
                if confirm.strip().lower() in {"y", "yes"}:
                    return ExtractionRequest(destination=dest, force=True)
                current_default = dest
                continue

            return ExtractionRequest(destination=dest, force=False)

    # ---- Public API -----------------------------------------------------
    def run(self) -> int:
        def cursor_position() -> Point:
            if not self._table_rows:
                return Point(0, 0)
            index = min(max(self.selected_index, 0), len(self._table_rows) - 1)
            return Point(0, index)

        header_control = FormattedTextControl(
            self._header_fragment,
            focusable=False,
        )
        self._header_window = Window(
            content=header_control,
            height=1,
            always_hide_cursor=True,
        )
        body_control = FormattedTextControl(
            self._entry_fragments,
            focusable=True,
            get_cursor_position=cursor_position,
        )
        self._body_window = Window(
            content=body_control,
            height=D(min=3),
            wrap_lines=False,
            always_hide_cursor=True,
            scroll_offsets=ScrollOffsets(top=2, bottom=2),
        )
        detail_control = FormattedTextControl(
            self._detail_fragments,
            focusable=False,
        )
        self._detail_window = Window(
            content=detail_control,
            height=D(min=4),
            wrap_lines=True,
            always_hide_cursor=True,
        )
        instructions_window = Window(
            content=FormattedTextControl(self._instructions_fragment),
            height=1,
            always_hide_cursor=True,
        )
        status_window = Window(
            content=FormattedTextControl(self._status_fragment),
            height=1,
            always_hide_cursor=True,
        )

        layout = Layout(
            HSplit(
                [
                    self._header_window,
                    self._body_window,
                    Window(height=1, char="-", always_hide_cursor=True),
                    self._detail_window,
                    Window(height=1, char="-", always_hide_cursor=True),
                    instructions_window,
                    status_window,
                ]
            )
        )

        style = Style.from_dict(
            {
                "session-list": "",
                "session-list.selected": "reverse",
                "session-list.header": "bold",
                "instructions": "fg:#888888",
                "status": "fg:#000000 bg:#e5e5e5",
                "detail": "",
            }
        )

        self._app = Application(
            layout=layout,
            key_bindings=self._build_key_bindings(),
            style=style,
            full_screen=True,
        )
        result = self._app.run()
        self._cleanup()
        return 0 if result is None else result


def browse_sessions(
    entries: Sequence["SessionEntry"],
    sessions_dir: Path,
    summary_options: "BrowseSummaryOptions",
) -> int:
    browser = SessionBrowser(
        entries=entries,
        sessions_dir=sessions_dir,
        summary_options=summary_options,
    )
    return browser.run()
