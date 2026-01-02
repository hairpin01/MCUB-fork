# author: @Hairpin00
# version: 1.0.3
# description: settings
import json
import os
from telethon import events, Button

def register(kernel):
    client = kernel.client

    @kernel.register_command('prefix')
    # поменять prefix
    async def prefix_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await event.edit(f'❌ Использование: {kernel.custom_prefix}prefix [символ]')
            return

        new_prefix = args[1]
        kernel.custom_prefix = new_prefix
        kernel.config['command_prefix'] = new_prefix

        with open(kernel.CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(kernel.config, f, ensure_ascii=False, indent=2)

        await event.edit(f'✅ Префикс изменен на `{new_prefix}`')

    @kernel.register_command('alias')
    # пример: addalias p=ping
    async def alias_handler(event):
        args = event.text[len(kernel.custom_prefix)+6:].strip()
        if '=' not in args:
            await event.edit(f'❌ Использование: `{kernel.custom_prefix}alias алиас = команда`')
            return

        parts = args.split('=')
        if len(parts) != 2:
            await event.edit(f'❌ Использование: `{kernel.custom_prefix}alias алиас = команда`')
            return

        alias = parts[0].strip()
        command = parts[1].strip()

        kernel.aliases[alias] = command
        kernel.config['aliases'] = kernel.aliases

        with open(kernel.CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(kernel.config, f, ensure_ascii=False, indent=2)

        await event.edit(f'✅ Алиас создан: `{kernel.custom_prefix}{alias}` → `{kernel.custom_prefix}{command}`')

    @kernel.register_command('2fa')
    # двухфакторная аутентификация
    async def twofa_handler(event):
        current = kernel.config.get('2fa_enabled', False)
        kernel.config['2fa_enabled'] = not current

        with open(kernel.CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(kernel.config, f, ensure_ascii=False, indent=2)

        status = '✅ включена (инлайн-подтверждение)' if not current else '❌ выключена'
        await event.edit(f'🔐 Двухфакторная аутентификация {status}\n\n'
                        f'Теперь опасные команды требуют подтверждения через кнопки.')

    @kernel.register_command('powersave')
    # энергосбережения
    async def powersave_handler(event):
        kernel.power_save_mode = not kernel.power_save_mode
        kernel.config['power_save_mode'] = kernel.power_save_mode

        with open(kernel.CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(kernel.config, f, ensure_ascii=False, indent=2)

        status = '🔋 включен' if kernel.power_save_mode else '⚡ выключен'
        features = '\n• Логирование отключено\n• Healthcheck реже в 3 раза\n• Снижена нагрузка' if kernel.power_save_mode else ''
        await event.edit(f'Режим энергосбережения {status}{features}')

    @kernel.register_command('lang')
    # ru or en
    async def lang_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await event.edit(f'❌ Использование: {kernel.custom_prefix}lang [ru/en]')
            return

        new_lang = args[1].lower()
        LANGS = {'ru', 'en'}

        if new_lang not in LANGS:
            await event.edit(f'❌ Доступные языки: {", ".join(LANGS)}')
            return

        kernel.config['language'] = new_lang

        with open(kernel.CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(kernel.config, f, ensure_ascii=False, indent=2)

        await event.edit(f'✅ Язык изменен на: {new_lang}')

    @kernel.register_command('settings')
    # всё настройки
    async def settings_handler(event):
        settings_info = f'''
**⚙️ Настройки юзербота**

**Основные:**
• Префикс: `{kernel.custom_prefix}`
• Язык: `{kernel.config.get("language", "ru")}`
• Тема: `{kernel.config.get("theme", "default")}`

**Безопасность:**
• 2FA: `{"✅ включена" if kernel.config.get("2fa_enabled", False) else "❌ выключена"}`
• API защита: `{"✅ включена" if kernel.config.get("api_protection", False) else "❌ выключена"}`

**Производительность:**
• Энергосбережение: `{"✅ включено" if kernel.power_save_mode else "❌ выключено"}`
• Healthcheck: каждые `{kernel.config.get("healthcheck_interval", 30)}` мин

**Алиасы:** {len(kernel.aliases)}
{chr(10).join([f"• `{kernel.custom_prefix}{alias}` → `{kernel.custom_prefix}{cmd}`" for alias, cmd in list(kernel.aliases.items())[:5]])}
{f"{chr(10)}... и еще {len(kernel.aliases) - 5}" if len(kernel.aliases) > 5 else ""}
'''
        await event.edit(settings_info)

    @kernel.register_command('mcubinfo')
    # shows detailed information about userbots, their pros and cons
    async def mcubinfo_cmd(event):
        try:
            await event.edit("🔑", parse_mode='html')
            info_text = (
                "🎭 <b>Что такое юзербот?</b>\n"
                "<blockquote>Это программа, которая работает через ваш личный аккаунт Telegram, используя клиентский API. "
                "В отличие от обычных ботов (<code>Bot API</code>зербот имеет доступ ко всем функциям обычного пользователя — может отправлять сообщения, управлять группами, "
                "автоматизировать действия и многое другое.</blockquote>\n\n"
                "<b>Преимущества:</b> <blockquote><b>Полная автоматизация</b> — можно настроить автоответы, мониторинг чатов, управление каналами и группами\n"
                "<b>Неограниченные возможности</b> — доступ ко всем функциям Telegram, включая те, что недоступны обычным ботам\n"
                "<b>Гибкость и кастомизация</b> — можно писать собственный код под любые задачи\n"
                "•<b>Прямое подключение</b> — работа напрямую с серверами Telegram без лишних промежуточных слоёв.</blockquote>\n\n"

                "🚂 <b>Главные риски и недостатки:</b>\n"
                "<blockquote><b>Блокировка аккаунта</b> — Telegram может заблокировать аккаунт за подозрительную активность (спам, массовые действия)\n"
                "• <b>Отсутствие официальной поддержки</b> — User API не документирован официально, могут быть нестабильности\n"
                "<b>Ответственность на пользователе</b> — за действия бота, нарушающие правила Telegram, отвечает владелец аккаунта\n"
                "<b>Риск для основного аккаунта</b> — рекомендуется использовать отдельный аккаунт для юзербота</blockquote>"
            )

            await event.edit(info_text, parse_mode='html')
        except Exception as e:
            await kernel.handle_error(e, source="mcubinfo_cmd", event=event)
            await event.edit("🌩️ <b>error, check logs</b>", parse_mode='html')




