# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

"""
MCUB type protocols — structural types for Kernel, Event, Client, Message.

Use these instead of ``Any`` in public and internal APIs::

    from core.lib.types import Kernel, Event

    def my_handler(k: Kernel, event: Event) -> None: ...
"""

from __future__ import annotations

from core.lib.types.client import Client
from core.lib.types.event import Event
from core.lib.types.kernel import Kernel
from core.lib.types.message import Message
from core.lib.types.register import Register

__all__ = [
    "Client",
    "Event",
    "Kernel",
    "Message",
    "Register",
]
