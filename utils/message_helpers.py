# utils/message_helpers.py
# author: @Hairpin00
# version: 1.0.1
# description: Хелперы для отправки сообщений с HTML разметкой

from .html_parser import parse_html

async def edit_with_html(kernel, event, html_text):
    """
    Редактирует сообщение с HTML разметкой

    Args:
        kernel: объект ядра
        event: событие Telethon
        html_text (str): HTML текст для отправки

    Returns:
        Обновленное сообщение
    """
    try:
        text, entities = parse_html(html_text)
        return await event.edit(text, formatting_entities=entities)
    except Exception as e:
        await kernel.handle_error(e, source="edit_with_html", event=event)
        # Fallback: отправляем без форматирования
        fallback_text = html_text
        for tag in ['<b>', '</b>', '<i>', '</i>', '<code>', '</code>', '<pre>', '</pre>']:
            fallback_text = fallback_text.replace(tag, '')
        # Убираем tg-emoji теги
        import re
        fallback_text = re.sub(r'<tg-emoji[^>]*>(.*?)</tg-emoji>', r'\1', fallback_text)
        return await event.edit(fallback_text)

async def reply_with_html(kernel, event, html_text):
    """
    Отвечает на сообщение с HTML разметкой

    Args:
        kernel: объект ядра
        event: событие Telethon
        html_text (str): HTML текст для отправки

    Returns:
        Отправленное сообщение
    """
    try:
        text, entities = parse_html(html_text)
        return await event.reply(text, formatting_entities=entities)
    except Exception as e:
        await kernel.handle_error(e, source="reply_with_html", event=event)
        # Fallback
        import re
        fallback_text = re.sub(r'<tg-emoji[^>]*>(.*?)</tg-emoji>', r'\1', html_text)
        for tag in ['<b>', '</b>', '<i>', '</i>', '<code>', '</code>']:
            fallback_text = fallback_text.replace(tag, '')
        return await event.reply(fallback_text)

async def send_with_html(kernel, client, chat_id, html_text):
    """
    Отправляет сообщение с HTML разметкой

    Args:
        kernel: объект ядра
        client: клиент Telethon
        chat_id: ID чата
        html_text (str): HTML текст для отправки

    Returns:
        Отправленное сообщение
    """
    try:
        text, entities = parse_html(html_text)
        return await client.send_message(chat_id, text, formatting_entities=entities)
    except Exception as e:
        await kernel.handle_error(e, source="send_with_html")
        # Fallback
        import re
        fallback_text = re.sub(r'<tg-emoji[^>]*>(.*?)</tg-emoji>', r'\1', html_text)
        for tag in ['<b>', '</b>', '<i>', '</i>', '<code>', '</code>']:
            fallback_text = fallback_text.replace(tag, '')
        return await client.send_message(chat_id, fallback_text)
