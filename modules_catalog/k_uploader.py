# порт на MCUBFB
# идея @kmodules
# requires: telethon, requests, json
from telethon import events
import io
import requests
import json

class UploaderModule:
    def __init__(self):
        self.uploading_text = "⚡ **Загружаю файл...**"
        self.reply_to_file_text = "❌ **Ответьте на файл!**"
        self.uploaded_text = "❤️ **Файл загружен!**\n\n🔥 **URL:** `{}`"
        self.error_text = "❌ **Ошибка при загрузке:** {}"

    async def get_file(self, event):
        reply = await event.get_reply_message()
        if not reply:
            await event.edit(self.reply_to_file_text)
            return None

        if reply.media:
            file_bytes = await event.client.download_media(reply.media, bytes)
            if not file_bytes:
                await event.edit("❌ **Не удалось скачать файл**")
                return None

            file = io.BytesIO(file_bytes)
            if reply.document:
                file.name = reply.document.attributes[0].file_name if reply.document.attributes else f"file_{reply.id}"
            else:
                file.name = f"file_{reply.id}.jpg"
        else:
            file = io.BytesIO(reply.raw_text.encode('utf-8'))
            file.name = "text.txt"

        return file

def register(client):
    uploader = UploaderModule()

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.catbox$'))
    async def catbox_handler(event):
        await event.edit(uploader.uploading_text)
        file = await uploader.get_file(event)
        if not file:
            return

        try:
            response = requests.post(
                "https://catbox.moe/user/api.php",
                files={"fileToUpload": file},
                data={"reqtype": "fileupload"}
            )
            if response.ok:
                await event.edit(uploader.uploaded_text.format(response.text.strip()))
            else:
                await event.edit(uploader.error_text.format(response.status_code))
        except Exception as e:
            await event.edit(uploader.error_text.format(str(e)))

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.envs$'))
    async def envs_handler(event):
        await event.edit(uploader.uploading_text)
        file = await uploader.get_file(event)
        if not file:
            return

        try:
            response = requests.post("https://envs.sh", files={"file": file})
            if response.ok:
                await event.edit(uploader.uploaded_text.format(response.text.strip()))
            else:
                await event.edit(uploader.error_text.format(response.status_code))
        except Exception as e:
            await event.edit(uploader.error_text.format(str(e)))

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.kappa$'))
    async def kappa_handler(event):
        await event.edit(uploader.uploading_text)
        file = await uploader.get_file(event)
        if not file:
            return

        try:
            response = requests.post("https://kappa.lol/api/upload", files={"file": file})
            if response.ok:
                data = response.json()
                url = f"https://kappa.lol/{data['id']}"
                await event.edit(uploader.uploaded_text.format(url))
            else:
                await event.edit(uploader.error_text.format(response.status_code))
        except Exception as e:
            await event.edit(uploader.error_text.format(str(e)))

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.0x0$'))
    async def oxo_handler(event):
        await event.edit(uploader.uploading_text)
        file = await uploader.get_file(event)
        if not file:
            return

        try:
            response = requests.post(
                "https://0x0.st",
                files={"file": file},
                data={"secret": True}
            )
            if response.ok:
                await event.edit(uploader.uploaded_text.format(response.text.strip()))
            else:
                await event.edit(uploader.error_text.format(response.status_code))
        except Exception as e:
            await event.edit(uploader.error_text.format(str(e)))

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.x0$'))
    async def x0_handler(event):
        await event.edit(uploader.uploading_text)
        file = await uploader.get_file(event)
        if not file:
            return

        try:
            response = requests.post("https://x0.at", files={"file": file})
            if response.ok:
                await event.edit(uploader.uploaded_text.format(response.text.strip()))
            else:
                await event.edit(uploader.error_text.format(response.status_code))
        except Exception as e:
            await event.edit(uploader.error_text.format(str(e)))

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.tmpfiles$'))
    async def tmpfiles_handler(event):
        await event.edit(uploader.uploading_text)
        file = await uploader.get_file(event)
        if not file:
            return

        try:
            response = requests.post(
                "https://tmpfiles.org/api/v1/upload",
                files={"file": file}
            )
            if response.ok:
                data = response.json()
                url = data["data"]["url"]
                await event.edit(uploader.uploaded_text.format(url))
            else:
                await event.edit(uploader.error_text.format(response.status_code))
        except Exception as e:
            await event.edit(uploader.error_text.format(str(e)))

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.pomf$'))
    async def pomf_handler(event):
        await event.edit(uploader.uploading_text)
        file = await uploader.get_file(event)
        if not file:
            return

        try:
            response = requests.post(
                "https://pomf.lain.la/upload.php",
                files={"files[]": file}
            )
            if response.ok:
                data = response.json()
                url = data["files"][0]["url"]
                await event.edit(uploader.uploaded_text.format(url))
            else:
                await event.edit(uploader.error_text.format(response.status_code))
        except Exception as e:
            await event.edit(uploader.error_text.format(str(e)))

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.bash$'))
    async def bash_handler(event):
        await event.edit(uploader.uploading_text)
        file = await uploader.get_file(event)
        if not file:
            return

        try:
            response = requests.put(
                "https://bashupload.com",
                data=file.read()
            )
            if response.ok:
                urls = [line for line in response.text.split("\n") if "wget" in line]
                if urls:
                    url = urls[0].split()[-1]
                    await event.edit(uploader.uploaded_text.format(url))
                else:
                    await event.edit(uploader.error_text.format("Не удалось найти URL"))
            else:
                await event.edit(uploader.error_text.format(response.status_code))
        except Exception as e:
            await event.edit(uploader.error_text.format(str(e)))

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.upload$'))
    async def upload_handler(event):
        help_text = """
📤 **Доступные сервисы для загрузки:**

`.catbox` - catbox.moe
`.envs` - envs.sh
`.kappa` - kappa.lol
`.0x0` - 0x0.st
`.x0` - x0.at
`.tmpfiles` - tmpfiles.org
`.pomf` - pomf.lain.la
`.bash` - bashupload.com

**Использование:** Ответьте на файл командой и файл будет загружен.
"""
        await event.edit(help_text)
