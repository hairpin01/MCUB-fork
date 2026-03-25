# requires: aiofiles
# scope: hikka_only
# meta name: ReadFile
# meta developer: @ItzNeedlemouseNB
# meta version: 1.0.0

import os
import tempfile

import aiofiles

from telethon.tl.types import Message

from .. import loader, utils


@loader.tds
class ReadFileMod(loader.Module):
    strings = {
        "name": "ReadFile",
        "developer": "<b>Разработчик:</b> @ItzNeedlemouseNB",
        "desc": "<b>Модуль для чтения текстовых файлов по пути или из ответа на документ с постраничным просмотром.</b>",
        "no_input": "<b>Укажи путь к текстовому файлу или ответь на документ.</b>",
        "downloading": "<b>Скачиваю файл...</b>",
        "not_found": "<b>Файл не найден.</b>",
        "not_file": "<b>Указанный путь не является файлом.</b>",
        "empty": "<b>Файл пуст.</b>",
        "binary": "<b>Похоже, это не текстовый файл или кодировка не поддерживается.</b>",
        "too_large": "<b>Файл слишком большой для одного сообщения, открываю постранично.</b>",
        "read_error": "<b>Не удалось прочитать файл:</b> <code>{}</code>",
        "caption": "<b>Содержимое файла:</b> <code>{}</code>",
        "page_info": "<b>Страница:</b> <code>{}/{}</code>",
        "close": "✖ Закрыть",
        "prev": "⬅ Назад",
        "next": "Вперёд ➡",
    }

    strings_ru = strings

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "max_message_chars",
                3500,
                lambda: "Максимум символов для вывода в сообщении",
                validator=loader.validators.Integer(minimum=256, maximum=15000),
            ),
            loader.ConfigValue(
                "max_read_bytes",
                1048576,
                lambda: "Максимальный размер читаемого файла в байтах",
                validator=loader.validators.Integer(minimum=1024, maximum=10485760),
            ),
            loader.ConfigValue(
                "default_encoding",
                "utf-8",
                lambda: "Кодировка по умолчанию",
                validator=loader.validators.String(min_len=3, max_len=40),
            ),
        )

    async def client_ready(self, client, db):
        self.client = client
        self.db = db

    async def _read_text_file(self, path: str) -> str:
        async with aiofiles.open(path, "rb") as f:
            data = await f.read(self.config["max_read_bytes"] + 1)

        if len(data) > self.config["max_read_bytes"]:
            raise ValueError("limit")

        if not data:
            return ""

        try:
            return data.decode(self.config["default_encoding"])
        except UnicodeDecodeError:
            try:
                return data.decode("utf-8-sig")
            except UnicodeDecodeError:
                try:
                    return data.decode("cp1251")
                except UnicodeDecodeError as e:
                    raise UnicodeDecodeError(e.encoding, e.object, e.start, e.end, e.reason)

    async def _download_reply_file(self, message: Message) -> tuple[str, str]:
        reply = await message.get_reply_message()
        if not reply or not reply.file:
            return None, None

        suffix = ""
        if reply.file.name and "." in reply.file.name:
            suffix = os.path.splitext(reply.file.name)[1]

        fd, temp_path = tempfile.mkstemp(prefix="hikka_rf_", suffix=suffix)
        os.close(fd)

        await utils.answer(message, self.strings("downloading"))
        await reply.download_media(file=temp_path)
        return temp_path, (reply.file.name or os.path.basename(temp_path))

    def _split_text(self, text: str) -> list[str]:
        base_limit = max(256, int(self.config["max_message_chars"]))
        limit = max(256, base_limit // 2)
        chunks = []
        start = 0

        while start < len(text):
            end = min(start + limit, len(text))
            if end < len(text):
                split_pos = text.rfind("\n", start, end)
                if split_pos <= start:
                    split_pos = text.rfind(" ", start, end)
                if split_pos > start:
                    end = split_pos + 1
            chunks.append(text[start:end])
            start = end

        return chunks or [""]

    def _render_page(self, display_name: str, pages: list[str], index: int) -> str:
        total = len(pages)
        safe_index = max(0, min(index, total - 1))
        escaped_name = utils.escape_html(display_name)
        escaped_text = utils.escape_html(pages[safe_index])
        return (
            f"{self.strings('caption').format(escaped_name)}\n"
            f"{self.strings('page_info').format(safe_index + 1, total)}\n"
            f"<pre>{escaped_text}</pre>"
        )

    def _build_markup(self, display_name: str, pages: list[str], index: int) -> list[list[dict]]:
        total = len(pages)
        if total <= 1:
            return [[{"text": self.strings("close"), "action": "close"}]]

        safe_index = max(0, min(index, total - 1))
        nav_row = []

        if safe_index > 0:
            nav_row.append(
                {
                    "text": self.strings("prev"),
                    "callback": self._page_cb,
                    "args": (display_name, pages, safe_index - 1),
                }
            )

        if safe_index < total - 1:
            nav_row.append(
                {
                    "text": self.strings("next"),
                    "callback": self._page_cb,
                    "args": (display_name, pages, safe_index + 1),
                }
            )

        markup = []
        if nav_row:
            markup.append(nav_row)
        markup.append([{"text": self.strings("close"), "action": "close"}])
        return markup

    async def _page_cb(self, call, display_name: str, pages: list[str], index: int):
        await call.edit(
            self._render_page(display_name, pages, index),
            reply_markup=self._build_markup(display_name, pages, index),
        )

    @loader.command(
        ru_doc="Прочитать текстовый файл по пути или из ответа на документ. Поддерживается постраничный просмотр длинного содержимого.",
        en_doc="Read a text file by path or from a replied document with paginated viewing for long content",
    )
    async def rf(self, message: Message):
        args = utils.get_args_raw(message).strip()
        temp_path = None
        display_name = None

        try:
            if args:
                path = os.path.expanduser(args)
                path = os.path.abspath(path)
                display_name = path
            else:
                temp_path, display_name = await self._download_reply_file(message)
                path = temp_path

            if not path:
                await utils.answer(message, self.strings("no_input"))
                return

            if not os.path.exists(path):
                await utils.answer(message, self.strings("not_found"))
                return

            if not os.path.isfile(path):
                await utils.answer(message, self.strings("not_file"))
                return

            try:
                text = await self._read_text_file(path)
            except ValueError:
                async with aiofiles.open(path, "rb") as f:
                    data = await f.read(self.config["max_read_bytes"])

                try:
                    text = data.decode(self.config["default_encoding"])
                except UnicodeDecodeError:
                    try:
                        text = data.decode("utf-8-sig")
                    except UnicodeDecodeError:
                        try:
                            text = data.decode("cp1251")
                        except UnicodeDecodeError:
                            await utils.answer(message, self.strings("binary"))
                            return

                await utils.answer(message, self.strings("too_large"))
            except UnicodeDecodeError:
                await utils.answer(message, self.strings("binary"))
                return
            except Exception as e:
                await utils.answer(message, self.strings("read_error").format(utils.escape_html(str(e))))
                return

            if not text:
                await utils.answer(message, self.strings("empty"))
                return

            escaped_name = utils.escape_html(display_name)
            escaped_text = utils.escape_html(text)
            limit = max(256, int(self.config["max_message_chars"]))
            page_limit = max(256, limit // 2)

            if len(escaped_text) <= page_limit:
                await utils.answer(
                    message,
                    f"{self.strings('caption').format(escaped_name)}\n<pre>{escaped_text}</pre>",
                )
                return

            pages = self._split_text(text)
            await self.inline.form(
                text=self._render_page(display_name, pages, 0),
                reply_markup=self._build_markup(display_name, pages, 0),
                message=message,
            )
        finally:
            if temp_path and os.path.isfile(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass