
# requires: telethon, json
from telethon import events
import random
import json
import os

CONFIG_FILE = "emoji_config.json"
DEFAULT_EMOJIS = ["💀", "😈😈😈", "😈😈", "😈", "✍️", "🖐️😈🤚", "😨😨😨", "🤑🤑🤑", "🤑", "😰😰", "🙏😭", "🤯", "⛄⛄", "⛄", "🥵🥵", "🫳🌍🫴", "🍌", "☠️☠️"]

class EmojiConfig:
    def __init__(self):
        self.enabled = True
        self.emojis = DEFAULT_EMOJIS.copy()
        self.load_config()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.enabled = data.get('enabled', True)
                    self.emojis = data.get('emojis', DEFAULT_EMOJIS.copy())
            except:
                self.enabled = True
                self.emojis = DEFAULT_EMOJIS.copy()

    def save_config(self):
        data = {
            'enabled': self.enabled,
            'emojis': self.emojis
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

def register(client):
    config = EmojiConfig()

    @client.on(events.NewMessage(outgoing=True))
    async def message_handler(event):
        if not config.enabled:
            return

        if event.text and not event.text.startswith('.'):
            try:
                await event.edit(event.text + random.choice(config.emojis))
            except:
                pass

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.emoji (on|off|status)$'))
    async def toggle_handler(event):
        cmd = event.pattern_match.group(1)
        if cmd == 'on':
            config.enabled = True
            await event.edit('✅ **Добавление эмодзи включено**')
        elif cmd == 'off':
            config.enabled = False
            await event.edit('❌ **Добавление эмодзи выключено**')
        else:
            status = 'включено ✅' if config.enabled else 'выключено ❌'
            await event.edit(f'📊 **Статус:** {status}\n🎭 **Эмодзи в списке:** {len(config.emojis)}')

        config.save_config()

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.emoji add (.+)$'))
    async def add_handler(event):
        emoji = event.pattern_match.group(1).strip()
        if emoji:
            config.emojis.append(emoji)
            config.save_config()
            await event.edit(f'✅ **Эмодзи добавлен:** {emoji}\n📋 **Всего:** {len(config.emojis)}')
        else:
            await event.edit('❌ **Укажите эмодзи**')

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.emoji list$'))
    async def list_handler(event):
        if not config.emojis:
            await event.edit('📭 **Список эмодзи пуст**')
            return

        text = '📋 **Список эмодзи:**\n\n'
        for i, emoji in enumerate(config.emojis, 1):
            text += f'{i}. {emoji}\n'

        if len(text) > 4000:
            text = text[:4000] + '\n...'

        await event.edit(text)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.emoji del (\d+)$'))
    async def delete_handler(event):
        try:
            index = int(event.pattern_match.group(1)) - 1
            if 0 <= index < len(config.emojis):
                removed = config.emojis.pop(index)
                config.save_config()
                await event.edit(f'✅ **Удален эмодзи:** {removed}\n📋 **Осталось:** {len(config.emojis)}')
            else:
                await event.edit('❌ **Неверный номер**')
        except:
            await event.edit('❌ **Используйте:** `.emoji del <номер>`')

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.emoji reset$'))
    async def reset_handler(event):
        config.emojis = DEFAULT_EMOJIS.copy()
        config.save_config()
        await event.edit(f'✅ **Список сброшен к стандартному**\n📋 **Эмодзи:** {len(config.emojis)}')

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.emoji$'))
    async def help_handler(event):
        help_text = """
🎭 **Управление эмодзи:**

`.emoji on` - включить
`.emoji off` - выключить
`.emoji status` - статус
`.emoji add <emoji>` - добавить эмодзи
`.emoji del <номер>` - удалить эмодзи
`.emoji list` - список эмодзи
`.emoji reset` - сбросить к стандартным
"""
        await event.edit(help_text)
