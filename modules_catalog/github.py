import aiohttp
from telethon import events

async def github_api(endpoint):
    url = f'https://api.github.com{endpoint}'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                return await resp.json()
            return None

def register(bot):
    @bot.on(events.NewMessage(outgoing=True, pattern=r'^\.github\s+repo\s+(.+)'))
    async def github_repo(event):
        query = event.pattern_match.group(1).strip()
        await event.edit('🔍 Поиск репозитория...')
        
        data = await github_api(f'/search/repositories?q={query}&sort=stars&per_page=1')
        
        if not data or not data.get('items'):
            await event.edit('❌ Репозиторий не найден')
            return
        
        repo = data['items'][0]
        msg = f"📦 **{repo['full_name']}**\n\n"
        msg += f"{repo.get('description', 'Нет описания')}\n\n"
        msg += f"⭐ Stars: {repo['stargazers_count']}\n"
        msg += f"🍴 Forks: {repo['forks_count']}\n"
        msg += f"📝 Language: {repo.get('language', 'N/A')}\n"
        msg += f"🔗 {repo['html_url']}"
        
        await event.edit(msg)
    
    @bot.on(events.NewMessage(outgoing=True, pattern=r'^\.github\s+user\s+(.+)'))
    async def github_user(event):
        username = event.pattern_match.group(1).strip()
        await event.edit('🔍 Поиск пользователя...')
        
        data = await github_api(f'/users/{username}')
        
        if not data or 'login' not in data:
            await event.edit('❌ Пользователь не найден')
            return
        
        msg = f"👤 **{data['login']}**\n"
        if data.get('name'):
            msg += f"{data['name']}\n"
        msg += f"\n{data.get('bio', '')}\n\n"
        msg += f"📦 Repos: {data['public_repos']}\n"
        msg += f"👥 Followers: {data['followers']}\n"
        msg += f"📍 Location: {data.get('location', 'N/A')}\n"
        msg += f"🔗 {data['html_url']}"
        
        await event.edit(msg)
