from __future__ import annotations
import os
import logging

import aiohttp_jinja2
import jinja2
from aiohttp import web

from .routes import setup_routes
from .plugin_manager import PluginManager
from .auth import AuthMiddleware

logger = logging.getLogger("mcub.web.app")


def create_app(kernel=None, setup_event=None) -> web.Application:
    """
    Create and configure the aiohttp web application.

    Args:
        kernel:      Kernel instance (None during the setup wizard).
        setup_event: asyncio.Event that gets set when the wizard completes.
    """
    logger.debug("[Web] create_app start")
    app = web.Application()
    app["kernel"] = kernel
    app["setup_event"] = setup_event
    logger.debug(
        "Creating web app kernel_present=%s setup_event_present=%s",
        kernel is not None,
        setup_event is not None,
    )

    aiohttp_jinja2.setup(
        app,
        loader=jinja2.FileSystemLoader("core/web/templates"),
    )

    logger.debug("[Web] Setting up routes")
    setup_routes(app)

    logger.debug("[Web] Creating plugin manager")
    plugin_manager = PluginManager(app, kernel)
    if kernel is not None:
        logger.debug("Loading web plugins for configured kernel")
        plugin_manager.load_plugins()
    app["plugin_manager"] = plugin_manager

    logger.debug("[Web] Setting up auth middleware")
    auth_middleware = AuthMiddleware(app)
    app["auth_middleware"] = auth_middleware
    logger.debug(
        "Web app ready plugins=%s auth_enabled=%s",
        plugin_manager.plugins,
        auth_middleware.auth_enabled,
    )

    return app


async def start_web_panel(kernel, host: str | None = None, port: int | None = None):
    """Start the web panel as a background coroutine."""
    host = host or os.environ.get("MCUB_HOST", "0.0.0.0")
    port = int(port or os.environ.get("MCUB_PORT", 8080))
    kernel.logger.debug("Starting web panel host=%s port=%s", host, port)

    app = create_app(kernel)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    kernel.logger.info(f"Web panel started at http://{host}:{port}")
    return runner
