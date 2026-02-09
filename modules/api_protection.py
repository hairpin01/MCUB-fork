# author: @Hairpin00
# version: 1.0.4
# description: API protection
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

    language = kernel.config.get('language', 'en')

    strings = {
        'ru': {
            'api_protection_enabled': '✅ API защита включена',
            'api_protection_disabled': '❌ API защита выключена',
            'api_protection_usage': 'Использование:',
            'are_you_sure': 'Вы уверены?',
            'yes': 'Yes',
            'no': 'No',
            'api_protection_on': 'api защита включена',
            'api_protection_off': 'api защита выключена',
            'too_many_requests': 'Слишком много запросов',
            'bot_stopped': 'Бот остановлен на {seconds} секунд',
            'bot_unlocked': '❄️ Бот разблокирован после {seconds} секунд ожидания',
            'request_limit_exceeded': 'Превышен лимит запросов ({limit_type})',
            'insufficient_permissions': '❌ Недостаточно прав',
            'limits_reset': '✅ Лимиты сброшены',
            'processing': '⌛ Processing...',
            'error_processing': '❌ Error processing',
        },
        'en': {
            'api_protection_enabled': '✅ API protection enabled',
            'api_protection_disabled': '❌ API protection disabled',
            'api_protection_usage': 'Usage:',
            'are_you_sure': 'Are you sure?',
            'yes': 'Yes',
            'no': 'No',
            'api_protection_on': 'api protection enabled',
            'api_protection_off': 'api protection disabled',
            'too_many_requests': 'Too many requests',
            'bot_stopped': 'Bot stopped for {seconds} seconds',
            'bot_unlocked': '❄️ Bot unlocked after {seconds} seconds of waiting',
            'request_limit_exceeded': 'Request limit exceeded ({limit_type})',
            'insufficient_permissions': '❌ Insufficient permissions',
            'limits_reset': '✅ Limits reset',
            'processing': '⌛ Processing...',
            'error_processing': '❌ Error processing',
        }
    }

    lang_strings = strings.get(language, strings['en'])

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

    async def enforce_cooldown(event, seconds, reason):
        nonlocal blocked_until
        blocked_until = time.time() + seconds

        await event.edit(
            f"❄️ <b>{reason}</b>\n<blockquote>{lang_strings['bot_stopped'].format(seconds=seconds)}</blockquote>",
            parse_mode="html",
        )

        if kernel.client.is_connected():
            await kernel.client.disconnect()

        await asyncio.sleep(seconds)

        blocked_until = 0
        await kernel.client.connect()
        await event.edit(lang_strings['bot_unlocked'].format(seconds=seconds))

    @kernel.register.command('api_protection')
    async def api_protection_handler(event):
        nonlocal protection_enabled
        args = event.text.split()

        if len(args) > 1:
            if args[1] in ["on", "enable", "true"]:
                kernel.config["api_protection"] = True
                protection_enabled = True
                await event.edit(lang_strings['api_protection_enabled'])
            elif args[1] in ["off", "disable", "false"]:
                kernel.config["api_protection"] = False
                protection_enabled = False
                await event.edit(lang_strings['api_protection_disabled'])
            else:
                await event.edit(
                    f"❌ {lang_strings['api_protection_usage']} {kernel.custom_prefix}api_protection [on/off]"
                )
                return
        else:
            buttons = [{"text": lang_strings['yes'], "type": "callback", "data": "api_protection_yes"},
                       {"text": lang_strings['no'], "type": "callback", "data": "api_protection_no"}]

            success = await kernel.inline_form(
                event.chat_id,
                lang_strings['are_you_sure'],
                buttons=buttons
                )
            if success:
                await event.delete()

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
            await enforce_cooldown(event, 30, lang_strings['request_limit_exceeded'].format(limit_type=limit_type))
            raise StopAsyncIteration

    @kernel.register.command('reset_limits')
    async def reset_limits_handler(event):
        if event.sender_id not in kernel.config.get("admins", []):
            await event.edit(lang_strings['insufficient_permissions'])
            return

        request_timestamps.clear()
        nonlocal blocked_until
        blocked_until = 0

        await event.edit(lang_strings['limits_reset'])

    async def api_protection_callback_handler(event):
        nonlocal protection_enabled
        data = event.data
        if data == b'api_protection_yes':
            kernel.config["api_protection"] = True
            protection_enabled = True
            await event.edit(f'<tg-emoji emoji-id="5368585403467048206">🪬</tg-emoji> {lang_strings["api_protection_on"]}', parse_mode='html')
        else:
            kernel.config["api_protection"] = False
            protection_enabled = False
            await event.edit(f'<tg-emoji emoji-id="5368585403467048206">🪬</tg-emoji> {lang_strings["api_protection_off"]}', parse_mode='html')

        with open(kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(kernel.config, f, ensure_ascii=False, indent=2)
    kernel.register_callback_handler(b"api_protection_", api_protection_callback_handler)
