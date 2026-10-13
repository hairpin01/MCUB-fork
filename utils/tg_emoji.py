# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01
# Author: рич белуга (@rich_beluga)

"""Downgrade ``<tg-emoji>`` tags for accounts without Telegram Premium.

Premium (custom) emoji sent as ``<tg-emoji emoji-id="...">`` do not render
on accounts without Telegram Premium. Rewriting them as
``<a href="tg://emoji?id=...">`` links makes the emoji visible everywhere,
since Telegram clients resolve such links into the custom emoji glyph.

Example:
    ``<tg-emoji emoji-id="5346022209389372742">🤔</tg-emoji>`` becomes
    ``<a href="tg://emoji?id=5346022209389372742">🤔</a>``.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Matches ``<tg-emoji emoji-id="123456">...</tg-emoji>`` (single or double
# quotes, arbitrary whitespace, case-insensitive tag/attribute names).
_TG_EMOJI_PATTERN = re.compile(
    r"<tg-emoji\s+emoji-id\s*=\s*[\"'](\d+)[\"']\s*>(.*?)</tg-emoji\s*>",
    re.IGNORECASE | re.DOTALL,
)


def tg_emoji_to_link(text: Any) -> str:
    """Rewrite every ``<tg-emoji>`` tag in *text* as a ``tg://emoji`` link.

    Tags whose ``emoji-id`` is not numeric are left untouched. Non-string
    input is returned unchanged.
    """
    if not isinstance(text, str) or "<tg-emoji" not in text.lower():
        return text

    def _replace(match: re.Match) -> str:
        emoji_id, inner = match.group(1), match.group(2)
        return f'<a href="tg://emoji?id={emoji_id}">{inner}</a>'

    return _TG_EMOJI_PATTERN.sub(_replace, text)


def has_tg_emoji(text: Any) -> bool:
    """Return True if *text* contains at least one ``<tg-emoji>`` tag."""
    return isinstance(text, str) and bool(_TG_EMOJI_PATTERN.search(text))


async def account_has_premium(client: Any) -> bool:
    """Return True if the *user* account behind *client* has Telegram Premium.

    Any failure (no client, ``get_me`` error, unknown shape) resolves to
    True so callers keep the original ``<tg-emoji>`` markup instead of
    rewriting messages based on a guess.
    """
    if client is None:
        return True
    get_me = getattr(client, "get_me", None)
    if not callable(get_me):
        return True
    try:
        me = await get_me()
    except Exception as e:
        logger.debug("tg_emoji: get_me() failed, assuming premium: %s", e)
        return True
    return bool(getattr(me, "premium", False))


async def downgrade_tg_emoji(text: str, client: Any) -> str:
    """Convert ``<tg-emoji>`` tags to links unless the account has Premium."""
    if not has_tg_emoji(text):
        return text
    if await account_has_premium(client):
        return text
    return tg_emoji_to_link(text)
