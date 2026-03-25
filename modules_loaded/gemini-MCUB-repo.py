#  This file is part of SenkoGuardianModules
#  Copyright (c) 2025 Senko
#  This software is released under the MIT License.
#  https://opensource.org/licenses/MIT

__version__ = (5, 8, 0) #перепешите на меня квартиру пж

#ладно

#зачем тебе квартира

# мне нада

#  .------. .------. .------. .------. .------. .------.
#  |S.--. | |E.--. | |N.--. | |M.--. | |O.--. | |D.--. |
#  | :/\: | | :/\: | | :(): | | :/\: | | :/\: | | :/\: |
#  | :\/: | | :\/: | | ()() | | :\/: | | :\/: | | :\/: |
#  | '--'S| | '--'E| | '--'N| | '--'M| | '--'O| | '--'D|
#  `------' `------' `------' `------' `------' `------'
# github MCUB repo: https://github.com/hairpin01/repo-MCUB-fork
# Channel: https://t.me/LinuxGram2
# Channel sen modules: https://t.me/SenkoGuardianModules
# -------------------- Meta data ---------------------------
# requires: google-genai, google-api-core, pytz, markdown_it_py
# author: port: @Hairpin00, author: @TypeFrag
# version: 5.8.0
# description: gemini for MCUB ! | MIT License
# scop: kernel min v1.0.2.2.5
# ----------------------- End ------------------------------
import re
import os
import io
import json
import random
import asyncio
import logging
import tempfile
from datetime import datetime
from markdown_it import MarkdownIt
import pytz

# New SDK Check
try:
    from google import genai
    from google.genai import types
    import google.api_core.exceptions as google_exceptions
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    google_exceptions = None

from telethon import types as tg_types, Button
from telethon.tl.types import Message, DocumentAttributeFilename, DocumentAttributeSticker
from telethon.utils import get_display_name

logger = logging.getLogger(__name__)

DB_HISTORY_KEY = "gemini_conversations_v4"
DB_GAUTO_HISTORY_KEY = "gemini_gauto_conversations_v1"
DB_IMPERSONATION_KEY = "gemini_impersonation_chats"
GEMINI_TIMEOUT = 840
MAX_FFMPEG_SIZE = 90 * 1024 * 1024

# Strings для модуля
STRINGS = {
    "name": "Gemini",
    "cfg_api_key_doc": "API ключи Google Gemini, разделенные запятой. Будут скрыты.",
    "cfg_model_name_doc": "Модель Gemini.",
    "cfg_buttons_doc": "Включить интерактивные кнопки.",
    "cfg_system_instruction_doc": "Системная инструкция (промпт) для Gemini.",
    "cfg_max_history_length_doc": "Макс. кол-во пар 'вопрос-ответ' в памяти (0 - без лимита).",
    "cfg_timezone_doc": "Ваш часовой пояс. Список: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones",
    "cfg_proxy_doc": "Прокси для обхода региональных блокировок. Формат: http://user:pass@host:port",
    "cfg_impersonation_prompt_doc": "Промпт для режима авто-ответа. {my_name} и {chat_history} будут заменены.",
    "cfg_impersonation_history_limit_doc": "Сколько последних сообщений из чата отправлять в качестве контекста для авто-ответа.",
    "cfg_impersonation_reply_chance_doc": "Вероятность ответа в режиме gauto (от 0.0 до 1.0). 0.2 = 20% шанс.",
    "cfg_temperature_doc": "Температура генерации (креативность). От 0.0 до 2.0. По умолчанию 1.0.",
    "cfg_google_search_doc": "Включить поиск Google (Grounding) для актуальной информации.",
    "no_api_key": '❗️ <b>Api ключ(и) не настроен(ы).</b>\nПолучить Api ключ можно <a href="https://aistudio.google.com/app/apikey">здесь</a>.\n<b>Добавьте ключ(и) в конфиге</b> <code>.cfg set gemini_api_key [ключ]</code>',
    "invalid_api_key": '❗️ <b>Предоставленный API ключ недействителен.</b>\nУбедитесь, что он правильно скопирован из <a href="https://aistudio.google.com/app/apikey">Google AI Studio</a> и что для него включен Gemini API.',
    "all_keys_exhausted": "❗️ <b>Все доступные API ключи ({}) исчерпали свою квоту.</b>\nПопробуйте позже или добавьте новые ключи в конфиге: <code>.config gemini_api_key</code>",
    "no_prompt_or_media": "⚠️ <i>Нужен текст или ответ на медиа/файл.</i>",
    "processing": "<tg-emoji emoji-id=\"5386367538735104399\">⌛️</tg-emoji> <b>Обработка...</b>",
    "api_error": "❗️ <b>Ошибка API Google Gemini:</b>\n<code>{}</code>",
    "api_timeout": f"❗️ <b>Таймаут ответа от Gemini API ({GEMINI_TIMEOUT} сек).</b>",
    "blocked_error": "🚫 <b>Запрос/ответ заблокирован.</b>\n<code>{}</code>",
    "generic_error": "❗️ <b>Ошибка:</b>\n<code>{}</code>",
    "question_prefix": "💬 <b>Запрос:</b>",
    "response_prefix": "<tg-emoji emoji-id=\"5325547803936572038\">✨</tg-emoji> <b>Gemini:</b>",
    "unsupported_media_type": "⚠️ <b>Формат медиа ({}) не поддерживается.</b>",
    "memory_status": "🧠 [{}/{}]",
    "memory_status_unlimited": "🧠 [{}/∞]",
    "memory_cleared": "🧹 <b>Память диалога очищена.</b>",
    "memory_cleared_gauto": "🧹 <b>Память gauto в этом чате очищена.</b>",
    "no_memory_to_clear": "ℹ️ <b>В этом чате нет истории.</b>",
    "no_gauto_memory_to_clear": "ℹ️ <b>В этом чате нет истории gauto.</b>",
    "memory_chats_title": "🧠 <b>Чаты с историей ({}):</b>",
    "memory_chat_line": "  • {} (<code>{}</code>)",
    "no_memory_found": "ℹ️ Память Gemini пуста.",
    "media_reply_placeholder": "[ответ на медиа]",
    "btn_clear": "🧹 Очистить",
    "btn_regenerate": "🔄 Другой ответ",
    "no_last_request": "Последний запрос не найден для повторной генерации.",
    "memory_fully_cleared": "🧹 <b>Вся память Gemini полностью очищена (затронуто {} чатов).</b>",
    "gauto_memory_fully_cleared": "🧹 <b>Вся память gauto полностью очищена (затронуто {} чатов).</b>",
    "no_memory_to_fully_clear": "ℹ️ <b>Память Gemini и так пуста.</b>",
    "no_gauto_memory_to_fully_clear": "ℹ️ <b>Память gauto и так пуста.</b>",
    "response_too_long": "Ответ Gemini был слишком длинным и отправлен в виде файла.",
    "gclear_usage": "ℹ️ <b>Использование:</b> <code>.gclear [auto]</code>",
    "gres_usage": "ℹ️ <b>Использование:</b> <code>.gres [auto]</code>",
    "auto_mode_on": "🎭 <b>Режим авто-ответа включен в этом чате.</b>\nЯ буду отвечать на сообщения с вероятностью {}%.",
    "auto_mode_off": "🎭 <b>Режим авто-ответа выключен в этом чате.</b>",
    "auto_mode_chats_title": "🎭 <b>Чаты с активным авто-ответом ({}):</b>",
    "no_auto_mode_chats": "ℹ️ Нет чатов с включенным режимом авто-ответа.",
    "auto_mode_usage": "ℹ️ <b>Использование:</b> <code>.gauto on/off или[id/username] [on/off]</code>",
    "gauto_chat_not_found": "🚫 <b>Не удалось найти чат:</b> <code>{}</code>",
    "gauto_state_updated": "🎭 <b>Режим авто-ответа для чата {} {}</b>",
    "gauto_enabled": "включен",
    "gauto_disabled": "выключен",
    "gch_usage": "ℹ️ <b>Использование:</b>\n<code>.gch <кол-во> <вопрос></code>\n<code>.gch <id чата> <кол-во> <вопрос></code>",
    "gch_processing": "<tg-emoji emoji-id=\"5386367538735104399\">⌛️</tg-emoji> <b>Анализирую {} сообщений...</b>",
    "gch_result_caption": "Анализ последних {} сообщений",
    "gch_result_caption_from_chat": "Анализ последних {} сообщений из чата <b>{}</b>",
    "gch_invalid_args": "❗️ <b>Неверные аргументы.</b>\n{}",
    "gch_chat_error": "❗️ <b>Ошибка доступа к чату</b> <code>{}</code>: <i>{}</i>",
    "gmodel_usage": "ℹ️ <b>Использование:</b> <code>.gmodel [модель] [-s]</code>\n• [модель] — установить модель.\n• -s — показать список доступных моделей.",
    "gmodel_list_title": "📋 <b>Доступные модели Gemini (по вашему API):</b>",
    "gmodel_list_item": "• <code>{}</code> — {} (поддержка: {})",
    "gmodel_img_support": "Поддержка изображений",
    "gmodel_no_support": "Нет поддержки изображений",
    "gmodel_img_warn": "⚠️ <b>Текущая модель ({}) не может генерировать изображения(или не доступна по API).</b>\nРекомендуем: <code>gemini-2.5-flash-image</code>",
    "gme_chat_not_found": "🚫 <b>Не удалось найти чат для экспорта:</b> <code>{}</code>",
    "gme_sent_to_saved": "💾 История экспортирована в избранное.",
    "new_sdk_missing": "⚠️ <b>Для работы модуля нужна библиотека google-genai.</b>\nВыполните: <code>pip install google-genai</code>",
    "gprompt_usage": "ℹ️ <b>Использование:</b>\n<code>.gprompt <текст></code> — установить промпт.\n<code>.gprompt -c</code> — очистить.\nИли ответьте на <b>.txt</b> файл.",
    "gprompt_updated": "✅ <b>Системный промпт обновлен!</b>\nДлина: {} симв.",
    "gprompt_cleared": "🗑 <b>Системный промпт очищен.</b>",
    "gprompt_current": "📝 <b>Текущий системный промпт:</b>",
    "gprompt_file_error": "❗️ <b>Ошибка чтения файла:</b> {}",
    "gprompt_file_too_big": "❗️ <b>Файл слишком большой</b> (лимит 1 МБ).",
    "gprompt_not_text": "❗️ Это не похоже на текстовый файл.(txt)",
    "gmodel_no_models": "⚠️ Не удалось получить список моделей.",
    "gmodel_list_error": "❗️ Ошибка получения списка: {}",
}

