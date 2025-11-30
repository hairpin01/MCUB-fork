# mitrichgram.py - Модуль для отправки случайных эдитов

import random
import json
import os
from telethon import events

def register(client):
    data_file = "mitrichgram_data.json"
    
    def load_data():
        if os.path.exists(data_file):
            with open(data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"edits": {}, "last_edit": None}
    
    def save_data(data):
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.edit'))
    async def edit_handler(event):
        args = event.text[6:].strip()
        data = load_data()
        
        # Очистка истории
        if args == "clear":
            data["last_edit"] = None
            save_data(data)
            await event.edit("🔄 История последнего эдита очищена")
            return
        
        # Сохранение эдита
        if args.startswith("set"):
            if not event.is_reply:
                await event.edit("❌ Ответьте на видео командой `.edit set номер`")
                return
            
            reply = await event.get_reply_message()
            if not (reply.video or reply.gif):
                await event.edit("❌ Это не видео. Ответьте на видео или GIF")
                return
            
            parts = args.split()
            num = parts[1] if len(parts) > 1 else str(len(data["edits"]) + 1)
            data["edits"][num] = {"chat_id": reply.chat_id, "message_id": reply.id}
            save_data(data)
            await event.edit(f"✅ Эдит №{num} сохранен!")
            return
        
        # Список эдитов
        if args == "list":
            if not data["edits"]:
                await event.edit("❌ Нет сохраненных эдитов. Используйте `.edit set номер`")
                return
            edits_list = ", ".join(sorted(data["edits"].keys(), key=lambda x: int(x) if x.isdigit() else 999))
            await event.edit(f"📋 Список сохраненных эдитов: {edits_list}")
            return
        
        # Отправка эдита
        if not data["edits"]:
            await event.edit("❌ Нет сохраненных эдитов. Используйте `.edit set номер`")
            return
        
        # Выбор эдита
        if args and args in data["edits"]:
            edit_key = args
        else:
            available = list(data["edits"].keys())
            if len(available) > 1 and data["last_edit"] in available:
                available.remove(data["last_edit"])
            edit_key = random.choice(available)
        
        data["last_edit"] = edit_key
        save_data(data)
        
        try:
            saved_msg = await client.get_messages(
                data["edits"][edit_key]["chat_id"],
                ids=data["edits"][edit_key]["message_id"]
            )
            
            if saved_msg.video:
                await event.edit(file=saved_msg.video, text="")
            elif saved_msg.gif:
                await event.edit(file=saved_msg.gif, text="")
            else:
                await event.edit("❌ Это не видео")
        except Exception as e:
            await event.edit(f"❌ Ошибка отправки: {str(e)}")
