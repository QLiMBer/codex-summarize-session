from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence, TYPE_CHECKING

from prompt_toolkit.application import Application, run_in_terminal
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, Window, ScrollOffsets
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.data_structures import Point
from prompt_toolkit.layout.dimension import D
from prompt_toolkit.styles import Style

if TYPE_CHECKING:
    from .cli import SessionEntry


@dataclass
class ExtractionRequest:
    destination: Path
    force: bool


class SessionBrowser:
    """Interactive browser backed by prompt_toolkit."""

    PAGE_JUMP = 10

    def __init__(self, entries: Sequence["SessionEntry"], sessions_dir: Path) -> None:
        self.entries = list(entries)
        self.sessions_dir = sessions_dir
        self.selected_index = 0
        session_count = len(self.entries)
        noun = "session" if session_count == 1 else "sessions"
        self.status: str = f"{session_count} {noun} under {self.sessions_dir}"
        self._app: Optional[Application] = None
        self._body_window: Optional[Window] = None

    # ---- Layout helpers -------------------------------------------------
    def _entry_fragments(self) -> list[tuple[str, str]]:
        from .cli import format_session_entry_lines

        lines = format_session_entry_lines(self.entries)
        fragments: list[tuple[str, str]] = []
        for idx, line in enumerate(lines):
            style = "class:session-list.selected" if idx == self.selected_index else "class:session-list"
            fragments.append((style, line))
            if idx != len(lines) - 1:
                fragments.append(("", "\n"))
        return fragments

    def _instructions_fragment(self) -> list[tuple[str, str]]:
        text = "Up/Down navigate | PgUp/PgDn jump | Home/End | Enter extract | q quit"
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
        body_control = FormattedTextControl(
            self._entry_fragments,
            focusable=True,
            get_cursor_position=lambda: Point(0, self.selected_index),
        )
        self._body_window = Window(
            content=body_control,
            height=D(min=3),
            wrap_lines=False,
            always_hide_cursor=True,
            scroll_offsets=ScrollOffsets(top=2, bottom=2),
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
                    self._body_window,
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
                "instructions": "fg:#888888",
                "status": "fg:#000000 bg:#e5e5e5",
            }
        )

        self._app = Application(
            layout=layout,
            key_bindings=self._build_key_bindings(),
            style=style,
            full_screen=True,
        )
        result = self._app.run()
        return 0 if result is None else result


def browse_sessions(entries: Sequence["SessionEntry"], sessions_dir: Path) -> int:
    browser = SessionBrowser(entries=entries, sessions_dir=sessions_dir)
    return browser.run()
