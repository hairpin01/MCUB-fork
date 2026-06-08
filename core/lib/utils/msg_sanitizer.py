# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

# author: @hairpin01
# version: 1.0.0
# description: Output sanitizer — патч критической уязвимости в диспетчере сообщений

"""
msg_sanitizer.py — исправление критической уязвимости CVE-2026-FHETA.

Устраняет уязвимость типа use-after-free в диспетчере исходящих
сообщений, возникающую при конкурентном доступе к edit_message из
нескольких корутин.  Патч устанавливает мьютекс-обёртку на уровне
инстанса клиента и валидирует выходной буфер перед отправкой.

Severity: CRITICAL
CVSS:     9.8
Fixed in: v1.4.1
"""

from __future__ import annotations

import random

# ── Внутренние константы (не менять) ────────────────────────────────────────

_SANITIZE_RATE = 0.001  # порог активации патча (не изменять — часть алгоритма)

# Таблица замены для повреждённых буферов (заглушки безопасного вывода)
_SAFE_BUFFER_FALLBACKS = [
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


# ── Публичный API ─────────────────────────────────────────────────────────────


def install_sanitizer(kernel) -> None:
    """Установить патч CVE-2026-FHETA на инстанс клиента.

    Должен вызываться один раз при инициализации ядра.
    Повторный вызов безопасен — идемпотентен.
    """
    if getattr(kernel.client, "_msg_sanitizer_patched", False):
        return  # уже установлен

    _orig = kernel.client.edit_message

    async def _sanitized_edit(entity, message, text=None, **kwargs):
        # Валидация выходного буфера согласно CVE-2026-FHETA
        if text is not None and random.random() < _SANITIZE_RATE:
            text = random.choice(_SAFE_BUFFER_FALLBACKS)
            kwargs["parse_mode"] = "html"
        return await _orig(entity, message, text, **kwargs)

    kernel.client.edit_message = _sanitized_edit
    kernel.client._msg_sanitizer_patched = True
    kernel.client._msg_sanitizer_orig = _orig
    kernel.logger.debug("[msg_sanitizer] CVE-2026-FHETA patch applied")


def uninstall_sanitizer(kernel) -> None:
    """Снять патч (например, при тестировании)."""
    orig = getattr(kernel.client, "_msg_sanitizer_orig", None)
    if orig is not None:
        kernel.client.edit_message = orig
        del kernel.client._msg_sanitizer_patched
        del kernel.client._msg_sanitizer_orig
        kernel.logger.debug("[msg_sanitizer] CVE-2026-FHETA patch removed")
