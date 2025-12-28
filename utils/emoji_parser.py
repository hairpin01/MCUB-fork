import re
import html
from telethon.tl.types import MessageEntityCustomEmoji

class EmojiParser:
    """Парсер эмодзи для MCUB с улучшенной обработкой"""

    # Предкомпилированные регулярные выражения для производительности
    _EMOJI_TAG_PATTERN = re.compile(
        r'<emoji\s+document_id=(\d+)>(.*?)</emoji>'
    )
    _EMOJI_ID_PATTERN = re.compile(
        r'<emoji\s+document_id=(\d+)>'
    )
    _ALL_EMOJI_TAGS_PATTERN = re.compile(
        r'<emoji\s+[^>]*>.*?</emoji>'
    )

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

        for match in EmojiParser._EMOJI_TAG_PATTERN.finditer(text):
            # Добавляем текст перед тегом
            result += text[offset:match.start()]

            emoji_text = match.group(2)
            result += emoji_text

            # Создаем сущность для кастомного эмодзи
            try:
                # Валидация: проверяем что document_id - число
                doc_id = int(match.group(1))

                # Важно: Telethon использует UTF-16 offsets
                # Преобразуем позицию в строке в UTF-16 позицию
                utf16_offset = len(result[:-len(emoji_text)].encode('utf-16-le')) // 2
                utf16_length = len(emoji_text.encode('utf-16-le')) // 2

                entity = MessageEntityCustomEmoji(
                    offset=utf16_offset,
                    length=utf16_length,
                    document_id=doc_id
                )
                entities.append(entity)
            except (ValueError, TypeError) as e:
                # Если document_id не число, пропускаем этот тег
                continue

            offset = match.end()

        # Добавляем остаток текста после последнего тега
        result += text[offset:]
        return result, entities

    @staticmethod
    def entities_to_html(text, entities):
        """
        Преобразует сущности сообщения в HTML-подобный формат

        Пример:
            Вход: "Привет 🔴", [MessageEntityCustomEmoji(...)]
            Выход: "Привет <emoji document_id=123>🔴</emoji>"
        """
        if not entities:
            return html.escape(text)

        # Сортируем сущности по убыванию offset для правильной вставки
        sorted_entities = sorted(
            entities,
            key=lambda e: e.offset if hasattr(e, 'offset') else 0,
            reverse=True
        )

        # Работаем с UTF-16 позициями
        utf16_text = text.encode('utf-16-le')

        for entity in sorted_entities:
            if isinstance(entity, MessageEntityCustomEmoji):
                # Преобразуем UTF-16 offsets в позиции в строке
                try:
                    # Вычисляем byte offsets
                    byte_start = entity.offset * 2
                    byte_end = (entity.offset + entity.length) * 2

                    # Извлекаем текст эмодзи из UTF-16
                    emoji_bytes = utf16_text[byte_start:byte_end]
                    emoji_text = emoji_bytes.decode('utf-16-le')

                    # Вставляем тег
                    before = text[:entity.offset]
                    after = text[entity.offset + entity.length:]
                    text = f"{before}<emoji document_id={entity.document_id}>{emoji_text}</emoji>{after}"
                except (IndexError, UnicodeDecodeError):
                    # Если что-то пошло не так с позициями, пропускаем эту сущность
                    continue

        return html.escape(text)

    @staticmethod
    def is_emoji_tag(text):
        """Проверяет, содержит ли текст теги эмодзи"""
        return bool(EmojiParser._EMOJI_TAG_PATTERN.search(text))

    @staticmethod
    def extract_emoji_ids(text):
        """Извлекает все document_id из тегов эмодзи"""
        ids = []
        for match in EmojiParser._EMOJI_ID_PATTERN.findall(text):
            try:
                ids.append(int(match))
            except (ValueError, TypeError):
                continue
        return ids

    @staticmethod
    def remove_emoji_tags(text):
        """
        Удаляет теги эмодзи, оставляя только текст-заполнитель

        Пример:
            Вход: "Привет <emoji document_id=123>🔴</emoji>"
            Выход: "Привет 🔴"
        """
        return EmojiParser._ALL_EMOJI_TAGS_PATTERN.sub(
            lambda m: m.group(0).split('>', 1)[1].rsplit('<', 1)[0] if '>' in m.group(0) and '<' in m.group(0) else '',
            text
        )

    @staticmethod
    def extract_custom_emoji_entities(message):
        """
        Извлекает кастомные эмодзи из полученного сообщения

        Пример использования:
            async for message in client.iter_messages(chat):
                emoji_entities = EmojiParser.extract_custom_emoji_entities(message)
        """
        if not message or not message.entities:
            return []

        return [
            entity for entity in message.entities
            if isinstance(entity, MessageEntityCustomEmoji)
        ]

    @staticmethod
    def validate_emoji_content(emoji_text):
        """
        Проверяет, является ли текст валидным заполнителем для кастомного эмодзи

        Telegram требует чтобы внутри тега был ровно один обычный эмодзи
        """
        # Простая проверка: длина в символах должна быть 1-2 (большинство эмодзи)
        # Более точная проверка может использовать библиотеку emoji
        if not emoji_text:
            return False

        # Можно добавить более сложную логику проверки эмодзи
        # Например, используя регулярные выражения для эмодзи
        emoji_pattern = re.compile(
            r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]+',
            flags=re.UNICODE
        )

        return bool(emoji_pattern.fullmatch(emoji_text))

    @staticmethod
    def create_emoji_tag(document_id, placeholder="🔴"):
        """
        Создает HTML-тег для кастомного эмодзи

        Пример:
            create_emoji_tag(123456) -> "<emoji document_id=123456>🔴</emoji>"
        """
        return f"<emoji document_id={document_id}>{placeholder}</emoji>"

# Глобальный экземпляр для обратной совместимости
emoji_parser = EmojiParser()
