import io
import requests


class UploaderModule:
    def __init__(self, kernel):
        self.kernel = kernel
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
            file_bytes = await self.kernel.client.download_media(reply.media, bytes)
            if not file_bytes:
                await event.edit("❌ **Не удалось скачать файл**")
                return None

            file = io.BytesIO(file_bytes)
            file.name = "file"

            if reply.document:
                for attr in reply.document.attributes:
                    if hasattr(attr, "file_name"):
                        file.name = attr.file_name
                        break
                if file.name == "file":
                    file.name = f"file_{reply.id}"
            else:
                file.name = f"file_{reply.id}.jpg"
        else:
            file = io.BytesIO(reply.raw_text.encode("utf-8"))
            file.name = "text.txt"

        return file


def register(kernel):
    uploader = UploaderModule(kernel)

    @kernel.register_command("catbox")
    async def catbox_handler(event):
        await event.edit(uploader.uploading_text)
        file = await uploader.get_file(event)
        if not file:
            return

        try:
            response = requests.post(
                "https://catbox.moe/user/api.php",
                files={"fileToUpload": file},
                data={"reqtype": "fileupload"},
            )
            if response.ok:
                await event.edit(uploader.uploaded_text.format(response.text.strip()))
            else:
                await event.edit(uploader.error_text.format(response.status_code))
        except Exception as e:
            await uploader.kernel.handle_error(e, source="catbox_handler", event=event)
            await event.edit(uploader.error_text.format(str(e)))

    @kernel.register_command("envs")
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
            await uploader.kernel.handle_error(e, source="envs_handler", event=event)
            await event.edit(uploader.error_text.format(str(e)))

    @kernel.register_command("kappa")
    async def kappa_handler(event):
        await event.edit(uploader.uploading_text)
        file = await uploader.get_file(event)
        if not file:
            return

        try:
            response = requests.post(
                "https://kappa.lol/api/upload", files={"file": file}
            )
            if response.ok:
                data = response.json()
                url = f"https://kappa.lol/{data['id']}"
                await event.edit(uploader.uploaded_text.format(url))
            else:
                await event.edit(uploader.error_text.format(response.status_code))
        except Exception as e:
            await uploader.kernel.handle_error(e, source="kappa_handler", event=event)
            await event.edit(uploader.error_text.format(str(e)))

    @kernel.register_command("0x0")
    async def oxo_handler(event):
        await event.edit(uploader.uploading_text)
        file = await uploader.get_file(event)
        if not file:
            return

        try:
            response = requests.post(
                "https://0x0.st", files={"file": file}, data={"secret": True}
            )
            if response.ok:
                await event.edit(uploader.uploaded_text.format(response.text.strip()))
            else:
                await event.edit(uploader.error_text.format(response.status_code))
        except Exception as e:
            await uploader.kernel.handle_error(e, source="oxo_handler", event=event)
            await event.edit(uploader.error_text.format(str(e)))

    @kernel.register_command("x0")
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
            await uploader.kernel.handle_error(e, source="x0_handler", event=event)
            await event.edit(uploader.error_text.format(str(e)))

    @kernel.register_command("tmpfiles")
    async def tmpfiles_handler(event):
        await event.edit(uploader.uploading_text)
        file = await uploader.get_file(event)
        if not file:
            return

        try:
            response = requests.post(
                "https://tmpfiles.org/api/v1/upload", files={"file": file}
            )
            if response.ok:
                data = response.json()
                url = data["data"]["url"]
                await event.edit(uploader.uploaded_text.format(url))
            else:
                await event.edit(uploader.error_text.format(response.status_code))
        except Exception as e:
            await uploader.kernel.handle_error(
                e, source="tmpfiles_handler", event=event
            )
            await event.edit(uploader.error_text.format(str(e)))

    @kernel.register_command("pomf")
    async def pomf_handler(event):
        await event.edit(uploader.uploading_text)
        file = await uploader.get_file(event)
        if not file:
            return

        try:
            response = requests.post(
                "https://pomf.lain.la/upload.php", files={"files[]": file}
            )
            if response.ok:
                data = response.json()
                url = data["files"][0]["url"]
                await event.edit(uploader.uploaded_text.format(url))
            else:
                await event.edit(uploader.error_text.format(response.status_code))
        except Exception as e:
            await uploader.kernel.handle_error(e, source="pomf_handler", event=event)
            await event.edit(uploader.error_text.format(str(e)))

    @kernel.register_command("bash")
    async def bash_handler(event):
        await event.edit(uploader.uploading_text)
        file = await uploader.get_file(event)
        if not file:
            return

        try:
            response = requests.put("https://bashupload.com", data=file.read())
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
            await uploader.kernel.handle_error(e, source="bash_handler", event=event)
            await event.edit(uploader.error_text.format(str(e)))

    @kernel.register_command("upload")
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
