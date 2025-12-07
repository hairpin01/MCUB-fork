import aiohttp
from telethon import events

async def search_wikipedia(query, lang='ru'):
    url = f'https://{lang}.wikipedia.org/api/rest_v1/page/summary/{query}'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                return await resp.json()
            return None

def register(bot):
    @bot.on(events.NewMessage(outgoing=True, pattern=r'^\.wiki\s+(.+)'))
    async def wiki_search(event):
        query = event.pattern_match.group(1).strip()
        await event.edit('🔍 Поиск в Wikipedia...')
        
        data = await search_wikipedia(query)
        
        if not data or 'title' not in data:
            data = await search_wikipedia(query, 'en')
        
        if not data or 'title' not in data:
            await event.edit('❌ Ничего не найдено')
            return
        
        title = data.get('title', '')
        description = data.get('extract', '')
        url = data.get('content_urls', {}).get('desktop', {}).get('page', '')
        
        msg = f'📖 **{title}**\n\n{description}\n\n🔗 {url}'
        
        if len(msg) > 4096:
            msg = msg[:4090] + '...'
        
        await event.edit(msg)
