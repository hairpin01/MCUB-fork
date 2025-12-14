# autoreact.py - Автоматические реакции на сообщения

import re
import json
import os
from telethon import events

def register(client):
    data_file = "autoreact_data.json"

    def load_data():
        if os.path.exists(data_file):
            with open(data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"rules": []}

    def save_data(data):
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @client.on(events.NewMessage(incoming=True))
    async def autoreact_watcher(event):
        try:
            if not event.text or event.text.startswith('.'):
                return

            data = load_data()
            text = event.text.lower().strip()

            for rule in data["rules"]:
                if rule["chat_id"] != event.chat_id:
                    continue

                for keyword in rule["keywords"]:
                    pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
                    if re.search(pattern, text):
                        try:
                            from telethon.tl.functions.messages import SendReactionRequest
                            from telethon.tl.types import ReactionEmoji
                            await client(SendReactionRequest(
                                peer=event.peer_id,
                                msg_id=event.id,
                                reaction=[ReactionEmoji(emoticon=rule["reaction"])]
                            ))
                        except:
                            try:
                                await event.react(rule["reaction"])
                            except:
                                pass
                        break
        except:
            pass

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.arconfig'))
    async def arconfig_handler(event):
        args = event.text[10:].strip()
        data = load_data()

        if not args:
            if not data["rules"]:
                await event.edit("❌ Конфигурация не настроена")
                return

            text = "📝 **Список правил AutoReact:**\n\n"
            for i, rule in enumerate(data["rules"], 1):
                keywords = ", ".join(rule["keywords"])
                text += f"{i}. Чат: `{rule['chat_id']}` | Реакция: {rule['reaction']} | Слова: `{keywords}`\n"
            await event.edit(text)
            return

        if args.lower() == "clear":
            data["rules"] = []
            save_data(data)
            await event.edit("✅ Конфигурация очищена")
            return

        try:
            parts = args.split(';')
            if len(parts) != 3:
                await event.edit("❌ Неверный формат. Используйте: `чатID;реакция;слово1,слово2,слово3`")
                return

            chat_id = int(parts[0])
            reaction = parts[1].strip()
            keywords = [k.strip() for k in parts[2].split(',') if k.strip()]

            if not reaction or not keywords:
                await event.edit("❌ Реакция и ключевые слова не могут быть пустыми")
                return

            data["rules"] = [r for r in data["rules"] if r["chat_id"] != chat_id]
            data["rules"].append({"chat_id": chat_id, "reaction": reaction, "keywords": keywords})
            save_data(data)

            await event.edit(f"✅ Правило добавлено:\nЧат: `{chat_id}`\nРеакция: {reaction}\nСлова: `{', '.join(keywords)}`")
        except ValueError:
            await event.edit("❌ Неверный формат ID чата")
        except Exception as e:
            await event.edit(f"❌ Ошибка: {str(e)}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.artest'))
    async def artest_handler(event):
        args = event.text[8:].strip()

        if not args:
            await event.edit("🧪 Использование: `.artest [текст для теста]`")
            return

        data = load_data()
        triggered = False

        for rule in data["rules"]:
            if rule["chat_id"] == event.chat_id:
                for keyword in rule["keywords"]:
                    if keyword.lower() in args.lower():
                        await event.edit(f"✅ Сработало правило:\nРеакция: {rule['reaction']}\nКлючевое слово: `{keyword}`")
                        triggered = True
                        break
                if triggered:
                    break

        if not triggered:
            await event.edit("❌ Ни одно правило не сработало")
