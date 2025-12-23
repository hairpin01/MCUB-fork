import json
import os
from telethon import events, Button

def register(kernel):
    client = kernel.client
    
    @kernel.register_command('prefix')
    async def prefix_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await event.edit(f'❌ Использование: {kernel.custom_prefix}prefix [символ]')
            return
        
        new_prefix = args[1]
        if len(new_prefix) != 1:
            await event.edit('❌ Префикс должен быть одним символом')
            return
        
        kernel.custom_prefix = new_prefix
        kernel.config['command_prefix'] = new_prefix
        
        with open(kernel.CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(kernel.config, f, ensure_ascii=False, indent=2)
        
        await event.edit(f'✅ Префикс изменен на `{new_prefix}`')
    
    @kernel.register_command('alias')
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
    async def twofa_handler(event):
        current = kernel.config.get('2fa_enabled', False)
        kernel.config['2fa_enabled'] = not current
        
        with open(kernel.CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(kernel.config, f, ensure_ascii=False, indent=2)
        
        status = '✅ включена (инлайн-подтверждение)' if not current else '❌ выключена'
        await event.edit(f'🔐 Двухфакторная аутентификация {status}\n\n'
                        f'Теперь опасные команды требуют подтверждения через кнопки.')
    
    @kernel.register_command('powersave')
    async def powersave_handler(event):
        kernel.power_save_mode = not kernel.power_save_mode
        kernel.config['power_save_mode'] = kernel.power_save_mode
        
        with open(kernel.CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(kernel.config, f, ensure_ascii=False, indent=2)
        
        status = '🔋 включен' if kernel.power_save_mode else '⚡ выключен'
        features = '\n• Логирование отключено\n• Healthcheck реже в 3 раза\n• Снижена нагрузка' if kernel.power_save_mode else ''
        await event.edit(f'Режим энергосбережения {status}{features}')
    
    @kernel.register_command('lang')
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
    
    @kernel.register_command('theme')
    async def theme_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await event.edit(f'❌ Использование: {kernel.custom_prefix}theme [default/minimal/emoji]')
            return
        
        new_theme = args[1].lower()
        THEMES = {'default', 'minimal', 'emoji'}
        
        if new_theme not in THEMES:
            await event.edit(f'❌ Доступные темы: {", ".join(THEMES)}')
            return
        
        kernel.config['theme'] = new_theme
        
        with open(kernel.CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(kernel.config, f, ensure_ascii=False, indent=2)
        
        await event.edit(f'✅ Тема изменена на: {new_theme}')
    
    @kernel.register_command('settings')
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