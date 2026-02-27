# MCUB interactive shell - runs inside the kernel's asyncio event loop.
# Commands live in console/bin/<n>.py and expose run(shell, args).

import os
import sys
import tty
import time
import termios
import logging
import asyncio
import importlib.util
import traceback
import fcntl
import pty
import select
import struct
import tempfile
import threading
import random
import math
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import ShellConfig


class _C:
    RESET      = "\033[0m"
    BOLD       = "\033[1m"
    DIM        = "\033[2m"
    ITALIC     = "\033[3m"
    RED        = "\033[91m"
    GREEN      = "\033[92m"
    YELLOW     = "\033[93m"
    BLUE       = "\033[94m"
    MAGENTA    = "\033[95m"
    CYAN       = "\033[96m"
    WHITE      = "\033[97m"
    GREY       = "\033[90m"
    CLEAR_LINE = "\033[2K"
    SAVE_CUR   = "\033[s"
    REST_CUR   = "\033[u"

    PROMPT_COLORS = {
        "green":   "\033[92m",
        "cyan":    "\033[96m",
        "yellow":  "\033[93m",
        "white":   "\033[97m",
        "magenta": "\033[95m",
        "blue":    "\033[94m",
    }

    LOG_COLORS = {
        "DEBUG":    "\033[97m",
        "INFO":     "\033[96m",
        "WARNING":  "\033[93m",
        "ERROR":    "\033[91m",
        "CRITICAL": "\033[91m\033[1m",
    }


class _Anim:
    """
    All animations write directly to the real stdout fd.
    They are short blocking calls (< 600 ms total).
    """

    # Braille spinner frames
    SPINNER_FRAMES = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
    # Classic dot spinner alternative
    DOT_FRAMES     = ["⣾","⣽","⣻","⢿","⡿","⣟","⣯","⣷"]
    # Bouncing bar
    BAR_FRAMES     = ["▏","▎","▍","▌","▋","▊","▉","█","▉","▊","▋","▌","▍","▎","▏"]

    @staticmethod
    def _fd():
        """Real stdout file-descriptor (never our wrapper)."""
        fd = sys.stdout
        # unwrap StdoutToShell layers
        while hasattr(fd, "_original"):
            fd = fd._original
        return fd

    @classmethod
    def _w(cls, text: str) -> None:
        cls._fd().write(text)
        cls._fd().flush()

    @classmethod
    def typewriter_header(cls, title: str, version: str, py: str, sep_char: str = "─") -> None:
        cols = _terminal_width()
        sep_len = min(cols - 2, 48)

        cls._w("\n")

        # Gradient colours cycling for the separator fill
        gradient = [
            "\033[38;5;21m",   # deep blue
            "\033[38;5;27m",
            "\033[38;5;33m",
            "\033[38;5;39m",
            "\033[38;5;45m",   # cyan
            "\033[38;5;51m",
            "\033[96m",
        ]

        # Typewriter: title char by char
        prefix = f"  {_C.CYAN}{_C.BOLD}"
        cls._w(f"\r{_C.CLEAR_LINE}{prefix}")
        for ch in title:
            cls._w(ch)
            time.sleep(0.022)
        cls._w(f"{_C.RESET}  {_C.GREY}v{version}  ·  {py}{_C.RESET}\n")

        # Separator fills left-to-right with colour wave
        for i in range(sep_len):
            col = gradient[int(i / sep_len * (len(gradient) - 1))]
            cls._w(f"{col}{sep_char}{_C.RESET}")
            time.sleep(0.008)
        cls._w("\n")

        # Hint line fades in after a tiny pause
        time.sleep(0.06)
        hint = "  Tab: complete  ↑↓: history  Ctrl+R: search  →: accept suggestion"
        cls._w(f"{_C.DIM}{hint}{_C.RESET}\n\n")

    @classmethod
    def cd_transition(cls, old_path: str, new_path: str) -> None:
        """Slide old path out, new path types in on same line."""
        arrow  = f"{_C.CYAN}→{_C.RESET}"
        old_s  = f"{_C.GREY}{old_path}{_C.RESET}"
        new_s  = f"{_C.GREEN}"

        cls._w(f"\r{_C.CLEAR_LINE}  {old_s}  {arrow}  {new_s}")
        for ch in new_path:
            cls._w(ch)
            time.sleep(0.018)
        cls._w(f"{_C.RESET}\n")
        time.sleep(0.06)
        # erase the line so it doesn't clutter output above prompt
        cls._w(f"\033[1A\r{_C.CLEAR_LINE}")

    @classmethod
    def goodbye_wave(cls, text: str = "Bye!") -> None:
        """Rainbow wave ripple across farewell text."""
        wave_colors = [
            "\033[91m", "\033[93m", "\033[92m",
            "\033[96m", "\033[94m", "\033[95m",
        ]
        phases = 6
        chars  = list(f"  {text}")
        for phase in range(phases):
            cls._w(f"\r{_C.CLEAR_LINE}")
            for i, ch in enumerate(chars):
                col_idx = (i + phase) % len(wave_colors)
                cls._w(f"{wave_colors[col_idx]}{_C.BOLD}{ch}{_C.RESET}")
            cls._w("  ")
            time.sleep(0.07)
        cls._w(f"\r{_C.CLEAR_LINE}  {_C.YELLOW}{_C.BOLD}{text}{_C.RESET}\n")

    @classmethod
    def bash_enter_banner(cls) -> None:
        """Neon flicker effect on the bash mode label."""
        label = "! bash mode"
        flicker_seq = [
            (_C.MAGENTA, _C.BOLD),
            (_C.GREY,    _C.DIM),
            (_C.MAGENTA, _C.BOLD),
            (_C.WHITE,   _C.BOLD),
            (_C.MAGENTA, _C.BOLD),
            (_C.GREY,    _C.DIM),
            (_C.MAGENTA, _C.BOLD),
        ]
        hint = f"{_C.GREY}(type 'exit' or Ctrl+D to return){_C.RESET}"

        cls._w("\n")
        for col, style in flicker_seq:
            cls._w(f"\r{_C.CLEAR_LINE}  {col}{style}{label}{_C.RESET}  {hint}")
            time.sleep(0.055)
        cls._w(f"\r{_C.CLEAR_LINE}  {_C.MAGENTA}{_C.BOLD}{label}{_C.RESET}  {hint}\n\n")

    @classmethod
    def bash_return_banner(cls) -> None:
        """Slide-in '← returned' message."""
        msg   = "← returned to MCUB shell"
        chars = list(f"  {msg}")
        cls._w(f"\n\r{_C.CLEAR_LINE}")
        for i, ch in enumerate(chars):
            alpha = int(232 + min(i / len(chars) * 23, 23))
            cls._w(f"\033[38;5;{alpha}m{ch}{_C.RESET}")
            time.sleep(0.012)
        cls._w("\n\n")

    @classmethod
    def error_pulse(cls, msg: str) -> None:
        """Red bracket pulse around the error message."""
        brackets = [("❮❮ ", " ❯❯"), ("❮  ", "  ❯"), ("   ", "   ")]
        for lb, rb in brackets:
            cls._w(f"\r{_C.CLEAR_LINE}  {_C.RED}{lb}{_C.RESET}{msg}{_C.RED}{rb}{_C.RESET}")
            time.sleep(0.08)
        cls._w(f"\r{_C.CLEAR_LINE}  {msg}\n")

    @classmethod
    def spinner(cls, label: str = "", delay: float = 0.30):
        """
        Context manager.  Shows a spinner if the block takes > `delay` seconds.

        Usage:
            with _Anim.spinner("Loading…"):
                do_slow_stuff()

        Also exposed on Shell as shell.spinner(label).
        """
        return _SpinnerCtx(label=label, delay=delay)


