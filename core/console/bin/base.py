"""
Shell command: base
MCUB Package Manager — installs, updates and removes shell packages.

Usage:
  base                              error: no operation specified
  base -h | --help | help           show full help
  base install  <pkg> [--force]     install a package
  base update   <pkg>               update an installed package
  base uninstall <pkg>              remove a package
  base search   <query>             search repository for packages
  base list     [--available]       list installed (+ optionally available) packages
  base show     <pkg>               show detailed package information
  base version                      print package manager version
"""

DESCRIPTION = "MCUB package manager"

PM_VERSION = "1.0.0"

# ── Colors (inline so bin has no dep on base.display at import) ──
_R   = "\033[0m"
_C   = "\033[96m"    # cyan
_G   = "\033[92m"    # green
_Y   = "\033[93m"    # yellow
_RED = "\033[91m"    # red
_GR  = "\033[90m"    # grey
_B   = "\033[1m"     # bold
_D   = "\033[2m"     # dim

_LOGO = f"""
{_C}{_B}  ██████╗  █████╗ ███████╗███████╗{_R}
{_C}{_B}  ██╔══██╗██╔══██╗██╔════╝██╔════╝{_R}
{_C}{_B}  ██████╔╝███████║███████╗█████╗  {_R}
{_C}{_B}  ██╔══██╗██╔══██║╚════██║██╔══╝  {_R}
{_C}{_B}  ██████╔╝██║  ██║███████║███████╗{_R}
{_C}{_B}  ╚═════╝ ╚═╝  ╚═╝╚══════╝╚══════╝{_R}
  {_GR}MCUB Package Manager  v{PM_VERSION}{_R}
"""

_HELP = f"""{_LOGO}
{_B}Usage:{_R}
  {_C}base{_R} {_Y}<operation>{_R} [package] [options]

{_B}Operations:{_R}
  {_G}install{_R}   {_Y}<pkg>{_R} [{_GR}--force{_R}]   Install a package
  {_G}update{_R}    {_Y}<pkg>{_R}              Update an installed package to latest
  {_G}uninstall{_R} {_Y}<pkg>{_R}              Uninstall a package
  {_G}search{_R}    {_Y}<query>{_R}            Search packages in the repository
  {_G}list{_R}      [{_GR}--available{_R}]     List installed packages
  {_G}show{_R}      {_Y}<pkg>{_R}              Show detailed package info
  {_G}version{_R}                    Print package manager version
"""



async def run(shell, args: list) -> None:
    out = shell.output

    # ── No args
    if not args:
        out(
            f"\n  {_RED}✖{_R}  No operation specified.\n"
            f"  {_GR}Run{_R} {_C}base -h{_R} {_GR}for help.{_R}\n"
        )
        return

    op = args[0].lower()

    if op in ("-h", "--help", "help"):
        out(_HELP)
        return

    if op == "version":
        out(f"\n  {_C}{_B}base{_R}  package manager  v{PM_VERSION}\n")
        return

    try:
        from ..base.manager import PackageManager
    except ImportError:
        import importlib.util
        import pathlib
        
        manager_path = pathlib.Path(__file__).resolve().parent.parent / "base" / "manager.py"
        spec = importlib.util.spec_from_file_location("console.base.manager", manager_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        PackageManager = mod.PackageManager

    pm = PackageManager()

    # ── Dispatch
    if op in ("install", "i"):
        if len(args) < 2:
            _usage_err(out, "install", "base install <package>  [--force]")
            return
        pkg   = args[1]
        force = "--force" in args or "-f" in args
        await pm.install(pkg, output=out, force=force)

    elif op in ("update", "upgrade", "up"):
        if len(args) < 2:
            _usage_err(out, "update", "base update <package>")
            return
        await pm.update(args[1], output=out)

    elif op in ("uninstall", "remove", "rm"):
        if len(args) < 2:
            _usage_err(out, "uninstall", "base uninstall <package>")
            return
        pkg = args[1]
        await pm.uninstall(pkg, output=out)

    elif op in ("search", "s", "find"):
        if len(args) < 2:
            _usage_err(out, "search", "base search <query>")
            return
        await pm.search(args[1], output=out)

    elif op in ("list", "ls", "l"):
        avail = "--available" in args or "-a" in args
        await pm.list_packages(output=out, show_available=avail)

    elif op in ("show", "info"):
        if len(args) < 2:
            _usage_err(out, "show", "base show <package>")
            return
        await pm.show(args[1], output=out)

    else:
        out(
            f"\n  {_RED}✖{_R}  Unknown operation: {_Y}{op}{_R}\n"
            f"  {_GR}Run{_R} {_C}base -h{_R} {_GR}to see available operations.{_R}\n"
        )


def _usage_err(out, op: str, usage: str) -> None:
    out(
        f"\n  {_RED}✖{_R}  Missing argument for '{_Y}{op}{_R}'.\n"
        f"  {_GR}Usage:{_R}  {_C}{usage}{_R}\n"
    )


async def _confirm(shell, prompt: str) -> bool:
    """
    Ask a yes/no question using the shell's readline or a simple fallback.
    Returns True if the user typed 'y' or 'Y'.
    """
    import asyncio
    loop = asyncio.get_event_loop()
    try:
        # Use shell's line editor if available
        if hasattr(shell, "_history"):
            from ..shell import _LineEditor
            # Plain prompt without ANSI codes
            plain_prompt = f"  {prompt}"
            editor = _LineEditor(
                plain_prompt,
                len(plain_prompt),
                [],
            )
            ans = await loop.run_in_executor(None, editor.read)
            return ans.strip().lower().startswith("y")
    except Exception:
        pass
    # Fallback: just return True (non-interactive)
    shell.output(f"\033[90m  (auto-confirmed)\033[0m\n")
    return True
