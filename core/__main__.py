# author: @Hairpin00
# version: 1.3.0
# description: Entry point — auto-deps, --no-web flag, --port / --host

import sys
import os
import threading
import time
import itertools
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

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

    print("\nstarting kernel…\n", flush=True)

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
    args       = _parse_args()
    web_enabled = not args.no_web

    if web_enabled and not os.path.exists("config.json"):
        await _run_setup_wizard(args.host, args.port)

    from core.kernel import Kernel

    kernel = Kernel()
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
