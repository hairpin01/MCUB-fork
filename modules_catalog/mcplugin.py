# mcplugin.py - Многофункциональный модуль

import asyncio
import random
import time
import json
import os
from telethon import events

def register(client):
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.dice$'))
    async def dice_handler(event):
        frames = ["🎲 Кубик крутится...", "🎲🎲 Крутится...", "🎲🎲🎲 Крутится..."]
        for frame in frames:
            await event.edit(frame)
            await asyncio.sleep(0.7)
        result = random.randint(1, 6)
        dice_emoji = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"][result - 1]
        await event.edit(f"🎲 Выпало: {dice_emoji} `{result}`")
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.coin$'))
    async def coin_handler(event):
        frames = ["🪙 Монетка в воздухе...", "🪙🪙 Почти упала..."]
        for frame in frames:
            await event.edit(frame)
            await asyncio.sleep(0.8)
        result = random.choice(["Орел 🦅", "Решка 💰"])
        await event.edit(f"🪙 Результат: {result}")
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.roulette$'))
    async def roulette_handler(event):
        frames = ["🔫 Крутим барабан...", "🔫 Щелк...", "🔫🔫 Щелк... щелк...", "🔫🔫🔫 Щелк... щелк... щелк..."]
        for frame in frames:
            await event.edit(frame)
            await asyncio.sleep(1.0)
        if random.randint(1, 6) == 1:
            await event.edit("💥 БАХ! Вы проиграли!")
        else:
            await event.edit("✅ Повезло! Выжили!")
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.slots$'))
    async def slots_handler(event):
        symbols = ["🍒", "🍋", "🍊", "🍇", "🔔", "💎", "7️⃣"]
        await event.edit("🎰 Крутим слоты...")
        for i in range(6):
            slot1, slot2, slot3 = [random.choice(symbols) for _ in range(3)]
            await event.edit(f"🎰 | {slot1} | {slot2} | {slot3} |")
            await asyncio.sleep(0.4)
        result = [random.choice(symbols) for _ in range(3)]
        jackpot = "🎉 ДЖЕКПОТ!" if result[0] == result[1] == result[2] else ""
        await event.edit(f"🎰 | {result[0]} | {result[1]} | {result[2]} | {jackpot}")
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.wheel$'))
    async def wheel_handler(event):
        sectors = ["💰", "🍎", "🍒", "🍋", "🍇", "🔔", "⭐", "💸"]
        await event.edit("🎡️ Колесо крутится...")
        for i in range(5):
            await event.edit(f"🎡️ {random.choice(sectors)}")
            await asyncio.sleep(0.5)
        result = random.choice(sectors)
        text = {"💰": "🎉 ДЖЕКПОТ! Максимальный выигрыш!", "⭐": "✨ Звезда! Отличный результат!", 
                "💸": "💸 Банкрот! Попробуй еще раз!"}.get(result, "🍓 Фрукт! Хороший результат!")
        await event.edit(f"🎡️ Результат: {result}\n\n{text}")
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.random'))
    async def random_handler(event):
        args = event.text[8:].strip().split()
        if len(args) == 2:
            min_val, max_val = int(args[0]), int(args[1])
        elif len(args) == 1:
            min_val, max_val = 1, int(args[0])
        else:
            min_val, max_val = 1, 100
        if min_val > max_val:
            min_val, max_val = max_val, min_val
        result = random.randint(min_val, max_val)
        await event.edit(f"🎰 Случайное число ({min_val}-{max_val}): `{result}`")
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.8ball'))
    async def ball8_handler(event):
        await event.edit("🎱 Магический шар думает...")
        await asyncio.sleep(1.5)
        answers = ["✅ Да", "❌ Нет", "🤔 Возможно", "😎 Определенно да", "😒 Определенно нет", "🤷 Не знаю"]
        await event.edit(f"🎱 Магический шар: {random.choice(answers)}")
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.type'))
    async def type_handler(event):
        args = event.text[6:].strip()
        if not args:
            await event.edit("⌨️ Использование: `.type [текст]`")
            return
        text = ""
        for char in args:
            text += char
            await event.edit(f"⌨️ {text}▌")
            await asyncio.sleep(0.1)
        await event.edit(text)
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.fact$'))
    async def fact_handler(event):
        facts = [
            "🧠 Человеческий мозг содержит около 86 миллиардов нейронов",
            "🐙 У осьминогов три сердца и голубая кровь",
            "🌍 Земля не идеально круглая - она сплюснута у полюсов",
            "🦈 Акулы существуют дольше деревьев",
            "🍯 Мёд никогда не портится",
            "🌙 Луна удаляется от Земли на 3.8 см каждый год",
            "🐧 Пингвины могут прыгать на высоту до 3 метров",
            "🌊 В океане больше исторических артефактов, чем во всех музеях мира"
        ]
        await event.edit(f"💡 {random.choice(facts)}")
