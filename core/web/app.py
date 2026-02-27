import os

import aiohttp_jinja2
import jinja2
from aiohttp import web

from .routes import setup_routes
from .plugin_manager import PluginManager


def create_app(kernel=None, setup_event=None) -> web.Application:
    """
    Create and configure the aiohttp web application.

    Args:
        kernel:      Kernel instance (None during the setup wizard).
        setup_event: asyncio.Event that gets set when the wizard completes.
    """
    app = web.Application()
    app["kernel"]      = kernel
    app["setup_event"] = setup_event

    aiohttp_jinja2.setup(
        app,
        loader=jinja2.FileSystemLoader("core/web/templates"),
    )

    setup_routes(app)

    plugin_manager = PluginManager(app, kernel)
    if kernel is not None:
        plugin_manager.load_plugins()
    app["plugin_manager"] = plugin_manager

    return app


async def start_web_panel(kernel, host: str | None = None, port: int | None = None):
    """Start the web panel as a background coroutine."""
    host = host or os.environ.get("MCUB_HOST", "0.0.0.0")
    port = int(port or os.environ.get("MCUB_PORT", 8080))

    app    = create_app(kernel)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    kernel.logger.info(f"Web panel started at http://{host}:{port}")
    return runner
