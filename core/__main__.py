# author: @Hairpin00
# version: 1.4.0
# description: Entry point

import sys
import os
import threading
import time
import itertools
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def _get_available_cores():
    """Return list of available kernel cores."""
    core_dir = Path(__file__).parent / "kernel"
    if not core_dir.exists():
        return []
    cores = []
    for item in core_dir.iterdir():
        if item.suffix == '.py' and not item.name.startswith('_'):
            cores.append(item.stem)
    return sorted(cores)


_DEFAULT_CORE_FILE = Path(__file__).parent / ".default_core"


def _get_default_core() -> "str | None":
    """Read the saved default core name, or None if not set."""
    if _DEFAULT_CORE_FILE.exists():
        value = _DEFAULT_CORE_FILE.read_text().strip()
        return value or None
    return None


def _set_default_core(core: str) -> None:
    """Persist *core* as the default for future launches."""
    _DEFAULT_CORE_FILE.write_text(core)
    print(f"✓  Default core set to: {core!r}", flush=True)
    print(f"   (saved to -> {_DEFAULT_CORE_FILE})", flush=True)


def _clear_default_core() -> None:
    """Remove the saved default core."""
    if _DEFAULT_CORE_FILE.exists():
        _DEFAULT_CORE_FILE.unlink()
        print("✓  Default core cleared", flush=True)
    else:
        print("  No default core was set", flush=True)


def _parse_args():
    import argparse
    p = argparse.ArgumentParser(description="MCUB Kernel")
    p.add_argument(
        "--no-web",
        dest="no_web",
        action="store_true",
        default=os.environ.get("MCUB_NO_WEB", "0") == "1",
        help="Disable the web panel (env: MCUB_NO_WEB=1). Panel is ON by default.",
    )
    p.add_argument(
        "--proxy-web",
        dest="proxy_web",
        default=os.environ.get("MCUB_PROXY_WEB", ""),
        help="Enable web proxy at specified path (e.g., /web or /). Use env: MCUB_PROXY_WEB=/web",
    )
    p.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("MCUB_PORT", 8080)),
        help="Web panel port (default: 8080, env: MCUB_PORT)",
    )
    p.add_argument(
        "--host",
        default=os.environ.get("MCUB_HOST", "127.0.0.1"),
        help="Web panel host (default: 127.0.0.1, env: MCUB_HOST)",
    )
    p.add_argument(
        "--core",
        dest="core",
        default=None,
        help="Kernel core to use for this launch (e.g., standard, zen, microkernel).",
    )
    p.add_argument(
        "--set-default-core",
        dest="set_default_core",
        metavar="CORE",
        default=None,
        help="Save CORE as the default for future launches, then exit.",
    )
    p.add_argument(
        "--clear-default-core",
        dest="clear_default_core",
        action="store_true",
        default=False,
        help="Remove the saved default core, then exit.",
    )
    return p.parse_args()


async def _run_setup_wizard(host: str, port: int) -> None:
    import asyncio
    from aiohttp import web
    from core.web.app import create_app

    done = asyncio.Event()
    app  = create_app(kernel=None, setup_event=done)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()

    print(f"  🌐  Setup wizard  →  http://{host}:{port}/", flush=True)
    try:
        await done.wait()
    finally:
        await runner.cleanup()

    print("\nStarting kernel…\n", flush=True)


def _patch_kernel(kernel, *, web_enabled: bool, host: str, port: int) -> None:
    import asyncio as _asyncio

    def _run_panel_patched():
        if not web_enabled:
            kernel.logger.debug("Web panel disabled (--no-web)")
            return
        try:
            from core.web.app import start_web_panel
            _asyncio.create_task(start_web_panel(kernel, host, port))
            kernel.logger.info(f"Web panel → http://{host}:{port}")
        except Exception as exc:
            kernel.logger.error(f"Web panel start failed: {exc}")

    kernel.run_panel = _run_panel_patched


async def _main() -> None:
    import asyncio
    args        = _parse_args()
    web_enabled = not args.no_web

    available_cores = _get_available_cores()

    if args.clear_default_core:
        _clear_default_core()
        sys.exit(0)

    if args.set_default_core:
        core = args.set_default_core
        if not available_cores:
            print("Error: No kernel cores found!", flush=True)
            sys.exit(1)
        if core not in available_cores:
            print(f"Error: Core '{core}' not found.", flush=True)
            print(f"Available: {', '.join(available_cores)}", flush=True)
            sys.exit(1)
        _set_default_core(core)
        sys.exit(0)

    if not available_cores:
        print("Error: No kernel cores found!", flush=True)
        sys.exit(1)

    # priority: --core flag  >  saved default  >  single core  >  interactive
    selected_core = args.core or _get_default_core()

    if selected_core is None:
        if len(available_cores) == 1:
            selected_core = available_cores[0]
        else:
            saved  = _get_default_core()
            hint   = f" [{saved}]" if saved else f" [{available_cores[0]}]"
            print(f"Available cores: {', '.join(available_cores)}", flush=True)
            print("Tip: --set-default-core <n> to skip this prompt next time", flush=True)
            answer = input(f"Select core{hint}: ").strip()
            selected_core = answer or saved or available_cores[0]

    if selected_core not in available_cores:
        print(f"Error: Kernel: '{selected_core}' not found!", flush=True)
        print(f"Available: {', '.join(available_cores)}", flush=True)
        sys.exit(1)

    print(f"=> Kernel Load: kernel.{selected_core}()", flush=True)

    if web_enabled and not os.path.exists("config.json"):
        await _run_setup_wizard(args.host, args.port)

    from importlib import import_module
    Kernel = import_module(f"core.kernel.{selected_core}").Kernel

    kernel = Kernel()
    kernel.CORE_NAME = selected_core
    _patch_kernel(kernel, web_enabled=web_enabled, host=args.host, port=args.port)
    await kernel.run()


if __name__ == "__main__":

    import asyncio

    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        print("\n-> exit kernel…", flush=True)
        sys.exit(0)
    except Exception as exc:
        print(f'\nFatal: "{exc}" [X]', flush=True)
        sys.exit(1)
