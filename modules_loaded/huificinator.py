__version__ = (1, 3, 0)
# meta developer: @eremod
#
#
# 	.----..----. .----..-.   .-. .----. .----.
# 	| {_  | {}  }| {_  |  `.'  |/  {}  \| {}  \
# 	| {__ | .-. \| {__ | |\ /| |\      /|     /
# 	`----'`-' `-'`----'`-' ` `-' `----' `----'
#
#              	© Copyright 2024
#          	https://t.me/eremod
#
# 🔒      Licensed under the GNU GPLv3
# 🌐 https://www.gnu.org/licenses/gpl-3.0.html
# Original repository: https://github.com/eremeyko/ne_Hikka
from hikkatl.types import Message
from .. import loader, utils
from re import findall


def huify(word):
    # Original repository of Huifier:
    # https://github.com/kefir500/huifier
    # MIT License Copyright (c) 2019 Alexander Gorishnyak
    # See the MIT License for more details: <https://opensource.org/licenses/MIT>
    word = word.lower().strip()
    vowels = "аеёиоуыэюя"
    rules = {
        "а": "я",
        "о": "е",
        "у": "ю",
        "ы": "и",
        "э": "е",
    }
    for letter in word:
        if letter in vowels:
            if letter in rules:
                word = rules[letter] + word[1:]
            break
        else:
            word = word[1:]
    return "Ху" + word if word else "Хуй"


def huify_text(text, with_original=False):
    words = findall(r"\b\w+\b", text)
    huified_words = [huify(word) for word in words]
    result = text
    for original, huified in zip(words, huified_words):
        if with_original:
            result = result.replace(original, f"{original}-{huified}", 1)
        else:
            result = result.replace(original, huified, 1)
    return result


@loader.tds
class Huificator(loader.Module):
    """Хуификатор телеграмма"""

    strings = {"name": "Huificinator", "no_text_error": "Please enter text to huify."}

    strings_ru = {
        "name": "Хуифицинатор",
        "no_text_error": "Пожалуйста, введите текст для хуификации.",
    }

    @loader.command(alias="х", ru_doc="[текст/ответ] — Хуифицирует сообщение")
    async def huify(self, message: Message):
        """[text/reply] — huificate message"""
        reply = await message.get_reply_message()
        if reply and reply.text:
            text = reply.text
            result = huify_text(text)
        else:
            text = utils.get_args_raw(message)
            if not text:
                await utils.answer(message, self.strings["no_text_error"])
                return
            result = huify_text(text, with_original=True)

        await utils.answer(message, result)
