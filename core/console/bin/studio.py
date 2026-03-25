"""
Shell command: studio
Launches the MCUB Studio — interactive TUI module manager.
"""

DESCRIPTION = "Interactive TUI module studio (vim-style)"

HELP = """
studio — MCUB Module Studio

A full-screen TUI for creating, editing, loading,
reloading, updating and deleting modules.

Usage:
  studio

Keybindings (inside Studio):
  j / k / ↑ / ↓     Navigate module list
  Enter / →           Open module detail
  ← / Esc / h        Back to list
  n                   Create new module (opens editor)
  e                   Edit selected module source
  r                   Reload selected module
  u                   Update from repository
  D                   Delete & unload module
  /                   Search repository for a module
  R                   Refresh module list
  ?                   Show help in the log panel
  q                   Quit Studio

Editor keybindings:
  Ctrl+S              Save & load module
  Ctrl+Z              Undo last change
  Tab                 Insert 4 spaces
  Ctrl+K / Ctrl+U     Kill to end / start of line
  Ctrl+Q / ESC        Cancel and exit editor
"""


async def run(shell, args) -> None:
    if args and args[0] in ("-h", "--help", "help"):
        shell.output(HELP)
        return

    if not hasattr(shell, "kernel") or shell.kernel is None:
        shell.output(
            "\033[91mStudio requires a running kernel (shell.kernel is None).\033[0m"
        )
        return

    try:
        # Import lazily so curses is not imported at shell startup
        from ..packages.studio.src.tui import Studio
    except ImportError as e:
        shell.output(f"\033[91mCould not import Studio: {e}\033[0m")
        return

    studio = Studio(shell.kernel)
    shell.output("\033[90m  Launching Studio...\033[0m")

    try:
        await studio.start()
    except Exception as e:
        shell.output(f"\033[91mStudio crashed: {e}\033[0m")
        import traceback

        shell.output("\033[91m" + traceback.format_exc() + "\033[0m")
