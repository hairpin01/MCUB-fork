# utils/message_helpers.py
# author: @Hairpin00
# version: 1.2.0
# description: Хелперы для отправки сообщений с HTML разметкой

import re
import html
from .html_parser import parse_html, _utf16_len

def clean_html_fallback(html_text: str) -> str:
    """
    Универсальная очистка HTML при ошибках парсинга.
    Удаляет теги форматирования, оставляя только текст.

    Args:
        html_text (str): HTML текст для очистки

    Returns:
        str: Текст без HTML тегов
    """
    if not html_text:
        return ""

    # Важно: сначала заменяем эмодзи
    # Кастомные эмодзи (новый синтаксис)
    text = re.sub(r'<tg-emoji[^>]*>(.*?)</tg-emoji>', r'\1', html_text)

    # Кастомные эмодзи (старый синтаксис через img)
    text = re.sub(r'<img[^>]*src="tg://emoji\?id=[^"]+"[^>]*alt="([^"]*)"[^>]*>', r'\1', text)
    text = re.sub(r'<img[^>]*src="tg://emoji\?id=[^"]+"[^>]*>', '', text)

    # Удаляем все теги форматирования (открывающие и закрывающие)
    # Порядок важен: сначала закрывающие, потом открывающие
    tags_patterns = [
        # Закрывающие теги
        r'</(?:b|strong|i|em|u|s|del|code|pre|blockquote|a|tg-spoiler|spoiler)>',

        # Открывающие теги (без атрибутов или с атрибутами)
        r'<(?:b|strong|i|em|u|s|del|code|tg-spoiler|spoiler)(?:\s[^>]*)?>',

        # Открывающие теги с атрибутами
        r'<pre(?:\s[^>]*)?>',
        r'<blockquote(?:\s[^>]*)?>',
        r'<a\s[^>]*>',

        # Одиночные теги
        r'<br(?:\s[^>]*)?>',
    ]

    for pattern in tags_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)

    # Декодируем HTML-сущности
    text = html.unescape(text)

    # Убираем лишние пробелы, оставшиеся после удаления тегов
    text = re.sub(r'\s+', ' ', text).strip()

    return text

def truncate_text_with_entities(text: str, entities: list, max_length: int = 4096):
    """
    Обрезает текст и сущности, чтобы уложиться в лимит Telegram.

    Args:
        text (str): Текст для обрезки
        entities (list): Список сущностей
        max_length (int): Максимальная длина текста (по умолчанию 4096 для Telegram)

    Returns:
        tuple: (обрезанный текст, обрезанные сущности)
    """
    # Проверяем длину текста в UTF-16
    text_length = _utf16_len(text)

    if text_length <= max_length:
        return text, entities

    # Обрезаем текст
    # Ищем позицию, где можно безопасно обрезать (по границе UTF-16 символов)
    truncated_text = ""
    current_length = 0

    for char in text:
        char_length = _utf16_len(char)
        if current_length + char_length > max_length:
            break
        truncated_text += char
        current_length += char_length

    # Корректируем сущности
    truncated_entities = []
    for entity in entities:
        # Если сущность полностью помещается в обрезанный текст
        if entity.offset + entity.length <= current_length:
            truncated_entities.append(entity)
        # Если сущность начинается внутри, но заканчивается снаружи
        elif entity.offset < current_length:
            # Создаем копию сущности с обрезанной длиной
            if hasattr(entity, '__dict__'):
                # Для большинства сущностей Telethon
                entity_dict = entity.__dict__.copy()
                entity_dict['length'] = current_length - entity.offset
                new_entity = entity.__class__(**entity_dict)
                truncated_entities.append(new_entity)

    return truncated_text, truncated_entities

async def _send_html_generic(send_func, html_text: str, kernel, truncate: bool = True, **kwargs):
    """
    Универсальная функция для отправки HTML с обработкой ошибок.

    Args:
        send_func: Функция отправки (event.edit, event.reply, client.send_message)
        html_text (str): HTML текст
        kernel: Объект ядра для обработки ошибок
        truncate (bool): Нужно ли обрезать текст по лимиту Telegram
        **kwargs: Дополнительные аргументы для send_func

    Returns:
        Результат выполнения send_func
    """
    try:
        text, entities = parse_html(html_text)

        # Обрезаем текст и сущности при необходимости
        if truncate:
            text, entities = truncate_text_with_entities(text, entities)

        return await send_func(text, formatting_entities=entities, **kwargs)
    except Exception as e:
        # Получаем имя функции
        source_name = getattr(send_func, '__name__', str(send_func))
        await kernel.handle_error(e, source=f"{source_name}_with_html")

        # Fallback: отправляем очищенный текст
        fallback_text = clean_html_fallback(html_text)

        # Обрезаем fallback текст тоже
        if truncate:
            fallback_text = truncate_text_with_entities(fallback_text, [])[0]

        return await send_func(fallback_text, **kwargs)

async def edit_with_html(kernel, event, html_text: str, truncate: bool = True, **kwargs):
    """
    Редактирует сообщение с HTML разметкой.

    Args:
        kernel: Объект ядра
        event: Событие Telethon
        html_text (str): HTML текст для отправки
        truncate (bool): Нужно ли обрезать текст по лимиту Telegram (по умолчанию True)
        **kwargs: Дополнительные аргументы для event.edit

    Returns:
        Обновленное сообщение
    """
    return await _send_html_generic(
        event.edit,
        html_text,
        kernel,
        truncate=truncate,
        **kwargs
    )

async def reply_with_html(kernel, event, html_text: str, truncate: bool = True, **kwargs):
    """
    Отвечает на сообщение с HTML разметкой.

    Args:
        kernel: Объект ядра
        event: Событие Telethon
        html_text (str): HTML текст для отправки
        truncate (bool): Нужно ли обрезать текст по лимиту Telegram (по умолчанию True)
        **kwargs: Дополнительные аргументы для event.reply

    Returns:
        Отправленное сообщение
    """
    return await _send_html_generic(
        event.reply,
        html_text,
        kernel,
        truncate=truncate,
        **kwargs
    )

async def send_with_html(kernel, client, chat_id, html_text: str, truncate: bool = True, **kwargs):
    """
    Отправляет сообщение с HTML разметкой.

    Args:
        kernel: Объект ядра
        client: Клиент Telethon
        chat_id: ID чата
        html_text (str): HTML текст для отправки
        truncate (bool): Нужно ли обрезать текст по лимиту Telegram (по умолчанию True)
        **kwargs: Дополнительные аргументы для client.send_message

    Returns:
        Отправленное сообщение
    """
    async def send_message(text, **inner_kwargs):
        return await client.send_message(chat_id, text, **inner_kwargs)

    return await _send_html_generic(
        send_message,
        html_text,
        kernel,
        truncate=truncate,
        **kwargs
    )

async def send_file_with_html(kernel, client, chat_id, html_text: str, file, truncate: bool = True, **kwargs):
    """
    Отправляет файл с HTML подписью.

    Args:
        kernel: Объект ядра
        client: Клиент Telethon
        chat_id: ID чата
        html_text (str): HTML подпись
        file: Файл для отправки
        truncate (bool): Нужно ли обрезать текст по лимиту Telegram (по умолчанию True)
        **kwargs: Дополнительные аргументы

    Returns:
        Отправленное сообщение
    """
    async def send_file(text, **inner_kwargs):
        return await client.send_file(
            chat_id,
            file,
            caption=text,
            **inner_kwargs
        )

    # Для подписей к файлам лимит 1024 символа
    return await _send_html_generic(
        send_file,
        html_text,
        kernel,
        truncate=truncate,
        **kwargs
    )
