import time
import aiohttp_jinja2
from aiohttp import web


def setup_routes(app):
    """Register all core web routes."""
    app.router.add_get("/", index)
    app.router.add_get("/status", status)
    app.router.add_static("/static", path="core/web/static", name="static")


async def index(request):
    """Main page – shows basic kernel information."""
    kernel = request.app.get("kernel")
    context = {
        "version": getattr(kernel, "VERSION", "N/A"),
        "prefix": getattr(kernel, "custom_prefix", "."),
        "modules_count": len(getattr(kernel, "loaded_modules", {})),
        "uptime": _format_uptime(kernel.start_time) if kernel and hasattr(kernel, "start_time") else "N/A",
        "error_load": getattr(kernel, "error_load_modules", 0),
    }
    return aiohttp_jinja2.render_template("index.html", request, context)


async def status(request):
    """Simple JSON endpoint with kernel status."""
    kernel = request.app.get("kernel")
    if kernel is None:
        return web.json_response({"error": "Kernel not available"}, status=503)

    data = {
        "version": kernel.VERSION,
        "prefix": kernel.custom_prefix,
        "modules": list(kernel.loaded_modules.keys()),
        "commands": list(kernel.command_handlers.keys()),
        "uptime": time.time() - kernel.start_time,
        "error_load_modules": kernel.error_load_modules,
    }
    return web.json_response(data)


def _format_uptime(seconds):
    """Convert seconds to human readable string."""
    if not seconds:
        return "N/A"
    delta = time.time() - seconds
    hours, remainder = divmod(int(delta), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"
