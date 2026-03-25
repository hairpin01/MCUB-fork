from .. import loader, utils
import io
import requests
import json

# meta developer: @kmodules
__version__ = (1, 1, 1)

@loader.tds
class UploaderMod(loader.Module):
    """Module for uploading files to various file hosting services"""

    strings = {
        "name": """K:Uploader""",
        "uploading": "⚡ <b>Uploading file...</b>",
        "reply_to_file": "❌ <b>Reply to file!</b>",
        "uploaded": "❤️ <b>File uploaded!</b>\n\n🔥 <b>URL:</b> <code>{}</code>",
        "error": "❌ <b>Error while uploading: {}</b>"
    }

    strings_ru = {
        "name": """K:Uploader""", 
        "uploading": "⚡ <b>Загружаю файл...</b>",
        "reply_to_file": "❌ <b>Ответьте на файл!</b>", 
        "uploaded": "❤️ <b>Файл загружен!</b>\n\n🔥 <b>URL:</b> <code>{}</code>",
        "error": "❌ <b>Ошибка при загрузке: {}</b>"
    }

    async def _get_file(self, message):
        """Helper to get file from message"""
        reply = await message.get_reply_message()
        if not reply:
            await utils.answer(message, self.strings["reply_to_file"])
            return None
            
        if reply.media:
            file = io.BytesIO(await self.client.download_media(reply.media, bytes))
            if hasattr(reply.media, "document"):
                file.name = reply.file.name or f"file_{reply.file.id}"
            else:
                file.name = f"file_{reply.id}.jpg"
        else:
            file = io.BytesIO(bytes(reply.raw_text, "utf-8"))
            file.name = "text.txt"
            
        return file

    async def catboxcmd(self, message):
        """Upload file to catbox.moe"""
        await utils.answer(message, self.strings["uploading"])
        file = await self._get_file(message)
        if not file:
            return
        
        try:
            response = requests.post(
                "https://catbox.moe/user/api.php",
                files={"fileToUpload": file},
                data={"reqtype": "fileupload"}
            )
            if response.ok:
                await utils.answer(message, self.strings["uploaded"].format(response.text))
            else:
                await utils.answer(message, self.strings["error"].format(response.status_code))
        except Exception as e:
            await utils.answer(message, self.strings["error"].format(str(e)))

    async def envscmd(self, message):
        """Upload file to envs.sh"""
        await utils.answer(message, self.strings["uploading"])
        file = await self._get_file(message)
        if not file:
            return
            
        try:
            response = requests.post("https://envs.sh", files={"file": file})
            if response.ok:
                await utils.answer(message, self.strings["uploaded"].format(response.text))
            else:
                await utils.answer(message, self.strings["error"].format(response.status_code))
        except Exception as e:
            await utils.answer(message, self.strings["error"].format(str(e)))

    async def kappacmd(self, message): 
        """Upload file to kappa.lol"""
        await utils.answer(message, self.strings["uploading"])
        file = await self._get_file(message)
        if not file:
            return
            
        try:
            response = requests.post("https://kappa.lol/api/upload", files={"file": file})
            if response.ok:
                data = response.json()
                url = f"https://kappa.lol/{data['id']}"
                await utils.answer(message, self.strings["uploaded"].format(url))
            else:
                await utils.answer(message, self.strings["error"].format(response.status_code))
        except Exception as e:
            await utils.answer(message, self.strings["error"].format(str(e)))

    async def oxocmd(self, message):
        """Upload file to 0x0.st"""
        await utils.answer(message, self.strings["uploading"])
        file = await self._get_file(message)
        if not file:
            return
            
        try:
            response = requests.post(
                "https://0x0.st",
                files={"file": file},
                data={"secret": True}
            )
            if response.ok:
                await utils.answer(message, self.strings["uploaded"].format(response.text))
            else:
                await utils.answer(message, self.strings["error"].format(response.status_code))
        except Exception as e:
            await utils.answer(message, self.strings["error"].format(str(e)))

    async def x0cmd(self, message):
        """Upload file to x0.at"""
        await utils.answer(message, self.strings["uploading"])
        file = await self._get_file(message)
        if not file:
            return
            
        try:
            response = requests.post("https://x0.at", files={"file": file})
            if response.ok:
                await utils.answer(message, self.strings["uploaded"].format(response.text))
            else:
                await utils.answer(message, self.strings["error"].format(response.status_code))
        except Exception as e:
            await utils.answer(message, self.strings["error"].format(str(e)))
            
    async def tmpfilescmd(self, message):
        """Upload file to tmpfiles.org"""
        await utils.answer(message, self.strings["uploading"])
        file = await self._get_file(message)
        if not file:
            return

        try:
            response = requests.post(
                "https://tmpfiles.org/api/v1/upload",
                files={"file": file}
            )
            if response.ok:
                data = json.loads(response.text)
                url = data["data"]["url"]
                await utils.answer(message, self.strings["uploaded"].format(url))
            else:
                await utils.answer(message, self.strings["error"].format(response.status_code))
        except Exception as e:
            await utils.answer(message, self.strings["error"].format(str(e)))

    async def pomfcmd(self, message):
        """Upload file to pomf.lain.la"""
        await utils.answer(message, self.strings["uploading"])
        file = await self._get_file(message)
        if not file:
            return

        try:
            response = requests.post(
                "https://pomf.lain.la/upload.php",
                files={"files[]": file}
            )
            if response.ok:
                data = json.loads(response.text)
                url = data["files"][0]["url"]
                await utils.answer(message, self.strings["uploaded"].format(url))
            else:
                await utils.answer(message, self.strings["error"].format(response.status_code))
        except Exception as e:
            await utils.answer(message, self.strings["error"].format(str(e)))

    async def bashcmd(self, message):
        """Upload file to bashupload.com"""
        await utils.answer(message, self.strings["uploading"])
        file = await self._get_file(message)
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
                    await utils.answer(message, self.strings["uploaded"].format(url))
                else:
                    await utils.answer(message, self.strings["error"].format("Could not find URL"))
            else:
                await utils.answer(message, self.strings["error"].format(response.status_code))
        except Exception as e:
            await utils.answer(message, self.strings["error"].format(str(e)))
