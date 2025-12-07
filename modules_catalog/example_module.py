from telethon import events
import random

def register(bot):
    @bot.on(events.NewMessage(outgoing=True, pattern=r'^\.dice$'))
    async def dice(event):
        result = random.randint(1, 6)
        await event.edit(f'🎲 Выпало: {result}')
    
    @bot.on(events.NewMessage(outgoing=True, pattern=r'^\.flip$'))
    async def flip(event):
        result = random.choice(['Орёл 🦅', 'Решка 💰'])
        await event.edit(result)
    
    @bot.on(events.NewMessage(outgoing=True, pattern=r'^\.hello'))
    async def hello(event):
        name = event.text.split(maxsplit=1)[1] if len(event.text.split()) > 1 else 'мир'
        await event.edit(f'👋 Привет, {name}!')
