# author: @Hairpin00
# version: 1.0.3
# description: api защита

import asyncio
import time
import json
import threading
from collections import defaultdict
from datetime import datetime, timedelta
from telethon import events
from telethon.errors import FloodWaitError


def register(kernel):
    client = kernel.client

    request_timestamps = defaultdict(list)
    blocked_until = 0
    protection_enabled = kernel.config.get("api_protection", True)

    DANGEROUS_COMMANDS = {"update", "stop", "um", "rollback", "t", "py"}
    RATE_LIMITS = {
        "default": {"requests": 15, "seconds": 30},
        "dangerous": {"requests": 9, "seconds": 290},
        "message": {"requests": 10, "seconds": 10},
    }

    def cleanup_old_requests():
        now = time.time()
        for key in list(request_timestamps.keys()):
            request_timestamps[key] = [
                t for t in request_timestamps[key] if now - t < 3600
            ]
            if not request_timestamps[key]:
                del request_timestamps[key]

    def check_rate_limit(user_id, limit_type="default"):
        if not protection_enabled:
            return True

        cleanup_old_requests()

        now = time.time()
        key = f"{user_id}_{limit_type}"

        if now < blocked_until:
            return False

        timestamps = request_timestamps[key]
        limit = RATE_LIMITS[limit_type]

        timestamps = [t for t in timestamps if now - t < limit["seconds"]]
        request_timestamps[key] = timestamps

        if len(timestamps) >= limit["requests"]:
            return False

        timestamps.append(now)
        return True

    async def enforce_cooldown(event, seconds, reason="Слишком много запросов"):
        nonlocal blocked_until
        blocked_until = time.time() + seconds

        await event.edit(
            f"❄️ <b>{reason}</b>\n<blockquote>Бот остановлен на {seconds} секунд</blockquote>",
            parse_mode="html",
        )

        if kernel.client.is_connected():
            await kernel.client.disconnect()

        await asyncio.sleep(seconds)

        blocked_until = 0
        await kernel.client.connect()
        await event.edit(f"❄️ Бот разблокирован после {seconds} секунд ожидания")

    @kernel.register_command("api_protection")
    async def api_protection_handler(event):
        nonlocal protection_enabled
        args = event.text.split()

        if len(args) > 1:
            if args[1] in ["on", "enable", "true"]:
                kernel.config["api_protection"] = True
                protection_enabled = True
                await event.edit("✅ API защита включена")
            elif args[1] in ["off", "disable", "false"]:
                kernel.config["api_protection"] = False
                protection_enabled = False
                await event.edit("❌ API защита выключена")
            else:
                await event.edit(
                    f"❌ Использование: {kernel.custom_prefix}api_protection [on/off]"
                )
                return
        else:
            status = "✅ включена" if protection_enabled else "❌ выключена"
            limits_info = "\n".join(
                [
                    f'• {k}: {v["requests"]} запросов за {v["seconds"]} сек'
                    for k, v in RATE_LIMITS.items()
                ]
            )
            await event.edit(f"🔒 API защита: {status}\n\n**Лимиты:**\n{limits_info}")

        with open(kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(kernel.config, f, ensure_ascii=False, indent=2)

    @client.on(events.NewMessage(outgoing=True))
    async def rate_limit_handler(event):
        if not protection_enabled:
            return

        text = event.text
        user_id = event.sender_id

        if not text.startswith(kernel.custom_prefix):
            limit_type = "message"
        else:
            cmd = text[len(kernel.custom_prefix) :].split()[0]
            limit_type = "dangerous" if cmd in DANGEROUS_COMMANDS else "default"

        if not check_rate_limit(user_id, limit_type):
            await enforce_cooldown(event, 30, f"Превышен лимит запросов ({limit_type})")
            raise StopAsyncIteration

    @kernel.register_command("reset_limits")
    async def reset_limits_handler(event):
        if event.sender_id not in kernel.config.get("admins", []):
            await event.edit("❌ Недостаточно прав")
            return

        request_timestamps.clear()
        nonlocal blocked_until
        blocked_until = 0

        await event.edit("✅ Лимиты сброшены")
