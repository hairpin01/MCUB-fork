# ----------------------------------------------------------
#  /\_/\  🌐 This module was loaded through https://t.me/hikkamods_bot
# ( o.o )  🔓 Not licensed.
#  > ^ <   ⚠️ Owner of heta.hikariatama.ru doesn't take any responsibilities or intellectual property rights regarding this script
# ----------------------------------------------------------
# github: https://github.com/hairpin01/repo-MCUB-fork/liber/
# Channel: https://t.me/LinuxGram2
# -------------------- Meta data ---------------------------
# requires: requests, pillow
# author: @KeyZenD && port: @Hairpin00
# version: 1.0.0
# description: ru: Генератор и читатель QR-кодов / en: QR code generator and reader
# ----------------------- End ------------------------------


import asyncio
from io import BytesIO

from PIL import Image
import requests
from telethon.tl.types import DocumentAttributeFilename


def register(kernel):

    @kernel.register_command("makeqr")
    # .makeqr <text> - generate QR code | .makeqr .file <text> - generate QR code as file |  Reply to message with .makeqr - generate QR from replied text
    async def makeqr_handler(event):
        try:
            # Get arguments and reply
            text = (
                " ".join(event.text.split()[1:]) if len(event.text.split()) > 1 else ""
            )
            reply = await event.get_reply_message()
            file = False

            # Parse arguments
            if not text or text.lower().startswith(".file"):
                if text and text.lower() == ".file":
                    file = True
                if not reply or not reply.text:
                    await event.edit(
                        "<b>Нет текста для кодирования!</b>", parse_mode="html"
                    )
                    return
                text = reply.text
            else:
                if text.lower().startswith(".file"):
                    file = True
                    text = text[5:].strip()

            # Generate QR code
            url = "https://api.qrserver.com/v1/create-qr-code/?data={}&size=512x512&charset-source=UTF-8&charset-target=UTF-8&ecc=L&color=0-0-0&bgcolor=255-255-255&margin=1&qzone=1&format=png"

            # Use async requests
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, lambda: requests.get(url.format(text), stream=True)
            )

            qrcode = BytesIO()
            qrcode.name = "qr.png" if file else "qr.webp"

            # Process image
            img = await loop.run_in_executor(
                None, lambda: Image.open(BytesIO(response.content))
            )
            await loop.run_in_executor(None, lambda: img.save(qrcode))
            qrcode.seek(0)

            await event.delete()

            # Send file
            await kernel.client.send_file(
                event.chat_id,
                qrcode,
                reply_to=reply.id if reply else None,
                force_document=file,
            )

        except Exception as e:
            await kernel.handle_error(e, source="makeqr", event=event)
            await event.edit("❌ Ошибка при генерации QR-кода", parse_mode="html")

    @kernel.register_command("readqr")
    # .readqr - read QR from replied image | .readqr <image attached> - read QR from attached image
    async def readqr_handler(event):
        try:
            # Check attached media
            ok = await _check_media(event)
            if not ok:
                # Check replied message
                reply = await event.get_reply_message()
                ok = await _check_media(reply) if reply else False

            if not ok:
                text = (
                    "<b>Это не изображение!</b>"
                    if reply
                    else "<b>Нечего не передано!</b>"
                )
                await event.edit(text, parse_mode="html")
                return

            # Download and process image
            file = BytesIO()
            file.name = "qr.png"

            media_data = await kernel.client.download_media(ok)
            if isinstance(media_data, bytes):
                img_data = media_data
            else:
                with open(media_data, "rb") as f:
                    img_data = f.read()

            # Process image
            loop = asyncio.get_event_loop()
            img = await loop.run_in_executor(
                None, lambda: Image.open(BytesIO(img_data))
            )
            await loop.run_in_executor(None, lambda: img.save(file))
            file.seek(0)

            # Read QR code
            url = "https://api.qrserver.com/v1/read-qr-code/?outputformat=json"

            response = await loop.run_in_executor(
                None, lambda: requests.post(url, files={"file": file.getvalue()})
            )

            data = response.json()
            text = (
                data[0]["symbol"][0]["data"]
                if data[0]["symbol"][0]["data"]
                else "<b>Невозможно распознать или QR пуст!</b>"
            )

            await event.edit(text, parse_mode="html")

        except Exception as e:
            await kernel.handle_error(e, source="readqr", event=event)
            await event.edit("❌ Ошибка при чтении QR-кода", parse_mode="html")


async def _check_media(msg):
    """Check if message contains valid image for QR reading"""
    if msg and msg.media:
        if msg.photo:
            return msg.photo
        elif msg.document:
            # Check if it's a supported image
            attrs = msg.document.attributes
            if any(
                attr for attr in attrs if isinstance(attr, DocumentAttributeFilename)
            ):
                # Check file type by extension
                filename_attr = next(
                    (
                        attr
                        for attr in attrs
                        if isinstance(attr, DocumentAttributeFilename)
                    ),
                    None,
                )
                if filename_attr:
                    filename = filename_attr.file_name.lower()
                    if any(
                        filename.endswith(ext)
                        for ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp"]
                    ):
                        return msg.document
            # Skip unsupported types
            return False
    return False
