from telethon import events
import random

def register(client):
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.dice$'))
    async def dice(event):
        result = random.randint(1, 6)
        await event.edit(f'🎲 Выпало: {result}')
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.flip$'))
    async def flip(event):
        result = random.choice(['Орёл 🦅', 'Решка 💰'])
        await event.edit(result)
