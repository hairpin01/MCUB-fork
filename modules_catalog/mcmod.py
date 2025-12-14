# mcmod.py - Модуль модерации

import time
import json
import os
from datetime import datetime, timedelta
from telethon import events
from telethon.tl.types import ChannelParticipantAdmin, ChannelParticipantCreator
from telethon.tl.functions.channels import GetParticipantRequest

def register(client):
    data_file = "mcmod_data.json"

    def load_data():
        if os.path.exists(data_file):
            with open(data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def save_data(data):
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def parse_time(time_str):
        if not time_str:
            return None
        multipliers = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400, 'w': 604800}
        try:
            if time_str[-1] in multipliers:
                return int(time_str[:-1]) * multipliers[time_str[-1]]
            return int(time_str) * 60
        except:
            return None

    def format_time(seconds):
        if not seconds:
            return "навсегда"
        periods = [('нед', 604800), ('дн', 86400), ('ч', 3600), ('мин', 60)]
        result = []
        for name, sec in periods:
            if seconds >= sec:
                val, seconds = divmod(seconds, sec)
                result.append(f"{val}{name}")
        return ' '.join(result[:2])

    async def get_user(event):
        if event.is_reply:
            reply = await event.get_reply_message()
            return await reply.get_sender() if reply else None
        args = event.text.split()
        if len(args) > 1:
            try:
                return await client.get_entity(args[1].lstrip('@'))
            except:
                pass
        return None

    async def is_admin(chat_id, user_id):
        try:
            participant = await client(GetParticipantRequest(chat_id, user_id))
            return isinstance(participant.participant, (ChannelParticipantAdmin, ChannelParticipantCreator))
        except:
            return False

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.mute'))
    async def mute_handler(event):
        user = await get_user(event)
        if not user:
            await event.edit("❌ Ответьте на сообщение или укажите @username")
            return

        if user.id == event.sender_id:
            await event.edit("❌ Нельзя применить к себе")
            return

        if await is_admin(event.chat_id, user.id):
            await event.edit("❌ Нельзя замутить администратора")
            return

        args = event.text.split()[2:] if len(event.text.split()) > 2 else []
        duration = parse_time(args[0]) if args else 3600

        try:
            until_date = datetime.now() + timedelta(seconds=duration) if duration else None
            await client.edit_permissions(event.chat_id, user.id, send_messages=False, until_date=until_date)

            data = load_data()
            chat_str = str(event.chat_id)
            if chat_str not in data:
                data[chat_str] = {"mutes": {}, "warns": {}}
            data[chat_str]["mutes"][str(user.id)] = {"until": time.time() + duration if duration else None}
            save_data(data)

            name = f"@{user.username}" if user.username else user.first_name
            await event.edit(f"🔇 Пользователь {name} заглушен на {format_time(duration)}")
        except Exception as e:
            await event.edit(f"❌ Ошибка: {str(e)}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.unmute'))
    async def unmute_handler(event):
        user = await get_user(event)
        if not user:
            await event.edit("❌ Ответьте на сообщение или укажите @username")
            return

        try:
            await client.edit_permissions(event.chat_id, user.id, send_messages=True)

            data = load_data()
            chat_str = str(event.chat_id)
            if chat_str in data and str(user.id) in data[chat_str].get("mutes", {}):
                del data[chat_str]["mutes"][str(user.id)]
                save_data(data)

            name = f"@{user.username}" if user.username else user.first_name
            await event.edit(f"🔊 Пользователь {name} разглушен")
        except Exception as e:
            await event.edit(f"❌ Ошибка: {str(e)}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ban'))
    async def ban_handler(event):
        user = await get_user(event)
        if not user:
            await event.edit("❌ Ответьте на сообщение или укажите @username")
            return

        if user.id == event.sender_id:
            await event.edit("❌ Нельзя применить к себе")
            return

        if await is_admin(event.chat_id, user.id):
            await event.edit("❌ Нельзя забанить администратора")
            return

        args = event.text.split()[2:] if len(event.text.split()) > 2 else []
        duration = parse_time(args[0]) if args else 86400

        try:
            until_date = datetime.now() + timedelta(seconds=duration) if duration else None
            await client.edit_permissions(event.chat_id, user.id, view_messages=False, until_date=until_date)

            name = f"@{user.username}" if user.username else user.first_name
            await event.edit(f"🚫 Пользователь {name} забанен на {format_time(duration)}")
        except Exception as e:
            await event.edit(f"❌ Ошибка: {str(e)}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.unban'))
    async def unban_handler(event):
        user = await get_user(event)
        if not user:
            await event.edit("❌ Ответьте на сообщение или укажите @username")
            return

        try:
            await client.edit_permissions(event.chat_id, user.id, view_messages=True)
            name = f"@{user.username}" if user.username else user.first_name
            await event.edit(f"✅ Пользователь {name} разбанен")
        except Exception as e:
            await event.edit(f"❌ Ошибка: {str(e)}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.kick'))
    async def kick_handler(event):
        user = await get_user(event)
        if not user:
            await event.edit("❌ Ответьте на сообщение или укажите @username")
            return

        if user.id == event.sender_id:
            await event.edit("❌ Нельзя применить к себе")
            return

        if await is_admin(event.chat_id, user.id):
            await event.edit("❌ Нельзя кикнуть администратора")
            return

        try:
            await client.kick_participant(event.chat_id, user.id)
            name = f"@{user.username}" if user.username else user.first_name
            await event.edit(f"👢 Пользователь {name} кикнут")
        except Exception as e:
            await event.edit(f"❌ Ошибка: {str(e)}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.warn'))
    async def warn_handler(event):
        user = await get_user(event)
        if not user:
            await event.edit("❌ Ответьте на сообщение или укажите @username")
            return

        if user.id == event.sender_id:
            await event.edit("❌ Нельзя применить к себе")
            return

        if await is_admin(event.chat_id, user.id):
            await event.edit("❌ Нельзя выдать предупреждение администратору")
            return

        data = load_data()
        chat_str = str(event.chat_id)
        if chat_str not in data:
            data[chat_str] = {"mutes": {}, "warns": {}}
        if "warns" not in data[chat_str]:
            data[chat_str]["warns"] = {}

        user_str = str(user.id)
        if user_str not in data[chat_str]["warns"]:
            data[chat_str]["warns"][user_str] = []

        args = event.text.split()[2:] if len(event.text.split()) > 2 else []
        duration = parse_time(args[0]) if args else 604800
        reason = ' '.join(args[1:]) if len(args) > 1 else "Не указана"

        data[chat_str]["warns"][user_str].append({
            "timestamp": time.time(),
            "reason": reason,
            "until": time.time() + duration if duration else None
        })

        current_time = time.time()
        active_warns = [w for w in data[chat_str]["warns"][user_str] if not w.get("until") or w["until"] > current_time]
        current = len(active_warns)
        max_warns = 3

        save_data(data)

        name = f"@{user.username}" if user.username else user.first_name

        if current >= max_warns:
            await client.edit_permissions(event.chat_id, user.id, send_messages=False, until_date=datetime.now() + timedelta(hours=1))
            await event.edit(f"🚫 Пользователь {name} достиг максимума предупреждений ({max_warns})")
        else:
            await event.edit(f"⚠️ Пользователь {name} получил предупреждение ({current}/{max_warns})\nПричина: {reason}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.unwarn'))
    async def unwarn_handler(event):
        user = await get_user(event)
        if not user:
            await event.edit("❌ Ответьте на сообщение или укажите @username")
            return

        data = load_data()
        chat_str = str(event.chat_id)
        user_str = str(user.id)

        if chat_str not in data or user_str not in data[chat_str].get("warns", {}) or not data[chat_str]["warns"][user_str]:
            await event.edit("❌ У пользователя нет предупреждений")
            return

        data[chat_str]["warns"][user_str].pop()
        save_data(data)

        current_time = time.time()
        active_warns = [w for w in data[chat_str]["warns"][user_str] if not w.get("until") or w["until"] > current_time]
        current = len(active_warns)

        name = f"@{user.username}" if user.username else user.first_name
        await event.edit(f"✅ Снято предупреждение у {name} ({current}/3)")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.warns'))
    async def warns_handler(event):
        user = await get_user(event)
        if not user:
            await event.edit("❌ Ответьте на сообщение или укажите @username")
            return

        data = load_data()
        chat_str = str(event.chat_id)
        user_str = str(user.id)

        if chat_str not in data or user_str not in data[chat_str].get("warns", {}) or not data[chat_str]["warns"][user_str]:
            await event.edit("❌ У пользователя нет предупреждений")
            return

        warns = data[chat_str]["warns"][user_str]
        name = f"@{user.username}" if user.username else user.first_name

        text = f"📋 **Предупреждения {name}:**\n\n"
        current_time = time.time()
        active = 0

        for i, w in enumerate(warns, 1):
            date = datetime.fromtimestamp(w["timestamp"]).strftime("%d.%m.%Y %H:%M")
            status = ""
            if w.get("until") and w["until"] <= current_time:
                status = " ⏰ (истек)"
            elif w.get("until"):
                time_left = w["until"] - current_time
                status = f" 🕒 (осталось: {format_time(time_left)})"
                active += 1
            else:
                status = " ♾️ (бессрочно)"
                active += 1
            text += f"{i}. {date} - {w['reason']}{status}\n"

        text += f"\n📊 Активных предупреждений: {active}"
        await event.edit(text)