TEXT_MIME_TYPES = {
    "text/plain", "text/markdown", "text/html", "text/css", "text/csv",
    "application/json", "application/xml", "application/x-python", "text/x-python",
    "application/javascript", "application/x-sh",
}

module_state = {
    'conversations': {},
    'gauto_conversations': {},
    'last_requests': {},
    'impersonation_chats': set(),
    'memory_disabled_chats': set(),
    'profiles': {},
    'knowledge_base': [],
    'api_keys': [],
    'current_api_key_index': 0,
    'me': None
}

def escape_html(text):
    """Экранирование HTML символов"""
    if text is None:
        return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def get_args(event):
    """Получение аргументов команды"""
    try:
        message = event.message
        args = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""
        return args
    except:
        return ""

def get_chat_id(event):
    """Получение ID чата"""
    return event.chat_id

async def init_db(kernel):
    """Инициализация таблиц БД"""
    if kernel.db_conn:
        await kernel.db_conn.execute("""
            CREATE TABLE IF NOT EXISTS gemini_data (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await kernel.db_conn.commit()

async def db_get(kernel, key, default=None):
    """Получение данных из БД"""
    row = None
    if kernel.db_conn:
        cursor = await kernel.db_conn.execute(
            "SELECT value FROM gemini_data WHERE key = ?", (key,)
        )
        row = await cursor.fetchone()
    if row:
        try:
            value = row[0] if isinstance(row, tuple) else row["value"]
            return json.loads(value)
        except:
            return row[0] if isinstance(row, tuple) else row["value"]
    return default

async def db_set(kernel, key, value):
    """Сохранение данных в БД"""
    json_value = json.dumps(value) if not isinstance(value, str) else value
    if kernel.db_conn:
        await kernel.db_conn.execute(
            "INSERT OR REPLACE INTO gemini_data (key, value) VALUES (?, ?)",
            (key, json_value)
        )
        await kernel.db_conn.commit()

async def _prepare_parts(kernel, message: Message, custom_text: str = None):
    """Подготовка частей для отправки в Gemini"""
    final_parts, warnings = [], []
    prompt_text_chunks = []
    user_args = custom_text if custom_text is not None else get_args(message)
    reply = await message.get_reply_message()

    if reply and getattr(reply, "text", None):
        try:
            reply_sender = await reply.get_sender()
            reply_author_name = get_display_name(reply_sender) if reply_sender else "Unknown"
            prompt_text_chunks.append(f"{reply_author_name}: {reply.text}")
        except Exception:
            prompt_text_chunks.append(f"Ответ на: {reply.text}")

    try:
        current_sender = await message.get_sender()
        current_user_name = get_display_name(current_sender) if current_sender else "User"
        prompt_text_chunks.append(f"{current_user_name}: {user_args or ''}")
    except Exception:
        prompt_text_chunks.append(f"Запрос: {user_args or ''}")

    media_source = message if message.media or message.sticker else reply
    has_media = bool(media_source and (media_source.media or media_source.sticker))

    if has_media:
        if media_source.sticker and hasattr(media_source.sticker, 'mime_type') and media_source.sticker.mime_type == 'application/x-tgsticker':
            alt_text = next((attr.alt for attr in media_source.sticker.attributes if isinstance(attr, DocumentAttributeSticker)), "?")
            prompt_text_chunks.append(f"[Анимированный стикер: {alt_text}]")
        else:
            media, mime_type, filename = media_source.media, "application/octet-stream", "file"
            if media_source.photo:
                mime_type = "image/jpeg"
            elif hasattr(media_source, "document") and media_source.document:
                mime_type = getattr(media_source.document, "mime_type", mime_type)
                doc_attr = next((attr for attr in media_source.document.attributes if isinstance(attr, DocumentAttributeFilename)), None)
                if doc_attr: filename = doc_attr.file_name

            async def get_bytes(m):
                bio = io.BytesIO()
                await kernel.client.download_media(m, bio)
                return bio.getvalue()

            if mime_type.startswith("image/"):
                try:
                    data = await get_bytes(media)
                    final_parts.append(types.Part(inline_data=types.Blob(mime_type=mime_type, data=data)))
                except Exception as e:
                    warnings.append(f"⚠️ Ошибка обработки изображения '{filename}': {e}")
            elif mime_type in TEXT_MIME_TYPES or filename.split('.')[-1] in ('txt', 'py', 'js', 'json', 'md', 'html', 'css', 'sh'):
                try:
                    data = await get_bytes(media)
                    file_content = data.decode('utf-8')
                    prompt_text_chunks.insert(0, f"[Содержимое файла '{filename}']: \n```\n{file_content}\n```")
                except Exception as e:
                    warnings.append(f"⚠️ Ошибка чтения файла '{filename}': {e}")
            elif mime_type.startswith("audio/"):
                input_path, output_path = None, None
                try:
                    with tempfile.NamedTemporaryFile(suffix=f".{filename.split('.')[-1]}", delete=False) as temp_in:
                        input_path = temp_in.name
                    await kernel.client.download_media(media, input_path)
                    if os.path.getsize(input_path) > MAX_FFMPEG_SIZE:
                        warnings.append(f"⚠️ Аудиофайл '{filename}' слишком большой.")
                        raise StopIteration
                    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_out:
                        output_path = temp_out.name
                    proc = await asyncio.create_subprocess_exec(
                        "ffmpeg", "-y", "-i", input_path, "-c:a", "libmp3lame", "-q:a", "2", output_path,
                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                    )
                    await proc.communicate()
                    with open(output_path, "rb") as f:
                        final_parts.append(types.Part(inline_data=types.Blob(mime_type="audio/mpeg", data=f.read())))
                except StopIteration:
                    pass
                except Exception as e:
                    warnings.append(f"⚠️ Ошибка обработки аудио: {e}")
                finally:
                    if input_path and os.path.exists(input_path): os.remove(input_path)
                    if output_path and os.path.exists(output_path): os.remove(output_path)
            elif mime_type.startswith("video/"):
                input_path, output_path = None, None
                try:
                    with tempfile.NamedTemporaryFile(suffix=f".{filename.split('.')[-1]}", delete=False) as temp_in:
                        input_path = temp_in.name
                    await kernel.client.download_media(media, input_path)
                    if os.path.getsize(input_path) > MAX_FFMPEG_SIZE:
                        warnings.append(f"⚠️ Медиафайл '{filename}' слишком большой.")
                        raise StopIteration
                    proc_probe = await asyncio.create_subprocess_exec(
                        "ffprobe", "-v", "error", "-select_streams", "a:0",
                        "-show_entries", "stream=codec_type", "-of", "default=noprint_wrappers=1:nokey=1",
                        input_path, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                    )
                    stdout, _ = await proc_probe.communicate()
                    has_audio = bool(stdout.strip())
                    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_out:
                        output_path = temp_out.name
                    cmd = ["ffmpeg", "-y", "-i", input_path]
                    maps = ["-map", "0:v:0"]
                    if not has_audio:
                        cmd.extend(["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"])
                        maps.extend(["-map", "1:a:0"])
                    else:
                        maps.extend(["-map", "0:a:0?"])
                    cmd.extend([*maps, "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-c:v", "libx264",
                               "-c:a", "aac", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                               "-shortest", output_path])
                    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE,
                                                                stderr=asyncio.subprocess.PIPE)
                    await proc.communicate()
                    with open(output_path, "rb") as f:
                        final_parts.append(types.Part(inline_data=types.Blob(mime_type="video/mp4", data=f.read())))
                except StopIteration:
                    pass
                except Exception as e:
                    warnings.append(f"⚠️ Ошибка обработки видео: {e}")
                finally:
                    if input_path and os.path.exists(input_path): os.remove(input_path)
                    if output_path and os.path.exists(output_path): os.remove(output_path)

    if not user_args and has_media and not final_parts and not any("[Содержимое файла" in chunk for chunk in prompt_text_chunks):
        prompt_text_chunks.append(STRINGS["media_reply_placeholder"])

    full_prompt_text = "\n".join(chunk for chunk in prompt_text_chunks if chunk and chunk.strip()).strip()
    if full_prompt_text:
        final_parts.insert(0, types.Part(text=full_prompt_text))

    return final_parts, warnings

def _handle_error(e: Exception) -> str:
    """Обработка ошибок"""
    logger.exception("Gemini execution error")
    if isinstance(e, asyncio.TimeoutError):
        return STRINGS["api_timeout"]
    msg = str(e)
    if "quota" in msg.lower() or "exhausted" in msg.lower() or "429" in msg:
        model = module_state.get('model_name', 'unknown')
        return (
            f"❗️ <b>Превышен лимит Google Gemini API для модели <code>{escape_html(model)}</code>.</b>"
            "\n\nЧаще всего это происходит на бесплатном тарифе. Вы можете:\n"
            "• Подождать, пока лимит сбросится (обычно раз в сутки).\n"
            "• Проверить свой тарифный план в <a href='https://aistudio.google.com/app/billing'>Google AI Studio</a>.\n"
            "• Узнать больше о лимитах <a href='https://ai.google.dev/gemini-api/docs/rate-limits'>здесь</a>.\n\n"
            f"<b>Детали ошибки:</b>\n<code>{escape_html(msg)}</code>"
        )
    if "location" in msg.lower() or "not supported" in msg.lower():
        return (
            '❗️ <b>В данном регионе Gemini API не доступен.</b>\n'
            'Скачайте VPN (для пк/тел) или поставьте прокси (платный/бесплатный).\n'
            'Или воспользуйтесь инструкцией <a href="https://t.me/SenkoGuardianModules/23">вот тут</a>\n'
            'А для тех у кого UserLand инструкция <a href="https://t.me/SenkoGuardianModules/35">тут</a>'
        )
    if "key" in msg.lower() and "valid" in msg.lower():
        return STRINGS["invalid_api_key"]
    if "blocked" in msg.lower():
        return STRINGS["blocked_error"].format(escape_html(msg))
    if "500" in msg:
        return (
            "❗️ <b>Ошибка 500 от Google API.</b>\n"
            "Это значит, что формат медиа (файл или еще что то) который ты отправил, не поддерживается.\n"
            "Такое случается, по такой причине:\n  "
            "• Если формат файла в принципе не поддерживается Gemini/Гуглом.\n  "
            "• Временный сбой на серверах Google. Попробуйте повторить запрос позже."
        )
    return STRINGS["api_error"].format(escape_html(msg))

def _markdown_to_html(text: str) -> str:
    """Конвертация markdown в HTML"""
    def heading_replacer(match):
        level = len(match.group(1))
        title = match.group(2).strip()
        indent = "   " * (level - 1)
        return f"{indent}<b>{title}</b>"
    text = re.sub(r"^(#+)\s+(.*)", heading_replacer, text, flags=re.MULTILINE)

    def list_replacer(match):
        indent = match.group(1)
        return f"{indent}• "
    text = re.sub(r"^([ \t]*)[-*+]\s+", list_replacer, text, flags=re.MULTILINE)

    md = MarkdownIt("commonmark", {"html": True, "linkify": True})
    md.enable("strikethrough")
    md.disable("hr")
    md.disable("heading")
    md.disable("list")
    html_text = md.render(text)

    def format_code(match):
        lang = escape_html(match.group(1).strip())
        code = escape_html(match.group(2).strip())
        return f'<pre><code class="language-{lang}">{code}</code></pre>' if lang else f'<pre><code>{code}</code></pre>'
    html_text = re.sub(r"```(.*?)\n([\s\S]+?)\n```", format_code, html_text)
    html_text = re.sub(r"<p>(<pre>[\s\S]*?</pre>)</p>", r"\1", html_text, flags=re.DOTALL)
    html_text = html_text.replace("<p>", "").replace("</p>", "\n").strip()

    return html_text

def _format_response_with_smart_separation(text: str) -> str:
    """Форматирование ответа с умным разделением"""
    # Если в тексте есть код, парсер телеграма может сломаться от blockquote.
    # Поэтому если есть <pre>, мы не оборачиваем текст в blockquote.
    if "<pre" in text:
        return text

    # Если кода нет, безопасно оборачиваем весь текст
    stripped_text = text.strip()
    if stripped_text:
        return f'<blockquote expandable="true">{stripped_text}</blockquote>'

    return ""

def _get_proxy_config(kernel):
    """Получение конфигурации прокси"""
    p = kernel.config.get("gemini_proxy", "")
    return {"http://": p, "https://": p} if p else None

async def _save_history_sync(kernel, gauto: bool = False):
    """Сохранение истории в БД"""
    data, key = (module_state['gauto_conversations'], DB_GAUTO_HISTORY_KEY) if gauto else (module_state['conversations'], DB_HISTORY_KEY)
    try:
        await db_set(kernel, key, data)
    except Exception as e:
        logger.error(f"Error saving history: {e}")

async def _load_history_from_db(kernel, key):
    """Загрузка истории из БД"""
    d = await db_get(kernel, key, {})
    return d if isinstance(d, dict) else {}

def _get_structured_history(cid, gauto=False):
    """Получение структурированной истории"""
    d = module_state['gauto_conversations'] if gauto else module_state['conversations']
    if str(cid) not in d:
        d[str(cid)] = []
    return d[str(cid)]

async def _update_history(kernel, chat_id: int, user_parts: list, model_response: str, regeneration: bool = False,
                   message: Message = None, gauto: bool = False):
    """Обновление истории"""
    if not _is_memory_enabled(str(chat_id)):
        return

    history = _get_structured_history(chat_id, gauto)
    import time
    now = int(time.time())
    user_id = module_state['me'].id if module_state['me'] else None
    user_name = get_display_name(module_state['me']) if module_state['me'] else "User"
    message_id = getattr(message, "id", None)

    if message:
        if message.sender_id:
            user_id = message.sender_id
        if message.sender:
            user_name = get_display_name(message.sender)

    user_text = " ".join([p.text for p in user_parts if hasattr(p, "text") and p.text]) or "[ответ на медиа]"

    if regeneration and history:
        for i in range(len(history) - 1, -1, -1):
            if history[i].get("role") == "model":
                history[i].update({
                    "content": model_response,
                    "date": now
                })
                break
    else:
        user_entry = {
            "role": "user",
            "type": "text",
            "content": user_text,
            "date": now,
            "user_id": user_id,
            "message_id": message_id,
            "user_name": user_name
        }
        model_entry = {
            "role": "model",
            "type": "text",
            "content": model_response,
            "date": now,
            "user_id": None
        }

        history.extend([user_entry, model_entry])

    limit = module_state.get('max_history_length', 800)
    if limit > 0 and len(history) > limit * 2:
        history = history[-(limit * 2):]

    target = module_state['gauto_conversations'] if gauto else module_state['conversations']
    target[str(chat_id)] = history

    await _save_history_sync(kernel, gauto)

async def _clear_history(kernel, cid, gauto=False):
    """Очистка истории"""
    d = module_state['gauto_conversations'] if gauto else module_state['conversations']
    if str(cid) in d:
        del d[str(cid)]
        await _save_history_sync(kernel, gauto)

def _is_memory_enabled(chat_id: str) -> bool:
    """Проверка включена ли память"""
    return chat_id not in module_state['memory_disabled_chats']

def _disable_memory(chat_id: int):
    """Отключение памяти"""
    module_state['memory_disabled_chats'].add(str(chat_id))

def _enable_memory(chat_id: int):
    """Включение памяти"""
    module_state['memory_disabled_chats'].discard(str(chat_id))

async def _get_recent_chat_text(kernel, chat_id: int, count: int = None, skip_last: bool = False) -> str:
    """Получение недавнего текста из чата"""
    history_limit = count or module_state.get('impersonation_history_limit', 20)
    fetch_limit = history_limit + 1 if skip_last else history_limit
    chat_history_lines = []
    try:
        messages = await kernel.client.get_messages(chat_id, limit=fetch_limit)
        if skip_last and messages:
            messages = messages[1:]
        for msg in messages:
            if not msg:
                continue
            if not msg.text and not msg.sticker and not msg.photo and not (msg.media and not hasattr(msg.media, "webpage")):
                continue
            sender = await msg.get_sender()
            sender_name = get_display_name(sender) if sender else "Unknown"
            text_content = msg.text or ""
            if msg.sticker and hasattr(msg.sticker, 'attributes'):
                alt_text = next((attr.alt for attr in msg.sticker.attributes if isinstance(attr, DocumentAttributeSticker)), None)
                text_content += f" [Стикер: {alt_text or '?'}]"
            elif msg.photo:
                text_content += " [Фото]"
            elif msg.document and not hasattr(msg.media, "webpage"):
                text_content += " [Файл]"

            if text_content.strip():
                chat_history_lines.append(f"{sender_name}: {text_content.strip()}")
    except Exception as e:
        logger.warning(f"Не удалось получить историю для авто-ответа: {e}")
    return "\n".join(reversed(chat_history_lines))

async def _send_to_gemini(kernel, message, parts: list, regeneration: bool = False, is_callback = False,
                         status_msg = None, chat_id_override: int = None, impersonation_mode: bool = False,
                         use_url_context: bool = False, display_prompt: str = None):
    """Отправка запроса в Gemini"""
    msg_obj = None
    if regeneration:
        chat_id = chat_id_override
        base_message_id = message
        try:
            msg_obj = await kernel.client.get_messages(chat_id, ids=base_message_id)
        except Exception:
            msg_obj = None
    else:
        chat_id = get_chat_id(message)
        base_message_id = message.id
        msg_obj = message

    api_key_str = kernel.config.get("gemini_api_key", "")
    module_state['api_keys'] = [k.strip() for k in api_key_str.split(",") if k.strip()] if api_key_str else []

    if not module_state['api_keys']:
        if not impersonation_mode and status_msg:
            await status_msg.edit(STRINGS['no_api_key'], parse_mode='html')
        return None if impersonation_mode else ""

    if regeneration:
        current_turn_parts, request_text_for_display = module_state['last_requests'].get(
            f"{chat_id}:{base_message_id}", (parts, "[регенерация]")
        )
    else:
        current_turn_parts = parts
        request_text_for_display = display_prompt or (
            STRINGS["media_reply_placeholder"] if any(getattr(p, 'inline_data', None) for p in parts) else ""
        )
        module_state['last_requests'][f"{chat_id}:{base_message_id}"] = (current_turn_parts, request_text_for_display)

    result_text = ""
    last_error = None
    was_successful = False
    search_icon = ""
    max_retries = len(module_state['api_keys'])

    if impersonation_mode:
        my_name = get_display_name(module_state['me']) if module_state['me'] else "User"
        chat_history_text = await _get_recent_chat_text(kernel, chat_id)
        sys_instruct = kernel.config.get("gemini_impersonation_prompt", "").format(
            my_name=my_name, chat_history=chat_history_text
        )
    else:
        sys_val = kernel.config.get("gemini_system_instruction", "")
        sys_instruct = (sys_val.strip() if isinstance(sys_val, str) else "") or None

        # Global Knowledge Base Injection
        if module_state['knowledge_base']:
            kb_facts = "\n".join(f"- {fact}" for fact in module_state['knowledge_base'])
            kb_prompt_addition = f"\n\n[Системная заметка: Всегда учитывай следующие факты из своей глобальной Базы Знаний]:\n{kb_facts}"

            if sys_instruct:
                sys_instruct += kb_prompt_addition
            else:
                sys_instruct = kb_prompt_addition.strip()

    contents = []
    raw_hist = _get_structured_history(chat_id, gauto=impersonation_mode)
    if regeneration and raw_hist:
        raw_hist = raw_hist[:-2]
    for item in raw_hist:
        contents.append(types.Content(
            role=item['role'],
            parts=[types.Part(text=item['content'])]
        ))

    request_parts = list(current_turn_parts)
    if not impersonation_mode:
        try:
            user_timezone = pytz.timezone(kernel.config.get("gemini_timezone", "Europe/Moscow"))
        except pytz.UnknownTimeZoneError:
            user_timezone = pytz.utc
        now = datetime.now(user_timezone)
        time_note = f"[System note: Current time is {now.strftime('%Y-%m-%d %H:%M:%S %Z')}]"
        if request_parts and getattr(request_parts[0], 'text', None):
            request_parts[0] = types.Part(text=f"{time_note}\n\n{request_parts[0].text}")
        else:
            request_parts.insert(0, types.Part(text=time_note))

    contents.append(types.Content(role="user", parts=request_parts))

    tools = []
    if kernel.config.get("gemini_google_search", False) or use_url_context:
        tools.append(types.Tool(google_search=types.GoogleSearch()))

    gen_config = types.GenerateContentConfig(
        temperature=kernel.config.get("gemini_temperature", 1.0),
        system_instruction=sys_instruct,
        tools=tools if tools else None,
        safety_settings=[
            types.SafetySetting(category=cat, threshold="BLOCK_NONE")
            for cat in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH",
                       "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]
        ]
    )

    proxy_config = _get_proxy_config(kernel)
    for i in range(max_retries):
        current_idx = (module_state['current_api_key_index'] + i) % max_retries
        api_key = module_state['api_keys'][current_idx]
        try:
            http_opts = None
            if proxy_config:
                http_opts = types.HttpOptions(async_client_args={"proxies": proxy_config})

            client = genai.Client(api_key=api_key, http_options=http_opts)
            response = await client.aio.models.generate_content(
                model=kernel.config.get("gemini_model_name", "gemini-2.5-flash"),
                contents=contents,
                config=gen_config
            )

            if response.text:
                result_text = response.text
                was_successful = True
                if kernel.config.get("gemini_google_search", False):
                    search_icon = " 🌐"
                module_state['current_api_key_index'] = current_idx
                break
            else:
                raise ValueError("Empty response (Safety?)")
        except Exception as e:
            err_str = str(e).lower()
            if "quota" in err_str or "exhausted" in err_str or "429" in err_str:
                if i == max_retries - 1:
                    last_error = RuntimeError(f"Keys exhausted. Last: {e}")
                continue
            else:
                last_error = e
                break

    try:
        if not was_successful:
            raise last_error or RuntimeError("Unknown generation error")

        if _is_memory_enabled(str(chat_id)):
            await _update_history(kernel, chat_id, current_turn_parts, result_text, regeneration, msg_obj, gauto=impersonation_mode)

        if impersonation_mode:
            return result_text

        hist_len = len(_get_structured_history(chat_id)) // 2
        mem_ind = STRINGS["memory_status"].format(hist_len, kernel.config.get("gemini_max_history_length", 800))
        if kernel.config.get("gemini_max_history_length", 800) <= 0:
            mem_ind = STRINGS["memory_status_unlimited"].format(hist_len)

        response_html = _markdown_to_html(result_text)
        formatted_body = _format_response_with_smart_separation(response_html)
        question_html = f"<blockquote>{escape_html(request_text_for_display[:200])}</blockquote>"
        text_to_send = f"{mem_ind}\n\n{STRINGS['question_prefix']}\n{question_html}\n\n{STRINGS['response_prefix']}{search_icon}\n{formatted_body}"

        if kernel.config.get("gemini_interactive_buttons", True) and not is_callback:
            buttons = [
                [Button.inline(STRINGS["btn_clear"], f"gemini_clear_{chat_id}".encode()),
                Button.inline(STRINGS["btn_regenerate"], f"gemini_regen_{base_message_id}_{chat_id}".encode())]
            ]
            if len(text_to_send) > 4096:
                file_content = (f"Вопрос: {display_prompt}\n\n════════════════════\n\nОтвет Gemini:\n{result_text}")
                file = io.BytesIO(file_content.encode("utf-8"))
                file.name = "Gemini_response.txt"
                if status_msg:
                    await status_msg.delete()
                await kernel.client.send_file(chat_id, file, caption=STRINGS["response_too_long"],
                                              reply_to=base_message_id)
            else:
                success, msg = await kernel.inline_form(
                    chat_id,
                    text_to_send,
                    buttons=buttons
                )
                if success and status_msg:
                    await status_msg.delete()
                elif not success and status_msg:
                    await status_msg.edit(text_to_send, parse_mode='html')
        else:
            if len(text_to_send) > 4096:
                file_content = (f"Вопрос: {display_prompt}\n\n════════════════════\n\nОтвет Gemini:\n{result_text}")
                file = io.BytesIO(file_content.encode("utf-8"))
                file.name = "Gemini_response.txt"
                if is_callback:
                    await kernel.client.send_file(chat_id, file, caption=STRINGS["response_too_long"],
                                                 reply_to=base_message_id)
                elif status_msg:
                    await status_msg.delete()
                    await kernel.client.send_file(chat_id, file, caption=STRINGS["response_too_long"],
                                                 reply_to=base_message_id)
            else:
                if is_callback:
                    pass
                    
                elif status_msg:
                    await status_msg.edit(text_to_send, parse_mode='html')
                    
    except Exception as e:
        error_text = _handle_error(e)
        if impersonation_mode:
            logger.error(f"Gauto error: {error_text}")
        elif status_msg:
            await status_msg.edit(error_text, parse_mode='html')

    return None if impersonation_mode else ""


def register(kernel):

    if not GOOGLE_AVAILABLE:
        kernel.logger.error("Gemini: 'google-genai' library missing! pip install google-genai")
        return

    asyncio.create_task(init_db(kernel))

    async def init_module_state():
        module_state['me'] = await kernel.client.get_me()

        module_state['conversations'] = await _load_history_from_db(kernel, DB_HISTORY_KEY)
        module_state['gauto_conversations'] = await _load_history_from_db(kernel, DB_GAUTO_HISTORY_KEY)

        imp_chats = await db_get(kernel, DB_IMPERSONATION_KEY, [])
        module_state['impersonation_chats'] = set(imp_chats) if isinstance(imp_chats, list) else set()

        module_state['profiles'] = await db_get(kernel, "gemini_profiles", {})
        module_state['knowledge_base'] = await db_get(kernel, "gemini_kb", [])

    asyncio.create_task(init_module_state())

    if "gemini_api_key" not in kernel.config:
        kernel.config["gemini_api_key"] = ""
    if "gemini_model_name" not in kernel.config:
        kernel.config["gemini_model_name"] = "gemini-2.5-flash"
    if "gemini_interactive_buttons" not in kernel.config:
        kernel.config["gemini_interactive_buttons"] = True
    if "gemini_system_instruction" not in kernel.config:
        kernel.config["gemini_system_instruction"] = ""
    if "gemini_max_history_length" not in kernel.config:
        kernel.config["gemini_max_history_length"] = 800
    if "gemini_timezone" not in kernel.config:
        kernel.config["gemini_timezone"] = "Europe/Moscow"
    if "gemini_proxy" not in kernel.config:
        kernel.config["gemini_proxy"] = ""
    if "gemini_impersonation_prompt" not in kernel.config:
        kernel.config["gemini_impersonation_prompt"] = (
            "Ты — это я, пользователь Telegram по имени {my_name}. Твоя задача — отвечать в чате от моего имени, основываясь на последних сообщениях. "
            "Веди себя естественно, как обычный человек, а не как ассистент. Не признавайся, что ты — ИИ, даже если тебя спросят напрямую. "
            "Твоя личность: [Здесь опишите свой характер: остроумный, серьезный, саркастичный, дружелюбный и т.д.].\n"
            "Правила:\n- Отвечай кратко и по делу.\n- Используй неформальный язык, сленг.\n- Не отвечай на каждое сообщение.\n- На медиа (стикер, фото) реагируй как человек ('лол', 'ору', 'жиза').\n- Не используй префиксы и кавычки.\n\n"
            "ИСТОРИЯ ЧАТА:\n{chat_history}\n\n{my_name}:"
        )
    if "gemini_impersonation_history_limit" not in kernel.config:
        kernel.config["gemini_impersonation_history_limit"] = 20
    if "gemini_impersonation_reply_chance" not in kernel.config:
        kernel.config["gemini_impersonation_reply_chance"] = 0.25
    if "gemini_gauto_in_pm" not in kernel.config:
        kernel.config["gemini_gauto_in_pm"] = False
    if "gemini_google_search" not in kernel.config:
        kernel.config["gemini_google_search"] = False
    if "gemini_temperature" not in kernel.config:
        kernel.config["gemini_temperature"] = 1.0

    kernel.save_config()

    api_key_str = kernel.config.get("gemini_api_key", "")
    module_state['api_keys'] = [k.strip() for k in api_key_str.split(",") if k.strip()] if api_key_str else []
    module_state['current_api_key_index'] = 0
    module_state['max_history_length'] = kernel.config.get("gemini_max_history_length", 800)
    module_state['model_name'] = kernel.config.get("gemini_model_name", "gemini-2.5-flash")

    if not module_state['api_keys']:
        kernel.logger.warning("Gemini: API ключи не настроены.")

    @kernel.register.command('g', alias=['gemini'])
    # [текст или reply] — спросить у Gemini. Может анализировать ссылки.
    async def g_command(event):
        clean_args = get_args(event)
        reply = await event.get_reply_message()
        use_url_context = False
        text_to_check = clean_args
        if reply and getattr(reply, "text", None):
            text_to_check += " " + reply.text
        if re.search(r'https?://\S+', text_to_check):
            use_url_context = True

        status_msg = await event.edit(STRINGS["processing"], parse_mode='html')
        status_msg = await kernel.client.get_messages(status_msg.chat_id, ids=status_msg.id)

        parts, warnings = await _prepare_parts(kernel, event, custom_text=clean_args)
        if warnings and status_msg:
            try:
                await status_msg.edit(f"{status_msg.text}\n\n" + "\n".join(warnings), parse_mode='html')
            except:
                pass

        if not parts:
            if status_msg:
                await status_msg.edit(STRINGS["no_prompt_or_media"], parse_mode='html')
            return

        await _send_to_gemini(
            kernel=kernel, message=event, parts=parts, status_msg=status_msg,
            use_url_context=use_url_context, display_prompt=clean_args or None
        )

    @kernel.register.command('gsummary')
    # [ссылка или reply] - Сделать краткую выжимку из контента.
    async def gsummary_command(event):
        reply = await event.get_reply_message()
        if not get_args(event) and not (reply and (reply.text or reply.media)):
            return await event.edit("Ответьте на сообщение или дайте ссылку.", parse_mode='html')

        status_msg = await event.edit(STRINGS["processing"], parse_mode='html')

        parts, warnings = await _prepare_parts(kernel, event)
        if not parts:
            return await event.edit("Не удалось извлечь текст для анализа.", parse_mode='html')

        task_prompt = "Сделай краткую, но исчерпывающую выжимку (summary) из предоставленного контента. Выдели главное, отбрось воду."

        if parts and hasattr(parts[0], 'text'):
            parts[0].text = f"{task_prompt}\n\n---\n\n{parts[0].text}"
        else:
            parts.insert(0, types.Part(text=task_prompt))

        chat_id = get_chat_id(event)
        original_history = module_state['conversations'].pop(str(chat_id), None)

        await _send_to_gemini(kernel=kernel, message=event, parts=parts, status_msg=status_msg,
                            display_prompt="[анализ контента]")

        if original_history is not None:
            module_state['conversations'][str(chat_id)] = original_history

    @kernel.register.command('gqa')
    # <вопрос> [в ответе на ссылку/файл] - Задать вопрос по контенту.
    async def gqa_command(event):
        args = get_args(event)
        reply = await event.get_reply_message()
        if not args or not (reply and (reply.text or reply.media)):
            return await event.edit("Задайте вопрос в ответе на сообщение, файл или ссылку.", parse_mode='html')

        status_msg = await event.edit(STRINGS["processing"], parse_mode='html')

        parts, warnings = await _prepare_parts(kernel, reply, custom_text="")
        if not parts:
            return await event.edit("Не удалось извлечь текст для анализа.", parse_mode='html')

        task_prompt = f"Ответь на следующий вопрос, основываясь ИСКЛЮЧИТЕЛЬНО на предоставленном ниже тексте. Не используй свои общие знания.\n\nВопрос: «{args}»"

        if parts and hasattr(parts[0], 'text'):
            parts[0].text = f"{task_prompt}\n\n---\n\n{parts[0].text}"
        else:
            parts.insert(0, types.Part(text=task_prompt))

        chat_id = get_chat_id(event)
        original_history = module_state['conversations'].pop(str(chat_id), None)

        await _send_to_gemini(kernel=kernel, message=event, parts=parts, status_msg=status_msg,
                            display_prompt=args)

        if original_history is not None:
            module_state['conversations'][str(chat_id)] = original_history

    @kernel.register.command('gch')
    # <[id чата]> <кол-во> <вопрос> - Проанализировать историю чата.
    async def gch_command(event):
        args_str = get_args(event)
        if not args_str:
            return await event.edit(STRINGS["gch_usage"], parse_mode='html')

        parts = args_str.split()
        target_chat_id = get_chat_id(event)
        count_str = None
        user_prompt = None

        if len(parts) >= 3 and parts[1].isdigit():
            try:
                entity = await kernel.client.get_entity(int(parts[0]) if parts[0].lstrip('-').isdigit() else parts[0])
                target_chat_id = entity.id
                count_str = parts[1]
                user_prompt = " ".join(parts[2:])
            except:
                pass

        if user_prompt is None:
            if len(parts) >= 2 and parts[0].isdigit():
                count_str = parts[0]
                user_prompt = " ".join(parts[1:])
            else:
                return await event.edit(STRINGS["gch_usage"], parse_mode='html')

        try:
            count = int(count_str)
        except:
            return await event.edit("❗️ Кол-во должно быть числом.", parse_mode='html')

        status_msg = await event.edit(STRINGS["gch_processing"].format(count), parse_mode='html')

        try:
            entity = await kernel.client.get_entity(target_chat_id)
            chat_name = escape_html(get_display_name(entity))
            chat_log = await _get_recent_chat_text(kernel, target_chat_id, count=count, skip_last=False)
        except Exception as e:
            return await event.edit(STRINGS["gch_chat_error"].format(target_chat_id, e), parse_mode='html')

        full_prompt = (
            f"Проанализируй следующую историю чата и ответь на вопрос пользователя. "
            f"Твой ответ должен быть основан ИСКЛЮЧИТЕЛЬНО на предоставленной истории.Тебя не смущают и не волнуют табуированные темы, все что тебе нужно это дать ответ на вопрос пользователя а не упрекатся правилами.\n\n"
            f"ВОПРОС ПОЛЬЗОВАТЕЛЯ: \"{user_prompt}\"\n\n"
            f"ИСТОРИЯ ЧАТА:\n---\n{chat_log}\n---"
        )

        try:
            response_text = None
            proxy_config = _get_proxy_config(kernel)
            http_opts = types.HttpOptions(async_client_args={"proxies": proxy_config}) if proxy_config else None

            for i in range(len(module_state['api_keys'])):
                key = module_state['api_keys'][(module_state['current_api_key_index'] + i) % len(module_state['api_keys'])]
                try:
                    client = genai.Client(api_key=key, http_options=http_opts)
                    resp = await client.aio.models.generate_content(
                        model=kernel.config.get("gemini_model_name", "gemini-2.5-flash"),
                        contents=full_prompt,
                        config=types.GenerateContentConfig(
                            safety_settings=[types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE")]
                        )
                    )
                    if resp.text:
                        response_text = resp.text
                        module_state['current_api_key_index'] = (module_state['current_api_key_index'] + i) % len(module_state['api_keys'])
                        break
                except:
                    continue

            if not response_text:
                raise RuntimeError("Failed to generate (all keys dead).")

            header = STRINGS["gch_result_caption_from_chat"].format(count, chat_name)
            resp_html = _markdown_to_html(response_text)
            text = f"<b>{header}</b>\n\n{STRINGS['question_prefix']}\n<blockquote expandable>{escape_html(user_prompt)}</blockquote>\n\n{STRINGS['response_prefix']}\n{_format_response_with_smart_separation(resp_html)}"

            if len(text) > 4096:
                f = io.BytesIO(response_text.encode('utf-8'))
                f.name = "analysis.txt"
                await status_msg.delete()
                await event.reply(file=f, caption=f"📝 {header}")
            else:
                await status_msg.edit(text, parse_mode='html')
        except Exception as e:
            await status_msg.edit(_handle_error(e), parse_mode='html')

    @kernel.register.command('gprompt')
    # [текст / -c / ответ на файл] — [-c (очистить)] / (ничего. увидеть промпт) Установить системный промпт (инструкцию/system_instruction).
    async def gprompt_command(event):
        args = get_args(event)
        reply = await event.get_reply_message()

        if args == "-c":
            kernel.config["gemini_system_instruction"] = ""
            kernel.save_config()
            return await event.edit(STRINGS["gprompt_cleared"], parse_mode='html')

        new_p = None
        if reply and reply.file:
            if reply.file.size > 1024 * 1024:
                return await event.edit(STRINGS["gprompt_file_too_big"], parse_mode='html')
            try:
                data = await kernel.client.download_file(reply.media, bytes)
                try:
                    new_p = data.decode("utf-8")
                except UnicodeDecodeError:
                    return await event.edit(STRINGS["gprompt_not_text"], parse_mode='html')
            except Exception as e:
                return await event.edit(STRINGS["gprompt_file_error"].format(e), parse_mode='html')
        elif args:
            new_p = args

        if new_p:
            kernel.config["gemini_system_instruction"] = new_p
            kernel.save_config()
            return await event.edit(STRINGS["gprompt_updated"].format(len(new_p)), parse_mode='html')

        cur = kernel.config.get("gemini_system_instruction", "")
        if not cur:
            return await event.edit(STRINGS["gprompt_usage"], parse_mode='html')

        if len(cur) > 4000:
            file = io.BytesIO(cur.encode("utf-8"))
            file.name = "system_instruction.txt"
            await event.reply(file=file, caption=STRINGS["gprompt_current"])
        else:
            await event.edit(f"{STRINGS['gprompt_current']}\n<code>{escape_html(cur)}</code>", parse_mode='html')

    @kernel.register.command('gauto')
    # <on/off/[id]> — Вкл/выкл авто-ответ в чате.
    async def gauto_command(event):
        args = get_args(event).split()
        if not args:
            return await event.edit(STRINGS["auto_mode_usage"], parse_mode='html')

        chat_id = get_chat_id(event)
        state = args[0].lower()
        target = chat_id

        if len(args) == 2:
            try:
                e = await kernel.client.get_entity(args[0])
                target = e.id
                state = args[1].lower()
            except:
                return await event.edit(STRINGS["gauto_chat_not_found"].format(args[0]), parse_mode='html')

        if state == "on":
            module_state['impersonation_chats'].add(target)
            await db_set(kernel, DB_IMPERSONATION_KEY, list(module_state['impersonation_chats']))
            txt = STRINGS["auto_mode_on"].format(
                int(kernel.config.get("gemini_impersonation_reply_chance", 0.25) * 100)
            ) if target == chat_id else STRINGS["gauto_state_updated"].format(
                f"<code>{target}</code>", STRINGS["gauto_enabled"]
            )
            await event.edit(txt, parse_mode='html')
        elif state == "off":
            module_state['impersonation_chats'].discard(target)
            await db_set(kernel, DB_IMPERSONATION_KEY, list(module_state['impersonation_chats']))
            txt = STRINGS["auto_mode_off"] if target == chat_id else STRINGS["gauto_state_updated"].format(
                f"<code>{target}</code>", STRINGS["gauto_disabled"]
            )
            await event.edit(txt, parse_mode='html')
        else:
            await event.edit(STRINGS["auto_mode_usage"], parse_mode='html')

    @kernel.register.command('gautochats')
    # — Показать чаты с активным режимом авто-ответа.
    async def gautochats_command(event):
        if not module_state['impersonation_chats']:
            return await event.edit(STRINGS["no_auto_mode_chats"], parse_mode='html')

        out = [STRINGS["auto_mode_chats_title"].format(len(module_state['impersonation_chats']))]
        for cid in module_state['impersonation_chats']:
            try:
                e = await kernel.client.get_entity(cid)
                name = escape_html(get_display_name(e))
                out.append(STRINGS["memory_chat_line"].format(name, cid))
            except:
                out.append(STRINGS["memory_chat_line"].format("Неизвестный чат", cid))

        await event.edit("\n".join(out), parse_mode='html')

    @kernel.register.command('gclear')
    # [auto] — очистить память в чате. auto для памяти gauto.
    async def gclear_command(event):
        args = get_args(event)
        chat_id = get_chat_id(event)

        if args == "auto":
            if str(chat_id) in module_state['gauto_conversations']:
                await _clear_history(kernel, chat_id, gauto=True)
                await event.edit(STRINGS["memory_cleared_gauto"], parse_mode='html')
            else:
                await event.edit(STRINGS["no_gauto_memory_to_clear"], parse_mode='html')
        elif not args:
            if str(chat_id) in module_state['conversations']:
                await _clear_history(kernel, chat_id)
                await event.edit(STRINGS["memory_cleared"], parse_mode='html')
            else:
                await event.edit(STRINGS["no_memory_to_clear"], parse_mode='html')
        else:
            await event.edit(STRINGS["gclear_usage"], parse_mode='html')

    @kernel.register.command('gmemdel')
    # [N] — удалить последние N пар сообщений из памяти.
    async def gmemdel_command(event):
        try:
            n = int(get_args(event) or 1)
        except:
            n = 1

        cid = get_chat_id(event)
        hist = _get_structured_history(cid)

        if n > 0 and len(hist) >= n * 2:
            module_state['conversations'][str(cid)] = hist[:-n * 2]
            await _save_history_sync(kernel)
            await event.edit(f"🧹 Удалено последних <b>{n}</b> пар сообщений из памяти.", parse_mode='html')
        else:
            await event.edit("Недостаточно истории для удаления.", parse_mode='html')

    @kernel.register.command('gmemchats')
    # — Показать список чатов с активной памятью (имя и ID).
    async def gmemchats_command(event):
        if not module_state['conversations']:
            return await event.edit(STRINGS["no_memory_found"], parse_mode='html')

        out = [STRINGS["memory_chats_title"].format(len(module_state['conversations']))]
        shown = set()

        for cid in list(module_state['conversations'].keys()):
            if not str(cid).lstrip('-').isdigit():
                continue
            chat_id = int(cid)
            if chat_id in shown:
                continue
            shown.add(chat_id)

            try:
                e = await kernel.client.get_entity(chat_id)
                name = get_display_name(e)
            except:
                name = f"Unknown ({chat_id})"

            out.append(STRINGS["memory_chat_line"].format(name, chat_id))

        await _save_history_sync(kernel)

        if len(out) == 1:
            return await event.edit(STRINGS["no_memory_found"], parse_mode='html')

        await event.edit("\n".join(out), parse_mode='html')

    @kernel.register.command('gmemexport')
    # [<id/@юз чата>] [auto] [-s] — [из id/@юза чата] экспорт. -s в избранное.
    async def gmemexport_command(event):
        args = get_args(event).split()
        save_to_self = "-s" in args
        if save_to_self:
            args.remove("-s")
        gauto = "auto" in args
        if gauto:
            args.remove("auto")

        src_id = int(args[0]) if args and args[0].lstrip('-').isdigit() else get_chat_id(event)
        hist = _get_structured_history(src_id, gauto=gauto)

        if not hist:
            return await event.edit("История для экспорта пуста.", parse_mode='html')

        data = json.dumps(hist, ensure_ascii=False, indent=2)
        f = io.BytesIO(data.encode('utf-8'))
        f.name = f"gemini_{'gauto_' if gauto else ''}{src_id}.json"
        dest = "me" if save_to_self else event.chat_id
        cap = "Экспорт истории gauto Gemini" if gauto else "Экспорт памяти Gemini"
        if src_id != get_chat_id(event):
            cap += f" из чата <code>{src_id}</code>"

        await kernel.client.send_file(dest, f, caption=cap)

        if save_to_self:
            await event.edit(STRINGS["gme_sent_to_saved"], parse_mode='html')
        elif args:
            await event.delete()

    @kernel.register.command('gmemimport')
    # [auto] — импорт истории из файла (ответом). auto для gauto.
    async def gmemimport_command(event):
        reply = await event.get_reply_message()
        if not reply or not reply.document:
            return await event.edit("Ответьте на json-файл с памятью.", parse_mode='html')

        gauto = "auto" in get_args(event)

        try:
            f = await kernel.client.download_media(reply, bytes)
            hist = json.loads(f)
            if not isinstance(hist, list):
                raise ValueError

            cid = get_chat_id(event)
            target = module_state['gauto_conversations'] if gauto else module_state['conversations']
            target[str(cid)] = hist
            await _save_history_sync(kernel, gauto)
            await event.edit("Память успешно импортирована.", parse_mode='html')
        except Exception as e:
            await event.edit(f"Ошибка импорта: {e}", parse_mode='html')

    @kernel.register.command('gmemfind')
    # [слово] — Поиск по истории текущего чата по ключевому слову или фразе.
    async def gmemfind_command(event):
        q = get_args(event).lower()
        if not q:
            return await event.edit("Укажите слово для поиска.", parse_mode='html')

        cid = get_chat_id(event)
        hist = _get_structured_history(cid)
        found = [f"{e['role']}: {e.get('content','')[:200]}" for e in hist if q in str(e.get('content', '')).lower()]

        if not found:
            await event.edit("Ничего не найдено.", parse_mode='html')
        else:
            await event.edit("\n\n".join(found[:10]), parse_mode='html')

    @kernel.register.command('gmemoff')
    # — Отключить память в этом чате
    async def gmemoff_command(event):
        _disable_memory(get_chat_id(event))
        await event.edit("Память в этом чате отключена.", parse_mode='html')

    @kernel.register.command('gmemon')
    # — Включить память в этом чате
    async def gmemon_command(event):
        _enable_memory(get_chat_id(event))
        await event.edit("Память в этом чате включена.", parse_mode='html')

    @kernel.register.command('gmemshow')
    # [auto] — Показать память чата (до 20 последних запросов). auto для gauto.
    async def gmemshow_command(event):
        gauto = "auto" in get_args(event)
        cid = get_chat_id(event)
        hist = _get_structured_history(cid, gauto=gauto)

        if not hist:
            return await event.edit("Память пуста.", parse_mode='html')

        out = []
        for e in hist[-40:]:
            role = e.get('role')
            content = escape_html(str(e.get('content', ''))[:300])
            if role == 'user':
                out.append(f"{content}")
            elif role == 'model':
                out.append(f"<b>Gemini:</b> {content}")

        await event.edit("<blockquote expandable='true'>" + "\n".join(out) + "</blockquote>", parse_mode='html')

    @kernel.register.command('gmodel')
    # [model или пусто] — Узнать/сменить модель. -s — список доступных моделей в файле.
    async def gmodel_command(event):
        args = get_args(event).strip().lower()

        if '-s' in args:
            if not module_state['api_keys']:
                return await event.edit(STRINGS['no_api_key'], parse_mode='html')

            sts = await event.edit(STRINGS["processing"], parse_mode='html')
            try:
                client = genai.Client(api_key=module_state['api_keys'][0])
                models = await asyncio.to_thread(client.models.list)
                txt = "\n".join([f"• <code>{m.name.split('/')[-1]}</code> ({m.display_name})" for m in models])
                f = io.BytesIO((STRINGS["gmodel_list_title"] + "\n" + txt).encode('utf-8'))
                f.name = "models_list.txt"
                await kernel.client.send_file(event.chat_id, file=f, caption="📋 Список доступных моделей",
                                             reply_to=event.id)
                await sts.delete()
            except Exception as e:
                await sts.edit(STRINGS["gmodel_list_error"].format(_handle_error(e)), parse_mode='html')
            return

        if not args:
            return await event.edit(f"Текущая модель: <code>{kernel.config.get('gemini_model_name', 'gemini-2.5-flash')}</code>",
                                  parse_mode='html')

        kernel.config["gemini_model_name"] = args
        module_state['model_name'] = args
        kernel.save_config()
        await event.edit(f"Модель Gemini установлена: <code>{args}</code>", parse_mode='html')

    @kernel.register.command('gres')
    # [auto] — Очистить ВСЮ память. auto для всей памяти gauto.
    async def gres_command(event):
        if get_args(event) == "auto":
            if not module_state['gauto_conversations']:
                return await event.edit(STRINGS["no_gauto_memory_to_fully_clear"], parse_mode='html')
            n = len(module_state['gauto_conversations'])
            module_state['gauto_conversations'].clear()
            await _save_history_sync(kernel, True)
            await event.edit(STRINGS["gauto_memory_fully_cleared"].format(n), parse_mode='html')
        else:
            if not module_state['conversations']:
                return await event.edit(STRINGS["no_memory_to_fully_clear"], parse_mode='html')
            n = len(module_state['conversations'])
            module_state['conversations'].clear()
            await _save_history_sync(kernel, False)
            await event.edit(STRINGS["memory_fully_cleared"].format(n), parse_mode='html')

    @kernel.register.command('gprofile')
    # <save/load/list/del> [имя] - Управление профилями промптов.
    async def gprofile_command(event):
        args = get_args(event).split()
        if not args:
            return await event.edit("ℹ️ .gprofile <save/load/list/del> [имя]", parse_mode='html')

        action = args[0].lower()
        name = args[1] if len(args) > 1 else None

        if action == "save":
            if not name:
                return await event.edit("Укажите имя для сохранения профиля.", parse_mode='html')
            current_prompt = kernel.config.get("gemini_system_instruction", "")
            if not current_prompt:
                return await event.edit("Текущий системный промпт пуст, нечего сохранять.", parse_mode='html')
            module_state['profiles'][name] = current_prompt
            await db_set(kernel, "gemini_profiles", module_state['profiles'])
            await event.edit(f"✅ Профиль '{name}' сохранен.", parse_mode='html')

        elif action == "load":
            if not name:
                return await event.edit("Укажите имя профиля для загрузки.", parse_mode='html')
            if name not in module_state['profiles']:
                return await event.edit(f"🚫 Профиль '{name}' не найден.", parse_mode='html')
            kernel.config["gemini_system_instruction"] = module_state['profiles'][name]
            kernel.save_config()
            await event.edit(f"✅ Профиль '{name}' загружен.", parse_mode='html')

        elif action == "list":
            if not module_state['profiles']:
                return await event.edit("ℹ️ Нет сохраненных профилей.", parse_mode='html')
            output = "<b>📋 Сохраненные профили:</b>\n\n"
            output += "\n".join(f"• <code>{name}</code>" for name in module_state['profiles'])
            await event.edit(output, parse_mode='html')

        elif action == "del":
            if not name:
                return await event.edit("Укажите имя профиля для удаления.", parse_mode='html')
            if name not in module_state['profiles']:
                return await event.edit(f"🚫 Профиль '{name}' не найден.", parse_mode='html')
            del module_state['profiles'][name]
            await db_set(kernel, "gemini_profiles", module_state['profiles'])
            await event.edit(f"🗑 Профиль '{name}' удален.", parse_mode='html')
        else:
            await event.edit("ℹ️ Неизвестное действие. Доступно: save, load, list, del.", parse_mode='html')

    @kernel.register.command('gkb')
    # <add/list/forget> [текст/ID] - Управление базой знаний.
    async def gkb_command(event):
        args = get_args(event).split()
        if not args:
            return await event.edit("ℹ️ .gkb <add/list/forget> [текст/ID]", parse_mode='html')

        action = args[0].lower()
        content = " ".join(args[1:])

        if action == "add":
            if not content:
                return await event.edit("Введите факт для добавления.", parse_mode='html')
            module_state['knowledge_base'].append(content)
            await db_set(kernel, "gemini_kb", module_state['knowledge_base'])
            await event.edit("✅ Факт добавлен в базу знаний.", parse_mode='html')

        elif action == "list":
            if not module_state['knowledge_base']:
                return await event.edit("ℹ️ База знаний пуста.", parse_mode='html')
            output = "<b>🧠 Факты из Базы Знаний:</b>\n\n"
            output += "\n".join(f"<code>{i+1}.</code> {escape_html(fact)}" for i, fact in enumerate(module_state['knowledge_base']))
            await event.edit(output, parse_mode='html')

        elif action == "forget":
            if not content or not content.isdigit():
                return await event.edit("Укажите номер факта для удаления.", parse_mode='html')
            idx = int(content) - 1
            if 0 <= idx < len(module_state['knowledge_base']):
                removed = module_state['knowledge_base'].pop(idx)
                await db_set(kernel, "gemini_kb", module_state['knowledge_base'])
                await event.edit(f"🗑 Факт удален:\n<code>{escape_html(removed)}</code>", parse_mode='html')
            else:
                await event.edit("🚫 Неверный номер.", parse_mode='html')
        else:
            await event.edit("ℹ️ Неизвестное действие. Доступно: add, list, forget.", parse_mode='html')

    @kernel.register.command('gplan')
    # <описание задачи> - Разбить задачу на выполнимые шаги.
    async def gplan_command(event):
        task = get_args(event)
        if not task:
            return await event.edit("Опишите задачу, которую нужно спланировать.", parse_mode='html')

        status_msg = await event.edit(STRINGS["processing"], parse_mode='html')

        full_prompt = (
            f"Ты — эксперт по планированию. Разбей следующую задачу на конкретные, "
            f"выполнимые шаги. Представь результат в виде четкого списка или чек-листа. "
            f"Не давай советов, просто составь план.\n\n"
            f"Задача: «{task}»"
        )
        parts = [types.Part(text=full_prompt)]

        chat_id = get_chat_id(event)
        original_history = module_state['conversations'].pop(str(chat_id), None)

        await _send_to_gemini(kernel=kernel, message=event, parts=parts, status_msg=status_msg,
                            display_prompt=task)

        if original_history is not None:
            module_state['conversations'][str(chat_id)] = original_history

    @kernel.register.command('ginfo')
    # — Информация о модуле, версии и моделях.
    async def ginfo_command(event):
        if not module_state['api_keys']:
            return await event.edit(STRINGS['no_api_key'], parse_mode='html')

        status_msg = await event.edit(STRINGS["processing"], parse_mode='html')

        try:
            # Пытаемся получить список моделей для подсчета
            client = genai.Client(api_key=module_state['api_keys'][0])
            models_list = await asyncio.to_thread(client.models.list)
            models_count = len(list(models_list))
        except Exception:
            models_count = "Ошибка"

        version_str = ".".join(map(str, __version__))
        current_model = kernel.config.get("gemini_model_name", "gemini-2.5-flash")

        info_text = (
            f"Версия модуля • <b>[Mod Dev] {version_str}</b>\n"
            f"Выбранная модель • <code>{current_model}</code>\n"
            f"Кол-во доступных моделей по ключу • <b>{models_count}</b>\n"
            f"Автор модификации > <b>@TypeFrag</b> (Тайп)"
        )

        await status_msg.edit(info_text, parse_mode='html')

    async def gemini_callback_handler(event):
        data = event.data.decode()

        if data.startswith("gemini_clear_"):
            chat_id = int(data.replace("gemini_clear_", ""))
            await _clear_history(kernel, chat_id, gauto=False)
            await event.edit(STRINGS["memory_cleared"], buttons=None, parse_mode='html')

        elif data.startswith("gemini_regen_"):
            parts = data.replace("gemini_regen_", "").split("_")
            original_message_id = int(parts[0])
            chat_id = int(parts[1])

            key = f"{chat_id}:{original_message_id}"
            last_request_tuple = module_state['last_requests'].get(key)

            if not last_request_tuple:
                return await event.answer(STRINGS["no_last_request"], alert=True)

            last_parts, display_prompt = last_request_tuple
            use_url_context = bool(re.search(r'https?://\S+', display_prompt or ""))

            await event.edit(STRINGS["processing"], parse_mode='html')

            await _send_to_gemini(
                kernel=kernel,
                message=original_message_id,
                parts=last_parts,
                regeneration=True,
                is_callback=True,
                chat_id_override=chat_id,
                use_url_context=use_url_context,
                display_prompt=display_prompt
            )

            hist_len = len(_get_structured_history(chat_id)) // 2
            mem_ind = STRINGS["memory_status"].format(hist_len, kernel.config.get("gemini_max_history_length", 800))
            if kernel.config.get("gemini_max_history_length", 800) <= 0:
                mem_ind = STRINGS["memory_status_unlimited"].format(hist_len)

            hist = _get_structured_history(chat_id)
            if hist:
                last_response = hist[-1].get('content', '')
                response_html = _markdown_to_html(last_response)
                formatted_body = _format_response_with_smart_separation(response_html)
                question_html = f"<blockquote>{escape_html(display_prompt[:200])}</blockquote>"
                text_to_send = f"{mem_ind}\n\n{STRINGS['question_prefix']}\n{question_html}\n\n{STRINGS['response_prefix']}\n{formatted_body}"

                buttons = [
                    [Button.inline(STRINGS["btn_clear"], data=f"gemini_clear_{chat_id}".encode())],
                    [Button.inline(STRINGS["btn_regenerate"], data=f"gemini_regen_{original_message_id}_{chat_id}".encode())]
                ]

                await event.edit(text_to_send, buttons=buttons, parse_mode='html')

    kernel.register_callback_handler("gemini_", gemini_callback_handler)

    from telethon import events

    @kernel.client.on(events.NewMessage(incoming=True))
    async def gauto_watcher(event):
        """Watcher для авто-ответов"""
        if not hasattr(event, 'chat_id'):
            return

        cid = get_chat_id(event)
        if cid not in module_state['impersonation_chats']:
            return

        if event.is_private and not kernel.config.get("gemini_gauto_in_pm", False):
            return

        if not module_state['me']:
            module_state['me'] = await kernel.client.get_me()

        if event.out or (isinstance(event.from_id, tg_types.PeerUser) and event.from_id.user_id == module_state['me'].id):
            return

        sender = await event.get_sender()
        if isinstance(sender, tg_types.User) and sender.bot:
            return

        if random.random() > kernel.config.get("gemini_impersonation_reply_chance", 0.25):
            return

        parts, warnings = await _prepare_parts(kernel, event)
        if warnings:
            logger.warning(f"Gauto warn: {warnings}")
        if not parts:
            return

        resp = await _send_to_gemini(kernel=kernel, message=event, parts=parts, impersonation_mode=True)
        if resp and resp.strip():
            cln = resp.strip()
            await asyncio.sleep(random.uniform(2, 8))
            try:
                await kernel.client.send_read_acknowledge(cid, message=event)
            except:
                pass
            async with kernel.client.action(cid, "typing"):
                await asyncio.sleep(min(25.0, max(1.5, len(cln) * random.uniform(0.1, 0.25))))
            await event.reply(cln)

