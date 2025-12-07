
# requires: json

from telethon import events
import re
import json
import os
from telethon.tl.types import MessageEntityTextUrl

CONFIG_FILE = "link_preview_config.json"
ZERO_WIDTH_CHAR = "\u2060"

class LinkPreviewConfig:
    def __init__(self):
        self.enabled = False
        self.link = ""
        self.load_config()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.enabled = data.get('enabled', False)
                    self.link = data.get('link', "")
            except:
                self.enabled = False
                self.link = ""

    def save_config(self):
        data = {
            'enabled': self.enabled,
            'link': self.link
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

def add_link_preview(text, entities, link):
    if not text or not link:
        return text, entities

    new_text = ZERO_WIDTH_CHAR + text

    new_entities = []

    if entities:
        for entity in entities:
            new_entity = entity
            if hasattr(entity, 'offset'):
                new_entity.offset += 1
            new_entities.append(new_entity)

    link_entity = MessageEntityTextUrl(
        offset=0,
        length=1,
        url=link
    )

    new_entities.append(link_entity)

    return new_text, new_entities

def register(client):
    config = LinkPreviewConfig()

    @client.on(events.NewMessage(outgoing=True))
    async def message_handler(event):
        if not config.enabled or not config.link:
            return

        if event.text and event.text.startswith('.lhe'):
            return

        if event.text and event.text.startswith('.setlhe'):
            return

        try:
            text = event.text
            entities = event.message.entities

            new_text, new_entities = add_link_preview(text, entities, config.link)

            if new_text != text:
                await event.edit(new_text, formatting_entities=new_entities, link_preview=True)
        except:
            pass

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.lhe (on|off|status)$'))
    async def toggle_handler(event):
        cmd = event.pattern_match.group(1)
        if cmd == 'on':
            config.enabled = True
            await event.edit('✅ **Предпросмотр ссылки включен**')
        elif cmd == 'off':
            config.enabled = False
            await event.edit('❌ **Предпросмотр ссылки выключен**')
        else:
            status = 'включен ✅' if config.enabled else 'выключен ❌'
            link_display = f"`{config.link}`" if config.link else "не установлена"
            await event.edit(f'📊 **Статус:** {status}\n🔗 **Ссылка:** {link_display}')

        config.save_config()

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.setlhe (.+)$'))
    async def setlink_handler(event):
        link = event.pattern_match.group(1).strip()

        if not re.match(r'^https?://', link):
            link = 'https://' + link

        config.link = link
        config.save_config()

        await event.edit(f'✅ **Ссылка установлена:**\n`{link}`')

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.lhe$'))
    async def help_handler(event):
        help_text = """
🔗 **Предпросмотр ссылки в сообщениях**

`.lhe on` - включить предпросмотр
`.lhe off` - выключить предпросмотр
`.lhe status` - статус
`.setlhe <ссылка>` - установить ссылку

Автор @Hairpin00
"""
        await event.edit(help_text)
