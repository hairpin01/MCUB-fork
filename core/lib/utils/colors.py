# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01
# author: @Hairpin00
# version: 2.1.0
# description: Terminal color codes


class Colors:

    RESET = "\033[0m"

    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    PURPLE = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    BRIGHT_BLACK = "\033[90m"  # aka dark grey
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_PURPLE = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_PURPLE = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"

    BG_BRIGHT_BLACK = "\033[100m"
    BG_BRIGHT_RED = "\033[101m"
    BG_BRIGHT_GREEN = "\033[102m"
    BG_BRIGHT_YELLOW = "\033[103m"
    BG_BRIGHT_BLUE = "\033[104m"
    BG_BRIGHT_PURPLE = "\033[105m"
    BG_BRIGHT_CYAN = "\033[106m"
    BG_BRIGHT_WHITE = "\033[107m"

    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    BLINK = "\033[5m"
    BLINK_FAST = "\033[6m"
    REVERSE = "\033[7m"  # swap fg/bg
    HIDDEN = "\033[8m"  # invisible text
    STRIKETHROUGH = "\033[9m"
    DOUBLE_UNDERLINE = "\033[21m"
    OVERLINE = "\033[53m"

    RESET_BOLD = "\033[22m"
    RESET_DIM = "\033[22m"
    RESET_ITALIC = "\033[23m"
    RESET_UNDERLINE = "\033[24m"
    RESET_BLINK = "\033[25m"
    RESET_REVERSE = "\033[27m"
    RESET_HIDDEN = "\033[28m"
    RESET_STRIKETHROUGH = "\033[29m"
    RESET_FG = "\033[39m"
    RESET_BG = "\033[49m"

    SUCCESS = "\033[92m"  # bright green
    ERROR = "\033[91m"  # bright red
    WARNING = "\033[93m"  # bright yellow
    INFO = "\033[96m"  # bright cyan
    DEBUG = "\033[95m"  # bright purple
    MUTED = "\033[90m"  # dark grey

    GREY = "\033[90m"
    GRAY = "\033[90m"
    PINK = "\033[95m"
    MAGENTA = "\033[35m"
    BRIGHT_MAGENTA = "\033[95m"
    ORANGE = "\033[38;5;214m"  # 256-color orange
    LIME = "\033[38;5;154m"  # 256-color lime
    TEAL = "\033[38;5;30m"  # 256-color teal
    MAROON = "\033[38;5;88m"  # 256-color maroon
    NAVY = "\033[38;5;17m"  # 256-color navy
    GOLD = "\033[38;5;220m"  # 256-color gold
    VIOLET = "\033[38;5;135m"  # 256-color violet
    INDIGO = "\033[38;5;54m"  # 256-color indigo
    BROWN = "\033[38;5;130m"  # 256-color brown
    SILVER = "\033[38;5;250m"  # 256-color silver

    @staticmethod
    def rgb(r: int, g: int, b: int) -> str:
        """Return a 24-bit (true-color) foreground escape for the given RGB values."""
        return f"\033[38;2;{r};{g};{b}m"

    @staticmethod
    def rgb_bg(r: int, g: int, b: int) -> str:
        """Return a 24-bit (true-color) background escape for the given RGB values."""
        return f"\033[48;2;{r};{g};{b}m"

    @staticmethod
    def color256(n: int) -> str:
        """Return a 256-color foreground escape (0-255)."""
        return f"\033[38;5;{n}m"

    @staticmethod
    def color256_bg(n: int) -> str:
        """Return a 256-color background escape (0-255)."""
        return f"\033[48;5;{n}m"

    @staticmethod
    def hex(code: str) -> str:
        """Return a 24-bit foreground escape from a hex color string like '#ff8800' or 'ff8800'."""
        code = code.lstrip("#")
        r, g, b = int(code[0:2], 16), int(code[2:4], 16), int(code[4:6], 16)
        return f"\033[38;2;{r};{g};{b}m"

    @staticmethod
    def hex_bg(code: str) -> str:
        """Return a 24-bit background escape from a hex color string."""
        code = code.lstrip("#")
        r, g, b = int(code[0:2], 16), int(code[2:4], 16), int(code[4:6], 16)
        return f"\033[48;2;{r};{g};{b}m"

    @classmethod
    def paint(cls, text: str, *codes: str) -> str:
        """Wrap *text* with one or more escape codes and auto-reset at the end.

        Example::

            print(Colors.paint("hello", Colors.BOLD, Colors.BRIGHT_GREEN))
        """
        return "".join(codes) + text + cls.RESET

    @classmethod
    def strip(cls, text: str) -> str:
        """Remove all ANSI escape sequences from *text*."""
        import re

        return re.sub(r"\033\[[0-9;]*m", "", text)

    @staticmethod
    def _lerp_rgb(
        r1: int,
        g1: int,
        b1: int,
        r2: int,
        g2: int,
        b2: int,
        t: float,
    ) -> tuple[int, int, int]:
        """Linearly interpolate between two RGB colours at position *t* ∈ [0, 1]."""
        return (
            round(r1 + (r2 - r1) * t),
            round(g1 + (g2 - g1) * t),
            round(b1 + (b2 - b1) * t),
        )

    @classmethod
    def gradient(
        cls,
        text: str,
        start: tuple[int, int, int],
        end: tuple[int, int, int],
        *,
        bg: bool = False,
        bold: bool = False,
    ) -> str:
        """Colour each character of *text* along a linear RGB gradient.

        Args:
            text:  The string to colour (newlines are passed through unstyled).
            start: (r, g, b) of the first character.
            end:   (r, g, b) of the last character.
            bg:    Apply the gradient to the background instead of the foreground.
            bold:  Wrap every character in bold as well.

        Example::

            print(Colors.gradient("Hello, world!", (255, 0, 0), (0, 0, 255)))
        """
        chars = list(text)
        visible = [c for c in chars if c != "\n"]
        n = max(len(visible) - 1, 1)
        style = cls.BOLD if bold else ""
        result: list[str] = []
        idx = 0
        for ch in chars:
            if ch == "\n":
                result.append(cls.RESET + "\n")
                continue
            t = idx / n
            r, g, b = cls._lerp_rgb(*start, *end, t)
            esc = cls.rgb_bg(r, g, b) if bg else cls.rgb(r, g, b)
            result.append(style + esc + ch)
            idx += 1
        return "".join(result) + cls.RESET

    @classmethod
    def gradient_multicolor(
        cls,
        text: str,
        stops: list[tuple[int, int, int]],
        *,
        bg: bool = False,
        bold: bool = False,
    ) -> str:
        """Colour each character through an arbitrary list of RGB colour stops.

        Args:
            text:  The string to colour.
            stops: At least two (r, g, b) tuples defining the colour stops.
            bg:    Apply to background instead of foreground.
            bold:  Wrap every character in bold.

        Example::

            print(Colors.gradient_multicolor(
                "RGB MAGIC",
                [(255, 0, 0), (0, 255, 0), (0, 0, 255)],
            ))
        """
        if len(stops) < 2:
            raise ValueError("gradient_multicolor requires at least 2 colour stops")
        chars = list(text)
        visible = [c for c in chars if c != "\n"]
        n = max(len(visible) - 1, 1)
        segments = len(stops) - 1
        style = cls.BOLD if bold else ""
        result: list[str] = []
        idx = 0
        for ch in chars:
            if ch == "\n":
                result.append(cls.RESET + "\n")
                continue
            t = idx / n  # 0.0 → 1.0 across full text
            seg = min(int(t * segments), segments - 1)
            local_t = t * segments - seg  # 0.0 → 1.0 within this segment
            r, g, b = cls._lerp_rgb(*stops[seg], *stops[seg + 1], local_t)
            esc = cls.rgb_bg(r, g, b) if bg else cls.rgb(r, g, b)
            result.append(style + esc + ch)
            idx += 1
        return "".join(result) + cls.RESET

    @classmethod
    def gradient_line(
        cls,
        text: str,
        start: tuple[int, int, int],
        end: tuple[int, int, int],
        width: int | None = None,
        *,
        bg: bool = True,
        char: str = " ",
    ) -> str:
        """Render a solid horizontal colour bar (useful for decorative separators).

        Args:
            text:  Label printed in the centre of the bar (empty = pure colour bar).
            start: Left edge colour.
            end:   Right edge colour.
            width: Total width in characters (defaults to ``len(text)`` or 40).
            bg:    Fill the background (True) or the foreground (False).
            char:  Fill character (default space).

        Example::

            print(Colors.gradient_line("", (255, 80, 0), (80, 0, 255), width=60))
        """
        if width is None:
            width = max(len(text), 40)
        bar = (char * width) if not text else text.center(width)
        return cls.gradient(bar, start, end, bg=bg, bold=bool(text))

    @classmethod
    def fire(cls, text: str, *, bold: bool = True) -> str:
        """🔥  Black → red → orange → yellow gradient."""
        return cls.gradient_multicolor(
            text,
            [(20, 0, 0), (180, 0, 0), (255, 120, 0), (255, 220, 50)],
            bold=bold,
        )

    @classmethod
    def ocean(cls, text: str, *, bold: bool = False) -> str:
        """🌊  Deep navy → teal → aqua → white-cyan gradient."""
        return cls.gradient_multicolor(
            text,
            [(0, 10, 80), (0, 80, 160), (0, 180, 200), (180, 240, 255)],
            bold=bold,
        )

    @classmethod
    def forest(cls, text: str, *, bold: bool = False) -> str:
        """🌿  Dark green → lime → yellow-green gradient."""
        return cls.gradient_multicolor(
            text,
            [(0, 60, 10), (0, 160, 40), (80, 220, 30), (200, 255, 80)],
            bold=bold,
        )

    @classmethod
    def sunset(cls, text: str, *, bold: bool = False) -> str:
        """🌅  Purple → magenta → orange → yellow gradient."""
        return cls.gradient_multicolor(
            text,
            [(80, 0, 120), (200, 0, 160), (255, 100, 20), (255, 210, 80)],
            bold=bold,
        )

    @classmethod
    def aurora(cls, text: str, *, bold: bool = False) -> str:
        """🌌  Green → cyan → purple → pink gradient (northern lights)."""
        return cls.gradient_multicolor(
            text,
            [(0, 200, 100), (0, 220, 200), (100, 80, 220), (220, 80, 180)],
            bold=bold,
        )

    @classmethod
    def neon(cls, text: str, *, bold: bool = True) -> str:
        """⚡  Hot pink → electric blue gradient."""
        return cls.gradient(text, (255, 0, 128), (0, 128, 255), bold=bold)

    @classmethod
    def candy(cls, text: str, *, bold: bool = False) -> str:
        """🍭  Pink → lavender → baby blue gradient."""
        return cls.gradient_multicolor(
            text,
            [(255, 100, 180), (200, 130, 255), (100, 180, 255)],
            bold=bold,
        )

    @classmethod
    def gold_gradient(cls, text: str, *, bold: bool = True) -> str:
        """✨  Dark gold → bright gold → white shimmer."""
        return cls.gradient_multicolor(
            text,
            [(120, 80, 0), (220, 170, 0), (255, 230, 100), (255, 255, 200)],
            bold=bold,
        )

    @classmethod
    def ice(cls, text: str, *, bold: bool = False) -> str:
        """🧊  White → light blue → deep blue gradient."""
        return cls.gradient_multicolor(
            text,
            [(220, 240, 255), (120, 200, 255), (40, 120, 220), (10, 40, 140)],
            bold=bold,
        )

    @classmethod
    def lava(cls, text: str, *, bold: bool = True) -> str:
        """🌋  Dark red → bright red → yellow-white core."""
        return cls.gradient_multicolor(
            text,
            [(60, 0, 0), (200, 20, 0), (255, 80, 0), (255, 255, 180)],
            bold=bold,
        )

    @classmethod
    def matrix(cls, text: str, *, bold: bool = False) -> str:
        """💻  Black → dark green → bright green gradient."""
        return cls.gradient(text, (0, 20, 0), (0, 255, 70), bold=bold)

    @classmethod
    def rose(cls, text: str, *, bold: bool = False) -> str:
        """🌹  Deep red → rose → blush pink gradient."""
        return cls.gradient_multicolor(
            text,
            [(120, 0, 30), (210, 30, 80), (255, 130, 160)],
            bold=bold,
        )

    @classmethod
    def rainbow(cls, text: str, *, bold: bool = False) -> str:
        """🌈  Full spectrum: red → orange → yellow → green → blue → violet."""
        return cls.gradient_multicolor(
            text,
            [
                (255, 0, 0),
                (255, 127, 0),
                (255, 255, 0),
                (0, 200, 0),
                (0, 0, 255),
                (139, 0, 255),
            ],
            bold=bold,
        )

    @classmethod
    def print_gradients(
        cls, sample: str = "The quick brown fox jumps over the lazy dog"
    ) -> None:
        """Print all built-in named gradients to the terminal for preview."""
        gradients = [
            ("fire", cls.fire),
            ("ocean", cls.ocean),
            ("forest", cls.forest),
            ("sunset", cls.sunset),
            ("aurora", cls.aurora),
            ("neon", cls.neon),
            ("candy", cls.candy),
            ("gold_gradient", cls.gold_gradient),
            ("ice", cls.ice),
            ("lava", cls.lava),
            ("matrix", cls.matrix),
            ("rose", cls.rose),
            ("rainbow", cls.rainbow),
        ]
        for name, fn in gradients:
            label = cls.paint(f"  {name:<16}", cls.BOLD, cls.WHITE)
            print(f"{label} {fn(sample)}")

    @classmethod
    def print_palette(cls) -> None:
        """Pretty-print all named color constants to the terminal (for debugging)."""
        import inspect

        for name, value in inspect.getmembers(cls):
            if name.startswith("_") or callable(value):
                continue
            if not isinstance(value, str) or not value.startswith("\033"):
                continue
            print(f"{value}{name:<26}{cls.RESET}  {repr(value)}")
