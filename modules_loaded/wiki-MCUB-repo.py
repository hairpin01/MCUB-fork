# author: @Mitrichq && @Hairpin00
# version: 1.1.0
# description: поиск информации в Википедии
# requires: aiohttp

import aiohttp
import urllib.parse


def register(kernel):
    client = kernel.client

    # Локализованные строки
    wiki_strings = {
        "ru": {
            "usage": '<tg-emoji emoji-id="5330273431898318607">🌩</tg-emoji> Использование: .wiki [язык] запрос',
            "searching": '<tg-emoji emoji-id="5373236586760651455">⏱️</tg-emoji> Поиск <code>{query}</code>...',
            "article_not_found": "⛈️ Статья не найдена\n\n🔍 Похожие запросы:\n",
            "similar_results": "{i}. {result}\n",
            "nothing_found": '<tg-emoji emoji-id="5330273431898318607">🌩</tg-emoji> Ничего не найдено.',
            "title_prefix": '<tg-emoji emoji-id="5372849966689566579">✈️</tg-emoji> <b>{title}</b>\n\n',
            "extract": "<blockquote>{extract}</blockquote>",
            "link": "\n\n<blockquote>🔗 {url}</blockquote>",
        },
        "en": {
            "usage": '<tg-emoji emoji-id="5330273431898318607">🌩</tg-emoji> Usage: .wiki [language] query',
            "searching": '<tg-emoji emoji-id="5373236586760651455">⏱️</tg-emoji> Searching <code>{query}</code>...',
            "article_not_found": "⛈️ Article not found\n\n🔍 Similar queries:\n",
            "similar_results": "{i}. {result}\n",
            "nothing_found": '<tg-emoji emoji-id="5330273431898318607">🌩</tg-emoji> Nothing found.',
            "title_prefix": '<tg-emoji emoji-id="5372849966689566579">✈️</tg-emoji> <b>{title}</b>\n\n',
            "extract": "<blockquote>{extract}</blockquote>",
            "link": "\n\n<blockquote>🔗 {url}</blockquote>",
        },
    }

    # Функция для получения локализованной строки
    def _(key, **kwargs):
        language = kernel.config.get("language", "ru")
        strings = wiki_strings.get(language, wiki_strings["ru"])
        text = strings.get(key, key)
        return text.format(**kwargs) if kwargs else text

    async def get_wiki_page(query, lang):
        # получение страницы Википедии
        url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(query)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        return await response.json()
        except:
            return None
        return None

    async def search_wiki(query, lang):
        # поиск в Википедии
        url = f"https://{lang}.wikipedia.org/w/api.php"
        params = {"action": "opensearch", "search": query, "limit": 5, "format": "json"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        return await response.json()
        except:
            return None
        return None

    @kernel.register_command("wiki")
    # поиск информации в Википедии
    async def wiki_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await event.edit(_("usage"), parse_mode="html")
            return

        if len(args) == 2:
            lang = "ru"
            query = args[1]
        else:
            if len(args[1]) == 2:
                lang = args[1].lower()
                query = " ".join(args[2:])
            else:
                lang = "ru"
                query = " ".join(args[1:])

        try:
            msg = await event.edit(_("searching", query=query), parse_mode="html")
        except:
            return

        page_data = await get_wiki_page(query, lang)

        if not page_data:
            search_results = await search_wiki(query, lang)

            if search_results and len(search_results) > 1 and search_results[1]:
                text = _("article_not_found")
                for i, res in enumerate(search_results[1], 1):
                    text += _("similar_results", i=i, result=res)
                await msg.edit(text, parse_mode="html")
                return

            if lang != "en":
                page_data = await get_wiki_page(query, "en")

        if not page_data:
            await msg.edit(_("nothing_found"), parse_mode="html")
            return

        title = page_data.get("title", "")
        extract = page_data.get("extract", "")
        url = page_data.get("content_urls", {}).get("desktop", {}).get("page", "")

        result = _("title_prefix", title=title) + _("extract", extract=extract)
        if url:
            result += _("link", url=url)

        if len(result) > 4096:
            result = result[:4000] + "..."

        await msg.edit(result, parse_mode="html")
