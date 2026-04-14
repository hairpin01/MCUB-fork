# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

"""
Web panel package for MCUB kernel.
Provides a simple asynchronous HTTP server with basic kernel info.
"""

from .app import create_app
from .plugin_manager import PluginManager
from .routes import setup_routes

__all__ = ["PluginManager", "create_app", "setup_routes"]
