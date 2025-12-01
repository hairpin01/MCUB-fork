# autoresponder.py - Автоответчик на ключевые слова

import json
import os
from telethon import events

def register(client):
    data_file = "autoresponder_data.json"
    
    def load_data():
        if os.path.exists(data_file):
            with open(data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"rules": []}
    
    def save_data(data):
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    @client.on(events.NewMessage(incoming=True))
    async def autoresponder_watcher(event):
        try:
            if not event.text:
                return
            
            data = load_data()
            text = event.text.lower()
            
            for rule in data["rules"]:
                if rule["trigger"].lower() in text:
                    await event.reply(rule["response"])
                    break
        except:
            pass
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ar'))
    async def ar_handler(event):
        args = event.text[4:].strip()
        data = load_data()
        
        if not args or args == "list":
            if not data["rules"]:
                await event.edit("📝 Нет правил автоответчика")
                return
            
            text = "📝 **Правила автоответчика:**\n\n"
            for i, rule in enumerate(data["rules"], 1):
                text += f"{i}. Триггер: `{rule['trigger']}`\n   Ответ: `{rule['response']}`\n\n"
            await event.edit(text)
            return
        
        if args.startswith("add "):
            parts = args[4:].split(" | ")
            if len(parts) != 2:
                await event.edit("❌ Формат: `.ar add триггер | ответ`")
                return
            
            trigger, response = parts[0].strip(), parts[1].strip()
            data["rules"].append({"trigger": trigger, "response": response})
            save_data(data)
            await event.edit(f"✅ Правило добавлено:\nТриггер: `{trigger}`\nОтвет: `{response}`")
            return
        
        if args.startswith("del "):
            try:
                index = int(args[4:].strip()) - 1
                if 0 <= index < len(data["rules"]):
                    removed = data["rules"].pop(index)
                    save_data(data)
                    await event.edit(f"🗑️ Правило удалено: `{removed['trigger']}`")
                else:
                    await event.edit("❌ Неверный номер правила")
            except ValueError:
                await event.edit("❌ Укажите номер правила")
            return
        
        if args == "clear":
            data["rules"] = []
            save_data(data)
            await event.edit("🗑️ Все правила удалены")
            return
        
        await event.edit(f"📝 **Автоответчик**\n\n"
                        f"`.ar add триггер | ответ` - добавить правило\n"
                        f"`.ar list` - список правил\n"
                        f"`.ar del [номер]` - удалить правило\n"
                        f"`.ar clear` - удалить все правила")
