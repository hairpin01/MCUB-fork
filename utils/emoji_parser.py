import re
import html
from telethon.tl.types import MessageEntityCustomEmoji

class EmojiParser:
    """парсер эмодзи для MCUB"""

    @staticmethod
    def parse_to_entities(text):
        """
        Парсит текст с тегами <emoji> в (текст, entities)

        Пример:
            Вход: "Привет <emoji document_id=123>🔴</emoji>"
            Выход: ("Привет 🔴", [MessageEntityCustomEmoji(...)])
        """
        entities = []
        result = ""
        offset = 0

        pattern = r'<emoji\s+document_id=(\d+)>(.*?)</emoji>'

        for match in re.finditer(pattern, text):

            result += text[offset:match.start()]

            emoji_text = match.group(2)
            result += emoji_text


            entity = MessageEntityCustomEmoji(
                offset=len(result) - len(emoji_text),
                length=len(emoji_text),
                document_id=int(match.group(1))
            )
            entities.append(entity)

            offset = match.end()

        # Добавляем остаток
        result += text[offset:]
        return result, entities

    @staticmethod
    def entities_to_html(text, entities):
        """
        Преобразует сущности сообщения в  HTML

        Пример:
            Вход: "Привет 🔴", [MessageEntityCustomEmoji(...)]
            Выход: "Привет <emoji document_id=123>🔴</emoji>"
        """
        if not entities:
            return html.escape(text)


        sorted_entities = sorted(entities, key=lambda e: e.offset, reverse=True)
        result = text

        for entity in sorted_entities:
            if isinstance(entity, MessageEntityCustomEmoji):

                emoji_text = text[entity.offset:entity.offset + entity.length]

                before = result[:entity.offset]
                after = result[entity.offset + entity.length:]
                result = f"{before}<emoji document_id={entity.document_id}>{emoji_text}</emoji>{after}"

        return html.escape(result)

    @staticmethod
    def is_emoji_tag(text):
        return bool(re.search(r'<emoji\s+document_id=\d+>.*?</emoji>', text))

    @staticmethod
    def extract_emoji_ids(text):
        pattern = r'<emoji\s+document_id=(\d+)>'
        return [int(match) for match in re.findall(pattern, text)]

emoji_parser = EmojiParser()
