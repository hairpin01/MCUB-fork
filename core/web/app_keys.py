# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

from __future__ import annotations

import asyncio
from typing import Any

from aiohttp import web

KERNEL = web.AppKey("mcub.kernel", Any)
SETUP_EVENT = web.AppKey("mcub.setup_event", asyncio.Event | None)
SETUP_MODE = web.AppKey("mcub.setup_mode", bool)
SETUP_STATE = web.AppKey("mcub.setup_state", dict[str, Any])
PLUGIN_MANAGER = web.AppKey("mcub.plugin_manager", Any)
AUTH_MIDDLEWARE = web.AppKey("mcub.auth_middleware", Any)
API_EXTENDER_PREFIX = web.AppKey("mcub.api_extender_prefix", str)
