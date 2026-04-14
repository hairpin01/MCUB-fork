# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

"""Tests for inline bot provisioning flow."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from core_inline.bot import BotProvisionResult, InlineBot


@pytest.mark.asyncio
async def test_provision_manual_success() -> None:
    """Manual mode should persist validated token and username."""

    kernel = MagicMock()
    kernel.config = {}
    kernel.CONFIG_FILE = "config.json"
    kernel.logger = MagicMock()

    inline_bot = InlineBot(kernel)
    inline_bot._get_bot_identity = AsyncMock(  # type: ignore[method-assign]
        return_value=BotProvisionResult(
            success=True,
            token="123:token",
            username="mcub_test_bot",
        )
    )
    inline_bot._write_config_atomic = MagicMock()  # type: ignore[method-assign]

    result = await inline_bot.provision_bot(
        mode="manual",
        token="123:token",
        username="mcub_test_bot",
        configure=False,
        persist=True,
    )

    assert result.success is True
    assert inline_bot.token == "123:token"
    assert inline_bot.username == "mcub_test_bot"
    inline_bot._write_config_atomic.assert_called_once()


@pytest.mark.asyncio
async def test_provision_config_without_token() -> None:
    """Config mode should fail when token is missing."""

    kernel = MagicMock()
    kernel.config = {"inline_bot_token": None, "inline_bot_username": None}
    kernel.logger = MagicMock()

    inline_bot = InlineBot(kernel)
    result = await inline_bot.provision_bot(mode="config")

    assert result.success is False
    assert result.error == "Token is not configured"


@pytest.mark.asyncio
async def test_create_bot_auto_web_is_non_interactive() -> None:
    """Web flow should always use non-interactive username strategy."""

    kernel = MagicMock()
    kernel.logger = MagicMock()
    inline_bot = InlineBot(kernel)

    inline_bot.provision_bot = AsyncMock(  # type: ignore[method-assign]
        return_value=BotProvisionResult(
            success=True,
            token="123:token",
            username="mcub_web_bot",
            created=True,
        )
    )

    response = await inline_bot.create_bot_auto_web(client=SimpleNamespace())

    assert response["success"] is True
    inline_bot.provision_bot.assert_awaited_once()
    kwargs = inline_bot.provision_bot.await_args.kwargs
    assert kwargs["interactive_username"] is False


@pytest.mark.asyncio
async def test_resolve_username_non_interactive_generates_pattern() -> None:
    """Non-interactive generation should produce mcub_*_bot username."""

    inline_bot = InlineBot(kernel=MagicMock())

    username = await inline_bot._resolve_username_for_creation(interactive=False)

    assert username.startswith("mcub_")
    assert username.endswith("_bot")
    assert len(username) >= len("mcub_12345678_bot")
