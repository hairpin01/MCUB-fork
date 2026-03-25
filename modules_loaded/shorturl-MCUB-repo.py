# author: @Mitrichq
# version: 1.0.1
# description: сокращение ссылок через различные сервисы
# requires: aiohttp

import aiohttp


def register(kernel):
    client = kernel.client

    async def shorten_tinyurl(url):
        # сокращение через tinyurl
        api_url = f"http://tinyurl.com/api-create.php?url={url}"
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as resp:
                if resp.status == 200:
                    return await resp.text()
        return None

    async def shorten_isgd(url):
        # сокращение через is.gd
        api_url = f"https://is.gd/create.php?format=simple&url={url}"
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as resp:
                if resp.status == 200:
                    return await resp.text()
        return None

    @kernel.register_command("short")
    # сокращение ссылки (tinyurl)
    async def shorturl_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await event.edit("⛈️ Использование: .short [сервис] ссылка")
            return

        if len(args) == 2:
            service = "tinyurl"
            url = args[1]
        else:
            service = args[1].lower()
            url = args[2]

        if service not in ["tinyurl", "isgd"]:
            await event.edit("⛈️ Неизвестный сервис\n\nДоступные: tinyurl, isgd")
            return

        await event.edit("🔗 Сокращение ссылки...")

        try:
            if service == "tinyurl":
                short = await shorten_tinyurl(url)
            else:
                short = await shorten_isgd(url)

            if short:
                await event.edit(
                    f"✅ **Сокращенная ссылка:**\n\n`{short}`\n\n📎 Оригинал: {url}"
                )
            else:
                await event.edit("⛈️ Не удалось сократить ссылку")
        except Exception as e:
            await event.edit(f"⛈️ Ошибка: {str(e)}")
