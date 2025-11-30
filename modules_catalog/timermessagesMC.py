# timermessagesMC.py - Модуль множественных таймеров

import asyncio
import time
import json
import os
from telethon import events

def register(client):
    data_file = "timers_data.json"
    timer_tasks = {}
    
    def load_data():
        if os.path.exists(data_file):
            with open(data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"timers": {}, "next_id": 1}
    
    def save_data(data):
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    async def timer_loop(timer_id, timer_data):
        while True:
            data = load_data()
            if timer_id not in data["timers"] or not data["timers"][timer_id].get("is_running"):
                break
            try:
                await client.send_message(timer_data["chat_id"], timer_data["message"])
                data["timers"][timer_id]["sent_count"] = data["timers"][timer_id].get("sent_count", 0) + 1
                data["timers"][timer_id]["last_sent"] = time.time()
                save_data(data)
            except:
                pass
            await asyncio.sleep(timer_data["interval"])
    
    def find_timer(name, data):
        for tid, tdata in data["timers"].items():
            if tdata["name"] == name:
                return tid
        return None
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.timer'))
    async def timer_handler(event):
        args = event.text[7:].strip()
        data = load_data()
        
        if not args or args == "help":
            await event.edit("🤖 **MultiTimer**\n\n"
                "`.timer add [интервал] [текст]` - добавить таймер\n"
                "`.timer add [имя] [интервал] [текст]` - с именем\n"
                "`.timer start [имя]` - запустить\n"
                "`.timer stop [имя]` - остановить\n"
                "`.timer delete [имя]` - удалить\n"
                "`.timer list` - список\n"
                "`.timer status [имя]` - статус\n"
                "`.timer startall` - запустить все\n"
                "`.timer stopall` - остановить все\n"
                "`.timer stats` - статистика")
            return
        
        parts = args.split(" ", 1)
        cmd = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""
        
        if cmd == "add":
            if not rest:
                await event.edit("❌ Использование: `.timer add [интервал] [текст]`")
                return
            
            try:
                first_space = rest.find(" ")
                if first_space == -1:
                    await event.edit("❌ Недостаточно аргументов")
                    return
                
                first_arg = rest[:first_space]
                try:
                    interval = int(first_arg)
                    name = f"Таймер_{data['next_id']}"
                    message = rest[first_space + 1:]
                except ValueError:
                    second_space = rest.find(" ", first_space + 1)
                    if second_space == -1:
                        await event.edit("❌ Недостаточно аргументов")
                        return
                    name = rest[:first_space]
                    interval = int(rest[first_space + 1:second_space])
                    message = rest[second_space + 1:]
                
                if interval <= 0:
                    await event.edit("❌ Интервал должен быть больше 0")
                    return
                
                timer_id = str(data["next_id"])
                data["next_id"] += 1
                data["timers"][timer_id] = {
                    "name": name,
                    "interval": interval,
                    "message": message,
                    "is_running": False,
                    "chat_id": event.chat_id,
                    "sent_count": 0,
                    "last_sent": None
                }
                save_data(data)
                await event.edit(f"✅ Таймер добавлен!\n📝 Имя: {name}\n💬 Сообщение: {message}\n⏰ Интервал: {interval} сек\n🆔 ID: {timer_id}")
            except Exception as e:
                await event.edit(f"❌ Ошибка: {str(e)}")
            return
        
        if cmd == "start":
            if not rest:
                await event.edit("❌ Использование: `.timer start [имя]`")
                return
            
            timer_id = find_timer(rest, data)
            if not timer_id:
                await event.edit(f"❌ Таймер '{rest}' не найден")
                return
            
            if data["timers"][timer_id].get("is_running"):
                await event.edit(f"⚠️ Таймер '{rest}' уже запущен")
                return
            
            data["timers"][timer_id]["is_running"] = True
            data["timers"][timer_id]["start_time"] = time.time()
            save_data(data)
            
            timer_tasks[timer_id] = asyncio.create_task(timer_loop(timer_id, data["timers"][timer_id]))
            await event.edit(f"🚀 Таймер '{rest}' запущен!")
            return
        
        if cmd == "stop":
            if not rest:
                await event.edit("❌ Использование: `.timer stop [имя]`")
                return
            
            timer_id = find_timer(rest, data)
            if not timer_id:
                await event.edit(f"❌ Таймер '{rest}' не найден")
                return
            
            if not data["timers"][timer_id].get("is_running"):
                await event.edit(f"⚠️ Таймер '{rest}' не запущен")
                return
            
            data["timers"][timer_id]["is_running"] = False
            save_data(data)
            
            if timer_id in timer_tasks:
                timer_tasks[timer_id].cancel()
                del timer_tasks[timer_id]
            
            await event.edit(f"⛔ Таймер '{rest}' остановлен")
            return
        
        if cmd == "delete":
            if not rest:
                await event.edit("❌ Использование: `.timer delete [имя]`")
                return
            
            timer_id = find_timer(rest, data)
            if not timer_id:
                await event.edit(f"❌ Таймер '{rest}' не найден")
                return
            
            if data["timers"][timer_id].get("is_running"):
                data["timers"][timer_id]["is_running"] = False
                if timer_id in timer_tasks:
                    timer_tasks[timer_id].cancel()
                    del timer_tasks[timer_id]
            
            del data["timers"][timer_id]
            save_data(data)
            await event.edit(f"🗑️ Таймер '{rest}' удален")
            return
        
        if cmd == "list":
            if not data["timers"]:
                await event.edit("❌ Нет добавленных таймеров")
                return
            
            text = "📊 **Текущие таймеры:**\n\n"
            for tid, tdata in data["timers"].items():
                status = "🟢 Запущен" if tdata.get("is_running") else "🔴 Остановлен"
                msg = tdata["message"][:30] + ("..." if len(tdata["message"]) > 30 else "")
                text += f"📝 **{tdata['name']}** (ID: {tid})\n   ⏰ {tdata['interval']} сек | {status}\n   💬 {msg}\n   📊 Отправлено: {tdata.get('sent_count', 0)} раз\n\n"
            await event.edit(text)
            return
        
        if cmd == "status":
            if not rest:
                await event.edit("❌ Использование: `.timer status [имя]`")
                return
            
            timer_id = find_timer(rest, data)
            if not timer_id:
                await event.edit(f"❌ Таймер '{rest}' не найден")
                return
            
            tdata = data["timers"][timer_id]
            status = "🟢 Запущен" if tdata.get("is_running") else "🔴 Остановлен"
            last_sent = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(tdata["last_sent"])) if tdata.get("last_sent") else "Никогда"
            
            await event.edit(f"📋 **Статус таймера '{tdata['name']}':**\n\n"
                f"• **Сообщение:** {tdata['message']}\n"
                f"• **Интервал:** {tdata['interval']} секунд\n"
                f"• **Статус:** {status}\n"
                f"• **Отправлено:** {tdata.get('sent_count', 0)} раз\n"
                f"• **Последняя отправка:** {last_sent}")
            return
        
        if cmd == "startall":
            started = 0
            for tid, tdata in data["timers"].items():
                if not tdata.get("is_running"):
                    tdata["is_running"] = True
                    tdata["start_time"] = time.time()
                    timer_tasks[tid] = asyncio.create_task(timer_loop(tid, tdata))
                    started += 1
            save_data(data)
            await event.edit(f"🚀 Запущено {started} таймеров")
            return
        
        if cmd == "stopall":
            stopped = 0
            for tid, tdata in data["timers"].items():
                if tdata.get("is_running"):
                    tdata["is_running"] = False
                    if tid in timer_tasks:
                        timer_tasks[tid].cancel()
                        del timer_tasks[tid]
                    stopped += 1
            save_data(data)
            await event.edit(f"🛑 Остановлено {stopped} таймеров")
            return
        
        if cmd == "stats":
            if not data["timers"]:
                await event.edit("❌ Нет добавленных таймеров")
                return
            
            total = len(data["timers"])
            running = sum(1 for t in data["timers"].values() if t.get("is_running"))
            messages = sum(t.get("sent_count", 0) for t in data["timers"].values())
            
            await event.edit(f"📈 **Статистика таймеров:**\n\n"
                f"• **Всего таймеров:** {total}\n"
                f"• **Активных:** {running}\n"
                f"• **Всего отправлено сообщений:** {messages}")
            return
