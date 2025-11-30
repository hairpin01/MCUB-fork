from telethon import events
import time

def register(client):
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.id$'))
    async def get_id(event):
        user_id = event.sender_id
        chat_id = event.chat_id
        await event.edit(f'👤 Ваш ID: `{user_id}`\n💬 ID чата: `{chat_id}`')
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.calc'))
    async def calc(event):
        expression = event.text[6:].strip()
        if not expression:
            await event.edit('❌ Введите пример: `.calc 2+2`')
            return
        
        try:
            allowed = "0123456789+-*/()., "
            if all(c in allowed for c in expression):
                result = eval(expression.replace(',', '.'))
                await event.edit(f'🧮 `{expression}` = `{result}`')
            else:
                await event.edit('❌ Разрешены только цифры и +, -, *, /, ()')
        except:
            await event.edit('❌ Ошибка вычисления')

