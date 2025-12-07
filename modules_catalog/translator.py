import aiohttp
from telethon import events

async def translate_text(text, target='ru', source='auto'):
    url = 'https://translate.googleapis.com/translate_a/single'
    params = {
        'client': 'gtx',
        'sl': source,
        'tl': target,
        'dt': 't',
        'q': text
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                return ''.join([item[0] for item in data[0] if item[0]])
            return None

def register(bot):
    @bot.on(events.NewMessage(outgoing=True, pattern=r'^\.tr(?:\s+([a-z]{2}))?(?:\s+(.+))?'))
    async def translate(event):
        target = event.pattern_match.group(1) or 'ru'
        text = event.pattern_match.group(2)
        
        if not text and event.is_reply:
            reply = await event.get_reply_message()
            text = reply.text
        
        if not text:
            await event.edit('❌ Укажите текст или ответьте на сообщение\n\nПример: .tr en Hello')
            return
        
        await event.edit('🔄 Перевожу...')
        
        result = await translate_text(text, target)
        
        if not result:
            await event.edit('❌ Ошибка перевода')
            return
        
        msg = f'🌐 **Перевод ({target}):**\n\n{result}'
        await event.edit(msg)
    
    @bot.on(events.NewMessage(outgoing=True, pattern=r'^\.tren(?:\s+(.+))?'))
    async def translate_en(event):
        text = event.pattern_match.group(1)
        
        if not text and event.is_reply:
            reply = await event.get_reply_message()
            text = reply.text
        
        if not text:
            await event.edit('❌ Укажите текст или ответьте на сообщение')
            return
        
        await event.edit('🔄 Перевожу...')
        result = await translate_text(text, 'en')
        
        if result:
            await event.edit(f'🌐 **Translation (en):**\n\n{result}')
        else:
            await event.edit('❌ Ошибка перевода')