class _SpinnerCtx:
    """Threading spinner context manager."""

    FRAMES = _Anim.SPINNER_FRAMES
    FPS    = 12   # frames per second

    def __init__(self, label: str, delay: float):
        self._label   = label
        self._delay   = delay
        self._stop    = threading.Event()
        self._started = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def __enter__(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        # Erase spinner line
        fd = sys.stdout
        while hasattr(fd, "_original"):
            fd = fd._original
        fd.write(f"\r{_C.CLEAR_LINE}")
        fd.flush()

    def _run(self):
        # Wait for delay before showing anything
        if self._stop.wait(timeout=self._delay):
            return   # command already done

        fd = sys.stdout
        while hasattr(fd, "_original"):
            fd = fd._original

        frame_i = 0
        interval = 1.0 / self.FPS
        while not self._stop.is_set():
            frame = self.FRAMES[frame_i % len(self.FRAMES)]
            label = f" {self._label}" if self._label else ""
            fd.write(f"\r{_C.CLEAR_LINE}  {_C.CYAN}{frame}{_C.RESET}{_C.DIM}{label}{_C.RESET}")
            fd.flush()
            frame_i += 1
            self._stop.wait(timeout=interval)


_BIN_DIR = Path(__file__).parent / "bin"

_BUILTINS = {"help", "?", "clear", "cls", "history", "exit", "cd"}


def _load_command(name: str):
    path = _BIN_DIR / f"{name}.py"
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location(f"console.bin.{name}", path)
    mod  = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        return None
    return mod


def _all_commands() -> list[str]:
    """Return sorted list of all available command names."""
    cmds = list(_BUILTINS)
    if _BIN_DIR.exists():
        cmds += [p.stem for p in _BIN_DIR.glob("*.py") if not p.stem.startswith("_")]
    return sorted(set(cmds))


def _terminal_width() -> int:
    try:
        return os.get_terminal_size().columns
    except Exception:
        return 80

class _LineEditor:
    """
    Blocking raw-mode line reader. Run via loop.run_in_executor().

    Keyboard support:
      ← →              move cursor
      Ctrl+← →         jump word
      Home / End       start / end of line
      ↑ ↓              history navigation
      →  (at end)      accept autosuggestion
      Tab              cycle tab-completion
      Ctrl+R           reverse history search
      Backspace        delete left
      Ctrl+W           delete word left
      Delete           delete right
      Ctrl+A / E       start / end of line
      Ctrl+K           kill to end
      Ctrl+U           kill to start
      Ctrl+C           KeyboardInterrupt
      Ctrl+D           EOFError (on empty line)
    """

    def __init__(self, prompt_str: str, prompt_plain_len: int,
                 history: list, last_ok: bool = True):
        self._prompt          = prompt_str
        self._prompt_len      = prompt_plain_len   # visible width (no ANSI)
        self._history         = history
        self._hist_pos        = len(history)
        self._buf: list       = []
        self._cur             = 0
        self._saved_buf: list = []
        self._suggestion      = ""     # fish-style ghost text
        self._search_mode     = False  # Ctrl+R mode
        self._search_query    = ""
        self._search_result   = ""
        self._last_ok         = last_ok
        # tab completion state
        self._tab_candidates: list = []
        self._tab_index            = -1


    def _render(self) -> None:
        line = "".join(self._buf)

        if self._search_mode:
            prompt_part = (
                f"\r{_C.CLEAR_LINE}"
                f"{_C.CYAN}(reverse-i-search)`{self._search_query}': "
                f"{_C.RESET}{self._search_result}"
            )
            sys.stdout.write(prompt_part)
            sys.stdout.flush()
            return

        # Build right-prompt (time) — only when cursor is at end for simplicity
        now       = datetime.now().strftime("%H:%M:%S")
        rprompt   = f"{_C.GREY}{now}{_C.RESET}"
        rprompt_w = len(now)          # visible width

        cols          = _terminal_width()
        left_visible  = self._prompt_len + len(line)
        rp_col        = cols - rprompt_w

        # Right-prompt (drawn then cursor returned)
        rp_str = ""
        if rp_col > left_visible + 2:
            rp_str = f"\033[{rp_col}G{rprompt}"

        # Suggestion (ghost text when cursor is at end)
        suggestion_str = ""
        if self._suggestion and self._cur == len(self._buf):
            suggestion_str = f"{_C.GREY}{_C.DIM}{self._suggestion}{_C.RESET}"

        tail = len(self._buf) - self._cur

        # Draw: clear line, right-prompt, return to start, draw prompt+line+suggestion
        out = (
            f"\r{_C.CLEAR_LINE}"
            + (f"{rp_str}\r" if rp_str else "")
            + f"{self._prompt}{line}{suggestion_str}"
        )

        # Move cursor back past suggestion and past tail chars
        back = len(self._suggestion) * bool(suggestion_str) + tail
        if back:
            out += f"\033[{back}D"

        sys.stdout.write(out)
        sys.stdout.flush()


    @staticmethod
    def _getch() -> str:
        return sys.stdin.read(1)

    @staticmethod
    def _read_esc() -> str:
        ch = sys.stdin.read(1)
        if ch != "[":
            # Alt+key or bare ESC
            return f"\x1b{ch}" if ch else "\x1b"
        seq = ""
        while True:
            c = sys.stdin.read(1)
            seq += c
            if c.isalpha() or c == "~":
                break
        return seq


    def _update_suggestion(self) -> None:
        """Fish-style: find the most recent history entry starting with current buf."""
        if not self._buf:
            self._suggestion = ""
            return
        prefix = "".join(self._buf)
        for entry in reversed(self._history):
            if entry.startswith(prefix) and entry != prefix:
                self._suggestion = entry[len(prefix):]
                return
        self._suggestion = ""

    def _accept_suggestion(self) -> None:
        if self._suggestion:
            self._buf.extend(list(self._suggestion))
            self._cur = len(self._buf)
            self._suggestion = ""


    def _tab_complete(self) -> None:
        line   = "".join(self._buf[:self._cur])
        parts  = line.split()
        # Only complete first token (command name)
        if len(parts) > 1 or (parts and " " in line and line[-1] == " "):
            return
        prefix = parts[0] if parts else ""
        if self._tab_candidates and self._tab_index >= 0:
            # already cycling — advance
            self._tab_index = (self._tab_index + 1) % len(self._tab_candidates)
        else:
            all_cmds = _all_commands()
            self._tab_candidates = [c for c in all_cmds if c.startswith(prefix)]
            self._tab_index = 0 if self._tab_candidates else -1

        if self._tab_index >= 0:
            chosen = self._tab_candidates[self._tab_index]
            # Replace buf up to cursor with chosen completion
            after       = self._buf[self._cur:]
            self._buf   = list(chosen) + after
            self._cur   = len(chosen)
            self._suggestion = ""

    def _reset_tab(self) -> None:
        self._tab_candidates = []
        self._tab_index      = -1


    def _hist_up(self) -> None:
        if self._hist_pos == len(self._history):
            self._saved_buf = self._buf[:]
        if self._hist_pos > 0:
            self._hist_pos -= 1
            self._buf = list(self._history[self._hist_pos])
            self._cur = len(self._buf)

    def _hist_down(self) -> None:
        if self._hist_pos >= len(self._history):
            return
        self._hist_pos += 1
        if self._hist_pos == len(self._history):
            self._buf = self._saved_buf[:]
        else:
            self._buf = list(self._history[self._hist_pos])
        self._cur = len(self._buf)


    def _search_update(self) -> None:
        self._search_result = ""
        if not self._search_query:
            return
        for entry in reversed(self._history):
            if self._search_query in entry:
                self._search_result = entry
                break

    def _search_accept(self) -> None:
        result = self._search_result
        self._search_mode  = False
        self._search_query = ""
        self._search_result = ""
        if result:
            self._buf = list(result)
            self._cur = len(self._buf)


    def _word_right(self) -> None:
        n = len(self._buf)
        while self._cur < n and self._buf[self._cur] == " ":
            self._cur += 1
        while self._cur < n and self._buf[self._cur] != " ":
            self._cur += 1

    def _word_left(self) -> None:
        while self._cur > 0 and self._buf[self._cur - 1] == " ":
            self._cur -= 1
        while self._cur > 0 and self._buf[self._cur - 1] != " ":
            self._cur -= 1

    def _delete_word_left(self) -> None:
        """Ctrl+W: delete from cursor back to previous word boundary."""
        if self._cur == 0:
            return
        end = self._cur
        while self._cur > 0 and self._buf[self._cur - 1] == " ":
            self._cur -= 1
        while self._cur > 0 and self._buf[self._cur - 1] != " ":
            self._cur -= 1
        del self._buf[self._cur:end]

    def read(self) -> str:
        fd  = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            self._render()
            while True:
                ch = self._getch()

                if self._search_mode:
                    if ch in ("\r", "\n"):
                        sys.stdout.write("\r\n")
                        sys.stdout.flush()
                        self._search_accept()
                        return "".join(self._buf)
                    elif ch == "\x03":
                        self._search_mode  = False
                        self._search_query = ""
                        self._buf = []
                        self._cur = 0
                        self._render()
                        continue
                    elif ch == "\x12":   # another Ctrl+R — cycle
                        # find next match before current
                        idx = None
                        for i in range(len(self._history) - 1, -1, -1):
                            if (self._search_query in self._history[i]
                                    and self._history[i] != self._search_result):
                                self._search_result = self._history[i]
                                break
                    elif ch in ("\x7f", "\x08"):
                        self._search_query = self._search_query[:-1]
                        self._search_update()
                    elif ch >= " ":
                        self._search_query += ch
                        self._search_update()
                    self._render()
                    continue

                if ch in ("\r", "\n"):               # Enter
                    sys.stdout.write("\r\n")
                    sys.stdout.flush()
                    return "".join(self._buf)

                elif ch == "\t":                     # Tab — completion
                    self._tab_complete()

                elif ch == "\x03":                   # Ctrl+C
                    sys.stdout.write("^C\r\n")
                    sys.stdout.flush()
                    raise KeyboardInterrupt

                elif ch == "\x04":                   # Ctrl+D
                    if not self._buf:
                        sys.stdout.write("\r\n")
                        sys.stdout.flush()
                        raise EOFError
                    if self._cur < len(self._buf):
                        del self._buf[self._cur]

                elif ch == "\x01":                   # Ctrl+A
                    self._cur = 0

                elif ch == "\x05":                   # Ctrl+E
                    self._cur = len(self._buf)

                elif ch == "\x0b":                   # Ctrl+K
                    self._buf = self._buf[: self._cur]

                elif ch == "\x15":                   # Ctrl+U - delete to start of line
                    del self._buf[:self._cur]
                    self._cur = 0

                elif ch == "\x17":                   # Ctrl+W
                    self._delete_word_left()

                elif ch == "\x12":                   # Ctrl+R
                    self._search_mode  = True
                    self._search_query = ""
                    self._search_result = ""

                elif ch in ("\x7f", "\x08"):         # Backspace
                    if self._cur > 0:
                        self._cur -= 1
                        del self._buf[self._cur]

                elif ch == "\x1b":                   # Escape sequence
                    seq = self._read_esc()
                    if   seq == "A":      self._hist_up()
                    elif seq == "B":      self._hist_down()
                    elif seq == "C":                 # →
                        if self._cur < len(self._buf):
                            self._cur += 1
                        else:
                            self._accept_suggestion()
                    elif seq == "D":                 # ←
                        if self._cur > 0:
                            self._cur -= 1
                    elif seq in ("H", "1~"):         # Home
                        self._cur = 0
                    elif seq in ("F", "4~"):         # End
                        self._cur = len(self._buf)
                    elif seq == "3~":                # Delete
                        if self._cur < len(self._buf):
                            del self._buf[self._cur]
                    elif seq == "1;5C":              # Ctrl+→
                        self._word_right()
                    elif seq == "1;5D":              # Ctrl+←
                        self._word_left()

                elif ch >= " ":                      # printable
                    self._reset_tab()
                    self._buf.insert(self._cur, ch)
                    self._cur += 1

                # Update suggestion after every keystroke (skip in tab cycling)
                if ch != "\t":
                    self._reset_tab()
                    self._update_suggestion()

                self._render()

        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

class ShellLogHandler(logging.Handler):
    def __init__(self, shell: "Shell"):
        super().__init__()
        self._shell = shell

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            col = _C.LOG_COLORS.get(record.levelname, "")
            self._shell.output(f"{col}{msg}{_C.RESET}")
        except Exception:
            self.handleError(record)


class _StdoutToShell:
    """
    Перехватывает print() и любой вывод в stdout,
    добавляя \\r перед каждой строкой чтобы не ломать промпт.
    """

    def __init__(self, shell: "Shell", original_stdout):
        self._shell    = shell
        self._original = original_stdout
        self._buf      = ""

    def write(self, data: str) -> int:
        self._buf += data
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            self._original.write(f"\r{_C.CLEAR_LINE}{line}\n")
        self._original.flush()
        return len(data)

    def flush(self) -> None:
        if self._buf:
            self._original.write(f"\r{_C.CLEAR_LINE}{self._buf}")
            self._buf = ""
        self._original.flush()

    def fileno(self):
        return self._original.fileno()

    def __getattr__(self, name):
        return getattr(self._original, name)


class _StderrToShell:
    def __init__(self, shell: "Shell", original_stderr):
        self._shell    = shell
        self._original = original_stderr
        self._buf      = ""

    def write(self, data: str) -> int:
        self._buf += data
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line:
                self._shell.output(f"{_C.RED}{line}{_C.RESET}")
        return len(data)

    def flush(self) -> None:
        if self._buf:
            self._shell.output(f"{_C.RED}{self._buf}{_C.RESET}")
            self._buf = ""

    def fileno(self):
        return self._original.fileno()

    def __getattr__(self, name):
        return getattr(self._original, name)

class Shell:
    """
    MCUB interactive shell.

    Usage inside kernel's async def run():
        self.shell = Shell(kernel=self)
        shell.attach_logging()
        asyncio.ensure_future(self.shell.run())
    """

    PROMPT  = "❯"
    VERSION = "2.0.0"

    def __init__(self, kernel=None):
        self.kernel   = kernel
        self.cfg      = ShellConfig()
        self.running  = False
        self.cwd      = Path.cwd()
        self._history: list  = []
        self._last_ok: bool  = True          # last command exit status
        self._log_handler: Optional[ShellLogHandler] = None
        self._original_stdout = None
        self._original_stderr = None


    def attach_logging(self, logger: Optional[logging.Logger] = None) -> None:
        if self._log_handler is not None:
            return
        target = logger or logging.getLogger()
        self._log_handler = ShellLogHandler(self)
        self._log_handler.setFormatter(
            logging.Formatter("%(levelname)s:%(name)s:%(message)s")
        )
        target.addHandler(self._log_handler)
        for h in list(target.handlers):
            if h is not self._log_handler and isinstance(h, logging.StreamHandler):
                target.removeHandler(h)

    def detach_logging(self, logger: Optional[logging.Logger] = None) -> None:
        if self._log_handler is None:
            return
        (logger or logging.getLogger()).removeHandler(self._log_handler)
        self._log_handler = None

    def attach_stdout(self) -> None:
        if self._original_stdout is not None:
            return
        self._original_stdout = sys.stdout
        sys.stdout = _StdoutToShell(self, self._original_stdout)

    def detach_stdout(self) -> None:
        if self._original_stdout is None:
            return
        sys.stdout = self._original_stdout
        self._original_stdout = None

    def attach_stderr(self) -> None:
        if self._original_stderr is not None:
            return
        self._original_stderr = sys.stderr
        sys.stderr = _StderrToShell(self, self._original_stderr)

    def detach_stderr(self) -> None:
        if self._original_stderr is None:
            return
        sys.stderr = self._original_stderr
        self._original_stderr = None

    def spinner(self, label: str = "", delay: float = 0.30) -> "_SpinnerCtx":
        """
        Context manager: show a braille spinner if block takes > delay seconds.

        Usage inside a bin/ command:
            with shell.spinner("Fetching data…"):
                result = fetch()
        """
        return _Anim.spinner(label=label, delay=delay)

    @staticmethod
    def _is_interactive() -> bool:
        try:
            return os.getpgrp() == os.tcgetpgrp(sys.stdin.fileno())
        except Exception:
            return False

    def _pcol(self) -> str:
        name = self.cfg.get("shell", "prompt_color", fallback="cyan")
        return _C.PROMPT_COLORS.get(name, _C.CYAN)

    def _show_time(self) -> bool:
        return self.cfg.getboolean("display", "show_exec_time", fallback=True)

    def _short_cwd(self) -> str:
        """Return cwd, replacing $HOME with ~."""
        try:
            rel = self.cwd.relative_to(Path.home())
            return "~/" + str(rel) if str(rel) != "." else "~"
        except ValueError:
            return str(self.cwd)

    def _prompt_str(self) -> tuple[str, int]:
        """Return (ansi_prompt, visible_length)."""
        pc       = self._pcol()
        ok_col   = _C.GREEN if self._last_ok else _C.RED
        dir_part = f"{_C.BLUE}{_C.BOLD}{self._short_cwd()}{_C.RESET}"
        sym_part = f"{ok_col}{_C.BOLD}{self.PROMPT}{_C.RESET} "
        ansi     = f"{dir_part} {sym_part}"
        # visible length = len(cwd) + 1(space) + 1(prompt) + 1(space)
        visible  = len(self._short_cwd()) + 3
        return ansi, visible

    def output(self, text: str) -> None:
        """Print a line above the current input. Safe from any thread."""
        out_fd = self._original_stdout or sys.stdout
        lines  = text.split("\n")
        out    = "\r\n".join(f"{_C.CLEAR_LINE}{l}" for l in lines)
        out_fd.write(f"\r{out}\r\n")
        out_fd.flush()

    def _print_header(self) -> None:
        """Simple re-draw for clear/cls — no animation to avoid blocking."""
        title    = self.cfg.get("display", "title", fallback="MCUB Shell")
        sep_char = self.cfg.get("shell", "separator", fallback="─")
        cols     = _terminal_width()
        sep      = sep_char * min(cols - 2, 48)
        py       = f"Python {sys.version.split()[0]}"
        print(f"\n{_C.CYAN}{_C.BOLD}  {title}{_C.RESET}  "
              f"{_C.GREY}v{self.VERSION}  ·  {py}{_C.RESET}")
        print(f"{_C.GREY}{sep}{_C.RESET}")
        print(f"{_C.DIM}  Tab: complete  ↑↓: history  Ctrl+R: search  →: accept suggestion{_C.RESET}\n")

    def _expand_history(self, line: str) -> str:
        """Support !! (last command) and !n (nth entry)."""
        if line == "!!":
            if self._history:
                cmd = self._history[-1]
                self.output(f"{_C.GREY}  {cmd}{_C.RESET}")
                return cmd
            self.output(f"{_C.YELLOW}No previous command.{_C.RESET}")
            return ""
        if line.startswith("!") and line[1:].lstrip("-").isdigit():
            idx = int(line[1:])
            if idx < 0:
                idx = len(self._history) + idx
            else:
                idx -= 1           # 1-based → 0-based
            if 0 <= idx < len(self._history):
                cmd = self._history[idx]
                self.output(f"{_C.GREY}  {cmd}{_C.RESET}")
                return cmd
            self.output(f"{_C.YELLOW}No such history entry.{_C.RESET}")
            return ""
        return line

    async def run(self) -> None:
        if not self._is_interactive():
            return

        self.running = True
        loop = asyncio.get_event_loop()
        self.attach_stdout()

        # Animated header (blocking in executor so timing is accurate)
        title    = self.cfg.get("display", "title", fallback="MCUB Shell")
        sep_char = self.cfg.get("shell", "separator", fallback="─")
        py       = f"Python {sys.version.split()[0]}"
        await loop.run_in_executor(
            None, _Anim.typewriter_header, title, self.VERSION, py, sep_char
        )

        while self.running:
            try:
                prompt_str, prompt_len = self._prompt_str()
                editor = _LineEditor(
                    prompt_str, prompt_len,
                    self._history, self._last_ok,
                )
                line = await loop.run_in_executor(None, editor.read)
            except KeyboardInterrupt:
                self.output(f"{_C.GREY}  (Ctrl+C — type 'exit' to quit){_C.RESET}")
                continue
            except (EOFError, Exception):
                break

            line = line.strip()
            if not line:
                continue

            # bare ! → enter bash mode
            if line == "!":
                await self._enter_bash_mode()
                continue

            line = self._expand_history(line)
            if not line:
                continue

            # Add to history (skip duplicates)
            max_hist = self.cfg.getint("shell", "history_size", fallback=500)
            if not self._history or self._history[-1] != line:
                self._history.append(line)
                if len(self._history) > max_hist:
                    self._history.pop(0)

            await self._handle(line)

        self.running = False
        self.detach_logging()
        self.detach_stdout()
        self.detach_stderr()

    async def _handle(self, line: str) -> None:
        parts = line.split()
        name  = parts[0].lower()
        args  = parts[1:]

        if name in ("help", "?"):
            self._cmd_help()
            return
        if name in ("clear", "cls"):
            os.system("clear" if os.name != "nt" else "cls")
            self._print_header()
            return
        if name == "history":
            self._cmd_history(args)
            return
        if name == "exit":
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _Anim.goodbye_wave, "Bye!")
            self.running = False
            return
        if name == "cd":
            self._cmd_cd(args)
            return

        mod = _load_command(name)
        if mod is None:
            # Did you mean? — find closest command
            suggestion = self._did_you_mean(name)
            msg = f"{_C.RED}Unknown command '{name}'.{_C.RESET}"
            if suggestion:
                msg += f"  {_C.YELLOW}Did you mean '{suggestion}'?{_C.RESET}"
            else:
                msg += f"  {_C.DIM}Type 'help' for the list.{_C.RESET}"
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _Anim.error_pulse, msg)
            self._last_ok = False
            return

        runner = getattr(mod, "run", None)
        if runner is None:
            self.output(f"{_C.RED}'{name}.py' has no run(shell, args) function.{_C.RESET}")
            self._last_ok = False
            return

        start = time.perf_counter()
        try:
            if asyncio.iscoroutinefunction(runner):
                with _Anim.spinner(name):
                    await runner(self, args)
            else:
                loop = asyncio.get_event_loop()
                with _Anim.spinner(name):
                    await loop.run_in_executor(None, runner, self, args)
            self._last_ok = True
        except SystemExit:
            self._last_ok = True
        except Exception as e:
            self._last_ok = False
            self.output(f"{_C.RED}✖  Error in '{name}': {e}{_C.RESET}")
            self.output(_C.RED + traceback.format_exc().rstrip() + _C.RESET)

        if self._show_time():
            elapsed = time.perf_counter() - start
            if elapsed >= 1.0:
                time_str = f"{elapsed:.2f}s"
            else:
                time_str = f"{elapsed * 1000:.1f}ms"
            col = _C.GREEN if self._last_ok else _C.RED
            sym = "✔" if self._last_ok else "✖"
            self.output(f"{_C.GREY}  {col}{sym}{_C.RESET}{_C.GREY}  done in {time_str}{_C.RESET}")

    async def _enter_bash_mode(self) -> None:
        """Switch to an interactive bash PTY session until the user exits."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _Anim.bash_enter_banner)

        # Temp file: bash writes $PWD on every prompt so we know where it ended up
        pwd_file = tempfile.mktemp(suffix=".mcub_pwd")

        # PS1 that mirrors the shell's look:  ! /path/to/dir ❯
        ps1 = (
            "\\[\\033[95m\\]!\\[\\033[0m\\] "        # magenta !
            "\\[\\033[94m\\]\\w\\[\\033[0m\\] "      # blue cwd
            "\\[\\033[92m\\]❯\\[\\033[0m\\] "        # green ❯
        )
        env = os.environ.copy()
        env["PS1"] = ps1
        env["PROMPT_COMMAND"] = f"echo \"$PWD\" > {pwd_file}"
        env["TERM"] = os.environ.get("TERM", "xterm-256color")

        cwd = self.cwd
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._run_bash_pty, env, cwd, pwd_file)

        # Sync cwd to wherever bash ended up
        try:
            new_pwd = Path(open(pwd_file).read().strip())
            if new_pwd.is_dir():
                self.cwd = new_pwd
                os.chdir(new_pwd)
        except Exception:
            pass
        finally:
            try:
                os.unlink(pwd_file)
            except OSError:
                pass

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _Anim.bash_return_banner)

    def _run_bash_pty(self, env: dict, cwd: "Path", pwd_file: str) -> None:
        """
        Spawn bash in a real pseudo-terminal and bridge stdin ↔ master ↔ stdout.
        Blocking — meant to run in an executor thread.
        """
        stdin_fd  = sys.stdin.fileno()

        # Always write to the real terminal fd, bypassing our _StdoutToShell wrapper
        orig_out  = self._original_stdout or sys.stdout
        stdout_fd = orig_out.fileno()

        def _get_winsize():
            try:
                buf = fcntl.ioctl(stdin_fd, termios.TIOCGWINSZ, b"\x00" * 8)
                rows, cols = struct.unpack("HHHH", buf)[:2]
                return rows, cols
            except Exception:
                return 24, 80

        def _set_pty_winsize(fd, rows, cols):
            try:
                winsize = struct.pack("HHHH", rows, cols, 0, 0)
                fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)
            except Exception:
                pass
        pid, master_fd = pty.fork()

        if pid == 0:
            # Child: become bash
            try:
                os.chdir(cwd)
                os.execvpe("bash", ["bash", "--norc", "--noprofile"], env)
            except Exception:
                os._exit(1)

        # Parent: bridge I/O
        rows, cols = _get_winsize()
        _set_pty_winsize(master_fd, rows, cols)
        last_size  = (rows, cols)

        old_settings = termios.tcgetattr(stdin_fd)
        tty.setraw(stdin_fd)

        try:
            while True:
                # Propagate terminal resize to bash PTY
                cur_size = _get_winsize()
                if cur_size != last_size:
                    _set_pty_winsize(master_fd, *cur_size)
                    last_size = cur_size

                try:
                    r, _, _ = select.select([stdin_fd, master_fd], [], [], 0.05)
                except (ValueError, OSError):
                    break

                # stdin → bash PTY
                if stdin_fd in r:
                    try:
                        data = os.read(stdin_fd, 256)
                        if not data:
                            break
                        os.write(master_fd, data)
                    except OSError:
                        break

                # bash PTY → real terminal stdout  (no line limit)
                if master_fd in r:
                    try:
                        data = os.read(master_fd, 65536)
                        if not data:
                            break
                        os.write(stdout_fd, data)
                    except OSError:
                        break

                # Check if bash already exited
                try:
                    wpid, _ = os.waitpid(pid, os.WNOHANG)
                except ChildProcessError:
                    break
                if wpid != 0:
                    # Drain any remaining output
                    try:
                        while True:
                            r2, _, _ = select.select([master_fd], [], [], 0.05)
                            if not r2:
                                break
                            chunk = os.read(master_fd, 65536)
                            if not chunk:
                                break
                            os.write(stdout_fd, chunk)
                    except OSError:
                        pass
                    break

        finally:
            termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_settings)
            try:
                os.close(master_fd)
            except OSError:
                pass
            # Reap child to avoid zombies
            try:
                os.waitpid(pid, 0)
            except ChildProcessError:
                pass

    def _cmd_cd(self, args: list) -> None:
        old_path = self._short_cwd()
        target = Path(args[0]).expanduser() if args else Path.home()
        if not target.is_absolute():
            target = self.cwd / target
        target = target.resolve()
        if target.is_dir():
            self.cwd = target
            os.chdir(target)
            self._last_ok = True
            new_path = self._short_cwd()
            _Anim.cd_transition(old_path, new_path)
        else:
            self.output(f"{_C.RED}cd: no such directory: {target}{_C.RESET}")
            self._last_ok = False

    def _cmd_help(self) -> None:
        commands = sorted(
            p.stem for p in _BIN_DIR.glob("*.py")
            if not p.stem.startswith("_")
        ) if _BIN_DIR.exists() else []

        cols = _terminal_width()
        sep  = self.cfg.get("shell", "separator", fallback="─") * min(cols - 2, 48)

        out  = f"\n{_C.CYAN}{_C.BOLD}  Built-in commands{_C.RESET}\n"
        builtins_info = [
            ("help",    "show this list"),
            ("clear",   "clear the terminal"),
            ("history", "show / search history   [history <query>]"),
            ("cd",      "change directory        [cd <path>]"),
            ("exit",    "exit the shell"),
        ]
        for cmd, desc in builtins_info:
            out += f"  {_C.GREEN}{cmd:<16}{_C.RESET}{_C.DIM}{desc}{_C.RESET}\n"

        if commands:
            out += f"\n{_C.CYAN}{_C.BOLD}  bin/{_C.RESET}\n"
            for cmd in commands:
                desc = ""
                try:
                    m    = _load_command(cmd)
                    desc = (
                        getattr(m, "DESCRIPTION", "")
                        or (m.__doc__ or "").strip().splitlines()[0]
                    )
                except Exception:
                    pass
                out += f"  {_C.GREEN}{cmd:<16}{_C.RESET}{_C.DIM}{desc}{_C.RESET}\n"
        else:
            out += f"\n{_C.GREY}  (no commands in console/bin/){_C.RESET}\n"

        out += f"\n{_C.GREY}{sep}{_C.RESET}"
        self.output(out)

    def _cmd_history(self, args: list) -> None:
        query = args[0].lower() if args else ""
        entries = [
            (i, cmd) for i, cmd in enumerate(self._history, 1)
            if not query or query in cmd.lower()
        ]
        if not entries:
            self.output(f"{_C.GREY}  No matching history entries.{_C.RESET}")
            return
        out = f"\n{_C.CYAN}{_C.BOLD}  History{' (filtered)' if query else ''}{_C.RESET}\n"
        for i, cmd in entries:
            # Highlight match
            if query:
                hi = cmd.replace(query, f"{_C.YELLOW}{query}{_C.RESET}")
            else:
                hi = cmd
            out += f"  {_C.GREY}{i:>4}.{_C.RESET}  {hi}\n"
        self.output(out)

    @staticmethod
    def _levenshtein(a: str, b: str) -> int:
        if len(a) < len(b):
            a, b = b, a
        row = list(range(len(b) + 1))
        for c1 in a:
            new_row = [row[0] + 1]
            for j, c2 in enumerate(b):
                new_row.append(min(new_row[-1] + 1, row[j + 1] + 1, row[j] + (c1 != c2)))
            row = new_row
        return row[-1]

    def _did_you_mean(self, name: str) -> str:
        candidates = _all_commands()
        best, best_d = "", 999
        for c in candidates:
            d = self._levenshtein(name, c)
            if d < best_d:
                best, best_d = c, d
        # Only suggest if edit distance is small relative to length
        if best_d <= max(2, len(name) // 3):
            return best
        return ""
