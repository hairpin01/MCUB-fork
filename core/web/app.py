import aiohttp_jinja2
import jinja2
from aiohttp import web

from .routes import setup_routes
from .plugin_manager import PluginManager


def create_app(kernel=None) -> web.Application:
    """
    Create and configure the aiohttp web application.
    Optionally accepts a kernel instance to expose internal data.
    """
    app = web.Application()
    app["kernel"] = kernel  # store reference to kernel for handlers

    # Setup Jinja2 templates (main templates folder)
    aiohttp_jinja2.setup(
        app,
        loader=jinja2.FileSystemLoader("core/web/templates")
    )

    # Register core routes
    setup_routes(app)

    # Initialize plugin manager and load plugins
    plugin_manager = PluginManager(app, kernel)
    plugin_manager.load_plugins()
    app["plugin_manager"] = plugin_manager

    return app


async def start_web_panel(kernel, host="127.0.0.1", port=8080):
    """
    Convenience function to start the web panel as a background task.
    """
    app = create_app(kernel)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    kernel.logger.info(f"Web panel started at http://{host}:{port}")
    return runner
