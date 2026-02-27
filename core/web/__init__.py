"""
Web panel package for MCUB kernel.
Provides a simple asynchronous HTTP server with basic kernel info.
"""

from .app import create_app
from .routes import setup_routes
from .plugin_manager import PluginManager

__all__ = ["create_app", "setup_routes", "PluginManager"]
