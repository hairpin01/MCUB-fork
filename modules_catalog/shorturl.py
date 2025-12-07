# requires: aiohttp
import aiohttp
from telethon import events

async def shorten_tinyurl(url):
    api_url = f'http://tinyurl.com/api-create.php?url={url}'
    async with aiohttp.ClientSession() as session:
        async with session.get(api_url) as resp:
            if resp.status == 200:
                return await resp.text()
    return None

async def shorten_isgd(url):
    api_url = f'https://is.gd/create.php?format=simple&url={url}'
    async with aiohttp.ClientSession() as session:
        async with session.get(api_url) as resp:
            if resp.status == 200:
                return await resp.text()
    return None

def register(client):
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.short(?:\s+(\w+))?\s+(.+)'))
    async def shorturl_handler(event):
        service = event.pattern_match.group(1) or 'tinyurl'
        url = event.pattern_match.group(2).strip()
        
        await event.edit('🔗 Сокращение ссылки...')
        
        try:
            if service.lower() == 'tinyurl':
                short = await shorten_tinyurl(url)
            elif service.lower() == 'isgd':
                short = await shorten_isgd(url)
            else:
                await event.edit(f'❌ Неизвестный сервис\n\nДоступные: tinyurl, isgd')
                return
            
            if short:
                await event.edit(f'✅ **Сокращенная ссылка:**\n\n`{short}`\n\n📎 Оригинал: {url}')
            else:
                await event.edit('❌ Не удалось сократить ссылку')
        except Exception as e:
            await event.edit(f'❌ Ошибка: {str(e)}')
