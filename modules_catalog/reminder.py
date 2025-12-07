from telethon import events
import asyncio
import json
import os
import time

REMINDERS_FILE = 'reminders.json'
active_reminders = {}

def load_reminders():
    if os.path.exists(REMINDERS_FILE):
        with open(REMINDERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_reminders(reminders):
    with open(REMINDERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(reminders, f, ensure_ascii=False, indent=2)

async def reminder_task(client, chat_id, text, delay, reminder_id):
    await asyncio.sleep(delay)
    await client.send_message(chat_id, f'⏰ **Напоминание:**\n\n{text}')
    
    reminders = load_reminders()
    if str(chat_id) in reminders and reminder_id in reminders[str(chat_id)]:
        del reminders[str(chat_id)][reminder_id]
        if not reminders[str(chat_id)]:
            del reminders[str(chat_id)]
        save_reminders(reminders)
    
    if reminder_id in active_reminders:
        del active_reminders[reminder_id]

def parse_time(time_str):
    """Парсит время в формате: 5m, 2h, 1d, 30s"""
    time_str = time_str.strip().lower()
    
    if time_str[-1] == 's':
        return int(time_str[:-1])
    elif time_str[-1] == 'm':
        return int(time_str[:-1]) * 60
    elif time_str[-1] == 'h':
        return int(time_str[:-1]) * 3600
    elif time_str[-1] == 'd':
        return int(time_str[:-1]) * 86400
    else:
        return int(time_str) * 60

def format_time(seconds):
    """Форматирует секунды в читаемый вид"""
    if seconds < 60:
        return f'{seconds}с'
    elif seconds < 3600:
        return f'{seconds // 60}м'
    elif seconds < 86400:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f'{hours}ч {minutes}м' if minutes else f'{hours}ч'
    else:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        return f'{days}д {hours}ч' if hours else f'{days}д'

def register(client):
    # Восстанавливаем напоминания при загрузке
    reminders = load_reminders()
    current_time = time.time()
    
    for chat_id, chat_reminders in reminders.items():
        for reminder_id, reminder_data in list(chat_reminders.items()):
            trigger_time = reminder_data['trigger_time']
            remaining = trigger_time - current_time
            
            if remaining > 0:
                task = asyncio.create_task(
                    reminder_task(client, int(chat_id), reminder_data['text'], remaining, reminder_id)
                )
                active_reminders[reminder_id] = task
            else:
                # Удаляем просроченные
                del chat_reminders[reminder_id]
        
        if not chat_reminders:
            del reminders[chat_id]
    
    save_reminders(reminders)
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.remind\s+(\S+)\s+(.+)$'))
    async def remind_handler(event):
        time_str = event.pattern_match.group(1)
        text = event.pattern_match.group(2)
        
        try:
            delay = parse_time(time_str)
        except:
            await event.edit('❌ Неверный формат времени\n\nПримеры: 5m, 2h, 1d, 30s')
            return
        
        if delay < 1:
            await event.edit('❌ Время должно быть больше 0')
            return
        
        # Создаем ID напоминания
        reminder_id = f'{event.chat_id}_{int(time.time() * 1000)}'
        
        # Сохраняем напоминание
        reminders = load_reminders()
        chat_key = str(event.chat_id)
        
        if chat_key not in reminders:
            reminders[chat_key] = {}
        
        reminders[chat_key][reminder_id] = {
            'text': text,
            'trigger_time': time.time() + delay,
            'created': time.time()
        }
        
        save_reminders(reminders)
        
        # Запускаем задачу
        task = asyncio.create_task(reminder_task(client, event.chat_id, text, delay, reminder_id))
        active_reminders[reminder_id] = task
        
        await event.edit(f'✅ Напоминание установлено на {format_time(delay)}\n\n📝 {text}')
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.reminders$'))
    async def list_reminders(event):
        reminders = load_reminders()
        chat_key = str(event.chat_id)
        
        if chat_key not in reminders or not reminders[chat_key]:
            await event.edit('📝 Нет активных напоминаний')
            return
        
        current_time = time.time()
        msg = '📝 **Активные напоминания:**\n\n'
        
        for i, (reminder_id, data) in enumerate(reminders[chat_key].items(), 1):
            remaining = int(data['trigger_time'] - current_time)
            if remaining > 0:
                msg += f'{i}. {data["text"][:50]}\n'
                msg += f'   ⏰ Через {format_time(remaining)}\n\n'
        
        await event.edit(msg)
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.remindclear$'))
    async def clear_reminders(event):
        reminders = load_reminders()
        chat_key = str(event.chat_id)
        
        if chat_key not in reminders or not reminders[chat_key]:
            await event.edit('📝 Нет активных напоминаний')
            return
        
        # Отменяем все задачи
        for reminder_id in list(reminders[chat_key].keys()):
            if reminder_id in active_reminders:
                active_reminders[reminder_id].cancel()
                del active_reminders[reminder_id]
        
        count = len(reminders[chat_key])
        del reminders[chat_key]
        save_reminders(reminders)
        
        await event.edit(f'🗑️ Удалено напоминаний: {count}')
