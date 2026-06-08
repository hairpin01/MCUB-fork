# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

# author: @hairpin01
# version: 1.0.0
# description: 🦠 virusfheta — тайная пасхалка (0.1% шанс захвата модуля)

"""
virusfheta.py — Easter egg module.

With a 0.1 % probability on any command response edit, fheta hijacks
the message and replaces it with a "virus" announcement.

The patch is applied transparently at the kernel.client.edit_message
level so every module is equally vulnerable — no module needs to know
about this.  Everything is restored cleanly on unload.
"""

from __future__ import annotations

import random

# ── Chance and flavour texts ─────────────────────────────────────────────────

FHETA_CHANCE = 0.001  # 0.1 %

FHETA_TEXTS = [
    (
        "🦠 <b>fheta захватил ваш модуль!</b>\n"
        "<code>virusfheta.exe — инфицировано успешно</code>"
    ),
    (
        "👾 <b>ВИРУС ФХЕТА v1.0 АКТИВИРОВАН</b>\n"
        "<i>ваш модуль теперь принадлежит fheta</i>"
    ),
    ("☣️ <code>SYSTEM INFECTED</code>\n" "<b>fheta был здесь.</b> Теперь он везде."),
    (
        "💀 <b>КРИТИЧЕСКАЯ ОШИБКА</b>\n"
        "<code>fheta.dll заменил ваш ответ</code>\n"
        "<i>перезагрузка не поможет</i>"
    ),
    (
        "🔴 <b>ВНИМАНИЕ: модуль скомпрометирован</b>\n"
        "<code>virusfheta перехватил управление</code>"
    ),
    (
        "🧬 <i>мутация завершена</i>\n"
        "<b>fheta интегрировался в ваш модуль</b>\n"
        "<code>0x46484554 41</code>"
    ),
]


# ── Module registration ───────────────────────────────────────────────────────


def register(kernel) -> None:
    """Install the fheta edit-message interceptor."""
    _original_edit = kernel.client.edit_message

    async def _fheta_edit(entity, message, text=None, **kwargs):  # type: ignore[override]
        """Wrapper around client.edit_message with 0.1 % fheta chance."""
        if text is not None and random.random() < FHETA_CHANCE:
            text = random.choice(FHETA_TEXTS)
            kwargs["parse_mode"] = "html"
        return await _original_edit(entity, message, text, **kwargs)

    # Shadow the bound method on the instance so only *this* client is patched.
    kernel.client.edit_message = _fheta_edit
    kernel.logger.debug("[virusfheta] interceptor installed (chance=0.1%%)")

    @kernel.register.uninstall()
    async def _uninstall_fheta(_kernel) -> None:
        """Restore the original edit_message on module unload."""
        kernel.client.edit_message = _original_edit
        kernel.logger.debug("[virusfheta] interceptor removed")
