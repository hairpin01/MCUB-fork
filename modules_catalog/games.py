from telethon import events
import random
import asyncio

def register(client):
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.dice$'))
    async def dice(event):
        result = random.randint(1, 6)
        dice_emoji = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"][result - 1]
        await event.edit(f'🎲 Выпало: {dice_emoji} ({result})')

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.flip$'))
    async def flip(event):
        result = random.choice(['Орёл 🦅', 'Решка 💰'])
        await event.edit(result)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.roulette$'))
    async def roulette(event):
        msg = await event.edit('🔫 Крутим барабан...')
        await asyncio.sleep(2)
        if random.randint(1, 6) == 1:
            await msg.edit('💥 БАХ! Вы проиграли!')
        else:
            await msg.edit('✅ Повезло! Выжили!')

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.slots$'))
    async def slots(event):
        symbols = ["🍒", "🍋", "🍊", "🍇", "🔔", "💎", "7️⃣"]
        msg = await event.edit('🎰 Крутим слоты...')
        await asyncio.sleep(1)

        result = [random.choice(symbols) for _ in range(3)]
        jackpot = " 🎉 ДЖЕКПОТ!" if result[0] == result[1] == result[2] else ""
        await msg.edit(f'🎰 | {result[0]} | {result[1]} | {result[2]} |{jackpot}')
