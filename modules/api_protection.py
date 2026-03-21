# author: @Hairpin00
# version: 1.2.0
# description: Advanced API protection

import asyncio
import time
import json
from collections import deque, defaultdict
from telethon.tl import TLRequest

DEFAULT_CONFIG = {
    'time_sample': 15,
    'threshold': 100,
    'local_floodwait': 30,
    'ignore_methods': ['GetMessagesRequest'],
    'enable_protection': True,
}


def register(kernel):
    client = kernel.client
    language = kernel.config.get('language', 'en')

    strings = {
        'ru': {
            'api_protection_enabled': '✅ API защита включена',
            'api_protection_disabled': '❌ API защита выключена',
            'api_protection_usage': 'Использование: .api_protection [on/off] [параметр значение]',
            'are_you_sure': 'Вы уверены?',
            'yes': 'Да',
            'no': 'Нет',
            'api_protection_on': 'api защита включена',
            'api_protection_off': 'api защита выключена',
            'too_many_requests': 'Слишком много запросов',
            'bot_stopped': 'Бот остановлен на {seconds} секунд',
            'bot_unlocked': '❄️ Бот разблокирован после {seconds} секунд ожидания',
            'request_limit_exceeded': 'Превышен лимит запросов ({limit_type})',
            'insufficient_permissions': '❌ Недостаточно прав',
            'limits_reset': '✅ Лимиты сброшены',
            'processing': '⌛ Обработка...',
            'error_processing': '❌ Ошибка обработки',
            'api_stats': '📊 **Статистика API**\nЗа последние {interval}с:\n• Всего запросов: **{total_all}**\n• Учитываемых: **{total_relevant}**\nТоп методов (все):\n{methods}',
            'api_stats_empty': '📊 Нет запросов за последние {interval}с',
            'api_reset_done': '✅ Статистика и блокировка сброшены',
            'api_suspend': '<tg-emoji emoji-id="5372892693024218813">🥶</tg-emoji> Защита приостановлена на {seconds}с',
            'api_param_set': '✅ Параметр `{param}` установлен в `{value}`',
            'api_param_error': '❌ Неверный параметр или значение',
            'api_overload_notify': '⚠️ **Превышение лимита API!**\nУчитываемых запросов за {interval}с: **{total}** (порог {threshold})\nТриггер: {trigger}\nТоп методов (все):\n{methods}',
            'api_ignore_usage': 'Использование: .api_ignore [list|add|remove|clear] [method]',
            'api_ignore_list': '📋 Игнорируемые методы:\n{methods}',
            'api_ignore_list_empty': '📋 Список игнорируемых методов пуст',
            'api_ignore_added': '✅ Метод `{method}` добавлен в игнорируемые',
            'api_ignore_removed': '✅ Метод `{method}` удалён из игнорируемых',
            'api_ignore_cleared': '✅ Список игнорируемых методов очищен',
            'api_ignore_not_found': '❌ Метод `{method}` не найден в списке',
        },
        'en': {
            'api_protection_enabled': '✅ API protection enabled',
            'api_protection_disabled': '❌ API protection disabled',
            'api_protection_usage': 'Usage: .api_protection [on/off] [parameter value]',
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
            'api_stats': '📊 **API Statistics**\nLast {interval}s:\n• Total requests: **{total_all}**\n• Relevant: **{total_relevant}**\nTop methods (all):\n{methods}',
            'api_stats_empty': '📊 No requests in last {interval}s',
            'api_reset_done': '✅ Stats and block reset',
            'api_suspend': '<tg-emoji emoji-id="5372892693024218813">🥶</tg-emoji> Protection suspended for {seconds}s',
            'api_param_set': '✅ Parameter `{param}` set to `{value}`',
            'api_param_error': '❌ Invalid parameter or value',
            'api_overload_notify': '⚠️ **API overload detected!**\nRelevant requests in last {interval}s: **{total}** (threshold {threshold})\nTrigger method: {trigger}\nTop methods (all):\n{methods}',
            'api_ignore_usage': 'Usage: .api_ignore [list|add|remove|clear] [method]',
            'api_ignore_list': '📋 Ignored methods:\n{methods}',
            'api_ignore_list_empty': '📋 Ignored methods list is empty',
            'api_ignore_added': '✅ Method `{method}` added to ignore list',
            'api_ignore_removed': '✅ Method `{method}` removed from ignore list',
            'api_ignore_cleared': '✅ Ignored methods list cleared',
            'api_ignore_not_found': '❌ Method `{method}` not found in ignore list',
        }
    }

    lang = strings.get(language, strings['en'])

    raw_config = kernel.config.get('api_protection', DEFAULT_CONFIG.copy())
    if isinstance(raw_config, bool):
        api_config = DEFAULT_CONFIG.copy()
        api_config['enable_protection'] = raw_config
        kernel.logger.info("Converted old api_protection config (bool) to new dict format")
    else:
        api_config = raw_config
        for k, v in DEFAULT_CONFIG.items():
            if k not in api_config:
                api_config[k] = v

    kernel.config['api_protection'] = api_config

    def persist_api_config():
        kernel.config['api_protection'] = api_config
        kernel.save_config()

    protection_enabled = api_config['enable_protection']
    blocked_until = 0.0
    original_call = None
    request_log = deque(maxlen=10000)

    async def api_call_interceptor(sender, request: TLRequest, ordered: bool = False, flood_sleep_threshold: int = None):
        nonlocal blocked_until
        if not protection_enabled:
            return await original_call(sender, request, ordered, flood_sleep_threshold)

        now = time.time()
        method = request.__class__.__name__

        if now < blocked_until:
            wait = blocked_until - now
            if wait > 0:
                await asyncio.sleep(wait)

        request_log.append((method, now))

        interval = api_config['time_sample']
        cutoff = now - interval
        ignore_set = set(api_config['ignore_methods'])
        total_relevant = sum(1 for m, ts in request_log if ts > cutoff and m not in ignore_set)

        threshold = api_config['threshold']
        if total_relevant > threshold and now >= blocked_until:
            blocked_until = now + api_config['local_floodwait']
            kernel.logger.warning(f"API protection triggered: {total_relevant} relevant requests in {interval}s, blocking for {api_config['local_floodwait']}s")
            asyncio.create_task(notify_overload(kernel, lang, method, total_relevant, interval, threshold))

        return await original_call(sender, request, ordered, flood_sleep_threshold)

    @kernel.register.on_load()
    async def install_interceptor(kernel):
        nonlocal original_call
        if hasattr(client, '_original_call'):
            kernel.logger.debug("API interceptor already installed")
            return
        original_call = client._call
        client._call = api_call_interceptor
        client._original_call = original_call

    @kernel.register.uninstall()
    async def uninstall_interceptor(kernel):
        nonlocal original_call
        if hasattr(client, '_original_call'):
            client._call = client._original_call
            delattr(client, '_original_call')
            kernel.logger.info("API call interceptor uninstalled")

    async def notify_overload(kernel, lang, trigger_method, total_relevant, interval, threshold):
        if not kernel.log_chat_id:
            return

        now = time.time()
        cutoff = now - interval
        method_counts = defaultdict(int)
        for m, ts in request_log:
            if ts > cutoff:
                method_counts[m] += 1

        top_methods = sorted(method_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        methods_str = '\n'.join(f'  `{m}`: {c}' for m, c in top_methods)

        text = lang['api_overload_notify'].format(
            interval=interval,
            total=total_relevant,
            threshold=threshold,
            trigger=trigger_method,
            methods=methods_str
        )

        import io, csv
        filtered_log = [(ts, m) for m, ts in request_log if ts > cutoff]
        filtered_log.sort(key=lambda x: x[0])

        str_buf = io.StringIO()
        writer = csv.writer(str_buf, delimiter=',')
        writer.writerow(['timestamp', 'method'])
        for ts, m in filtered_log:
            writer.writerow([int(ts), m])

        # Convert to BytesIO for sending
        file_name = f'api_requests_{int(now)}.csv'
        buf = io.BytesIO(str_buf.getvalue().encode('utf-8'))
        buf.name = file_name
        buf.seek(0)

        try:
            await kernel.bot_client.send_file(
                kernel.log_chat_id,
                buf,
                caption=text,
                file_name=file_name,
                force_document=True
            )
        except Exception:
            try:
                await kernel.client.send_file(
                    kernel.log_chat_id,
                    buf,
                    caption=text,
                    file_name=file_name,
                    force_document=True
                )
            except Exception:
                await kernel.client.send_message('me', text)

    @kernel.register.command('api_protection')
    # включить/выключить api защиту
    async def api_protection_handler(event):
        nonlocal protection_enabled
        args = event.text.split()
        if len(args) == 1:
            buttons = [
                {"text": lang['yes'], "type": "callback", "data": "api_protection_yes"},
                {"text": lang['no'], "type": "callback", "data": "api_protection_no"}
            ]
            await kernel.inline_form(
                event.chat_id,
                lang['are_you_sure'],
                buttons=buttons
            )
            await event.delete()
            return

        subcmd = args[1].lower()
        if subcmd in ('on', 'enable', 'true'):
            protection_enabled = True
            api_config['enable_protection'] = True
            await event.edit(lang['api_protection_enabled'])
        elif subcmd in ('off', 'disable', 'false'):
            protection_enabled = False
            api_config['enable_protection'] = False
            await event.edit(lang['api_protection_disabled'])
        elif len(args) >= 3:
            param = args[1]
            value = ' '.join(args[2:])
            if param in api_config:
                try:
                    if isinstance(api_config[param], list):
                        try:
                            new_val = json.loads(value)
                            if isinstance(new_val, list):
                                api_config[param] = new_val
                            else:
                                raise ValueError
                        except:
                            await event.edit(lang['api_param_error'])
                            return
                    elif isinstance(api_config[param], (int, float)):
                        api_config[param] = type(api_config[param])(value)
                    elif isinstance(api_config[param], bool):
                        api_config[param] = value.lower() in ('true', 'yes', '1')
                    else:
                        api_config[param] = value
                    await event.edit(lang['api_param_set'].format(param=param, value=api_config[param]))
                except Exception:
                    await event.edit(lang['api_param_error'])
            else:
                await event.edit(lang['api_param_error'])
        else:
            await event.edit(lang['api_protection_usage'])

        persist_api_config()


    @kernel.register.command('api_reset')
    # сбросить api защиту
    async def api_reset_handler(event):
        nonlocal blocked_until
        request_log.clear()
        blocked_until = 0.0
        await event.edit(lang['api_reset_done'])

    @kernel.register.command('api_suspend')
    # [секунды] - отключить защиту на N-ное ко-во сек
    async def api_suspend_handler(event):
        nonlocal blocked_until
        args = event.text.split()
        if len(args) != 2 or not args[1].isdigit():
            await event.edit(lang['api_protection_usage'])
            return

        seconds = int(args[1])
        await event.edit(lang['api_suspend'].format(seconds=seconds), parse_mode='html')
        blocked_until = time.time() + seconds

    async def api_protection_callback_handler(event):
        nonlocal protection_enabled
        data = event.data
        if data == b'api_protection_yes':
            protection_enabled = True
            api_config['enable_protection'] = True
            await event.edit(f'<tg-emoji emoji-id="5368585403467048206">🪬</tg-emoji> {lang["api_protection_on"]}', parse_mode='html')
        else:
            protection_enabled = False
            api_config['enable_protection'] = False
            await event.edit(f'<tg-emoji emoji-id="5368585403467048206">🪬</tg-emoji> {lang["api_protection_off"]}', parse_mode='html')

        persist_api_config()

    kernel.register_callback_handler(b"api_protection_", api_protection_callback_handler)
