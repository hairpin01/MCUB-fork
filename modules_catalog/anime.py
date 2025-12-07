# requires: aiohttp
import aiohttp
from telethon import events

ANILIST_API = 'https://graphql.anilist.co'

async def search_anime(query):
    gql_query = '''
    query ($search: String) {
      Media (search: $search, type: ANIME) {
        title { romaji english }
        episodes
        status
        averageScore
        description
        coverImage { large }
        siteUrl
      }
    }
    '''
    async with aiohttp.ClientSession() as session:
        async with session.post(ANILIST_API, json={'query': gql_query, 'variables': {'search': query}}) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data['data']['Media']
    return None

async def get_random_anime():
    gql_query = '''
    query ($page: Int) {
      Page (page: $page, perPage: 1) {
        media (type: ANIME, sort: POPULARITY_DESC) {
          title { romaji }
          coverImage { large }
          siteUrl
        }
      }
    }
    '''
    import random
    page = random.randint(1, 100)
    async with aiohttp.ClientSession() as session:
        async with session.post(ANILIST_API, json={'query': gql_query, 'variables': {'page': page}}) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data['data']['Page']['media'][0]
    return None

def register(client):
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.anime\s+(.+)'))
    async def anime_search(event):
        query = event.pattern_match.group(1)
        await event.edit('🔍 Поиск аниме...')
        
        try:
            anime = await search_anime(query)
            if anime:
                title = anime['title']['english'] or anime['title']['romaji']
                desc = anime['description'][:200] + '...' if anime['description'] else 'Нет описания'
                desc = desc.replace('<br>', '\n').replace('<i>', '').replace('</i>', '')
                
                text = f"**{title}**\n\n"
                text += f"📺 Эпизоды: {anime['episodes'] or 'N/A'}\n"
                text += f"⭐ Рейтинг: {anime['averageScore'] or 'N/A'}/100\n"
                text += f"📊 Статус: {anime['status']}\n\n"
                text += f"{desc}\n\n"
                text += f"🔗 [AniList]({anime['siteUrl']})"
                
                await event.delete()
                await client.send_file(event.chat_id, anime['coverImage']['large'], caption=text)
            else:
                await event.edit('❌ Аниме не найдено')
        except Exception as e:
            await event.edit(f'❌ Ошибка: {str(e)}')
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.randomanime$'))
    async def random_anime(event):
        await event.edit('🎲 Случайное аниме...')
        
        try:
            anime = await get_random_anime()
            if anime:
                await event.delete()
                await client.send_file(
                    event.chat_id,
                    anime['coverImage']['large'],
                    caption=f"**{anime['title']['romaji']}**\n\n🔗 [AniList]({anime['siteUrl']})"
                )
            else:
                await event.edit('❌ Ошибка получения аниме')
        except Exception as e:
            await event.edit(f'❌ Ошибка: {str(e)}')
