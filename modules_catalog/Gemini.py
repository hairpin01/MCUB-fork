from telethon import events
import asyncio
import random
import json
import html
import io
import os
import re
from datetime import datetime
from pathlib import Path
import pytz

try:
    import google.generativeai as genai
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

def register(client):
    class GeminiModule:
        def __init__(self, client):
            self.client = client
            self.config = {
                "api_keys": [],
                "model": "gemini-1.5-flash",
                "temperature": 1.0,
                "max_history_length": 20,
                "impersonation_reply_chance": 0.2,
                "system_prompt": "",
                "gauto_in_pm": False,
                "timezone": "Europe/Moscow",
                "use_expandable": True,
                "max_response_length": 1500,
                "use_inline": True,
                "show_buttons": True,
                "inline_bot_username": None,
            }

            self.conversations = {}
            self.gauto_conversations = {}
            self.impersonation_chats = set()
            self.data_dir = Path("gemini_data")
            self.data_dir.mkdir(exist_ok=True)

            self.me = None
            self.current_api_key_index = 0

        async def initialize(self):
            self.me = await self.client.get_me()
            await self.load_config()
            await self.load_data()

        async def load_config(self):
            config_file = self.data_dir / "config.json"
            if config_file.exists():
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        loaded_config = json.load(f)
                        for key in self.config:
                            if key in loaded_config:
                                self.config[key] = loaded_config[key]
                except Exception:
                    pass

        async def save_config(self):
            config_file = self.data_dir / "config.json"
            try:
                with open(config_file, 'w', encoding='utf-8') as f:
                    json.dump(self.config, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

        async def load_data(self):
            try:
                conv_file = self.data_dir / "conversations.json"
                if conv_file.exists():
                    with open(conv_file, 'r', encoding='utf-8') as f:
                        self.conversations = json.load(f)

                gauto_file = self.data_dir / "gauto_conversations.json"
                if gauto_file.exists():
                    with open(gauto_file, 'r', encoding='utf-8') as f:
                        self.gauto_conversations = json.load(f)

                imp_file = self.data_dir / "impersonation_chats.json"
                if imp_file.exists():
                    with open(imp_file, 'r', encoding='utf-8') as f:
                        self.impersonation_chats = set(json.load(f))
            except Exception:
                pass

        async def save_data(self, data_type="all"):
            try:
                if data_type in ["all", "conversations"]:
                    conv_file = self.data_dir / "conversations.json"
                    with open(conv_file, 'w', encoding='utf-8') as f:
                        json.dump(self.conversations, f, ensure_ascii=False, indent=2)

                if data_type in ["all", "gauto"]:
                    gauto_file = self.data_dir / "gauto_conversations.json"
                    with open(gauto_file, 'w', encoding='utf-8') as f:
                        json.dump(self.gauto_conversations, f, ensure_ascii=False, indent=2)

                if data_type in ["all", "impersonation"]:
                    imp_file = self.data_dir / "impersonation_chats.json"
                    with open(imp_file, 'w', encoding='utf-8') as f:
                        json.dump(list(self.impersonation_chats), f, ensure_ascii=False, indent=2)
            except Exception:
                pass

        def _get_conversation_history(self, chat_id, gauto=False):
            conversations = self.gauto_conversations if gauto else self.conversations
            chat_key = str(chat_id)
            return conversations.get(chat_key, [])

        def _update_conversation_history(self, chat_id, user_message, ai_response, gauto=False):
            conversations = self.gauto_conversations if gauto else self.conversations
            chat_key = str(chat_id)

            if chat_key not in conversations:
                conversations[chat_key] = []

            conversations[chat_key].append({
                'role': 'user',
                'content': user_message,
                'timestamp': datetime.now().isoformat()
            })

            conversations[chat_key].append({
                'role': 'assistant',
                'content': ai_response,
                'timestamp': datetime.now().isoformat()
            })

            max_len = self.config["max_history_length"]
            if max_len > 0 and len(conversations[chat_key]) > max_len * 2:
                conversations[chat_key] = conversations[chat_key][-max_len * 2:]

        def _clear_conversation_history(self, chat_id, gauto=False):
            conversations = self.gauto_conversations if gauto else self.conversations
            chat_key = str(chat_id)
            if chat_key in conversations:
                del conversations[chat_key]

        async def _prepare_prompt(self, event, custom_text=None):
            prompt_parts = []

            reply = await event.get_reply_message()

            if reply and reply.text:
                try:
                    from telethon.utils import get_display_name
                    reply_sender = await reply.get_sender()
                    reply_name = get_display_name(reply_sender) if reply_sender else "Unknown"
                    reply_text = self._clean_text(reply.text)
                    prompt_parts.append(f"{reply_name}: {reply_text}")
                except Exception:
                    reply_text = self._clean_text(reply.text)
                    prompt_parts.append(f"Ответ на: {reply_text}")

            user_text = custom_text if custom_text is not None else (event.pattern_match.group(1) or "").strip()
            if user_text:
                try:
                    from telethon.utils import get_display_name
                    current_sender = await event.get_sender()
                    current_name = get_display_name(current_sender) if current_sender else "User"
                    cleaned_text = self._clean_text(user_text)
                    prompt_parts.append(f"{current_name}: {cleaned_text}")
                except Exception:
                    cleaned_text = self._clean_text(user_text)
                    prompt_parts.append(f"Запрос: {cleaned_text}")

            return "\n".join(prompt_parts).strip()

        def _clean_text(self, text):
            if not text:
                return text

            text = str(text)

            invisible_chars = [
                '\u200b', '\u200c', '\u200d', '\u200e', '\u200f',
                '\u202a', '\u202b', '\u202c', '\u202d', '\u202e',
                '\u2060', '\u2061', '\u2062', '\u2063', '\u2064',
                '\ufeff', '\u00a0', '\u2028', '\u2029', '\u3000',
                '\u3164', '\uffa0',
            ]

            for char in invisible_chars:
                text = text.replace(char, ' ')

            text = text.replace('󠆜', '')

            text = ' '.join(text.split())

            return text.strip()

        def _format_response(self, text):
            if not text:
                return text

            text = str(text)

            text = html.escape(text)

            text = text.replace('&quot;', '"').replace('&#34;', '"')
            text = text.replace('&#39;', "'").replace('&#x27;', "'")
            text = text.replace('&amp;', '&')
            text = text.replace('&lt;', '<')
            text = text.replace('&gt;', '>')
            text = text.replace('&nbsp;', ' ')

            return text

        async def _call_gemini_api(self, prompt, chat_id=None, gauto=False):
            api_keys = self.config["api_keys"]
            if not api_keys:
                raise ValueError("No API keys configured")

            messages = []
            if chat_id is not None:
                history = self._get_conversation_history(chat_id, gauto)
                for msg in history:
                    role = "user" if msg['role'] == 'user' else "model"
                    messages.append({"role": role, "parts": [msg['content']]})

            system_prompt = self.config["system_prompt"]
            if system_prompt and not gauto:
                messages.insert(0, {"role": "user", "parts": [f"System: {system_prompt}\n\n"]})

            try:
                user_timezone = pytz.timezone(self.config["timezone"])
            except pytz.UnknownTimeZoneError:
                user_timezone = pytz.utc

            now = datetime.now(user_timezone)
            time_str = now.strftime("%Y-%m-%d %H:%M:%S %Z")
            time_note = f"[System note: Current time is {time_str}]"
            messages.append({"role": "user", "parts": [f"{time_note}\n\n{prompt}"]})

            for i, api_key in enumerate(api_keys):
                try:
                    genai.configure(api_key=api_key)

                    model_kwargs = {
                        "model_name": self.config["model"]
                    }

                    try:
                        from google.generativeai.types import HarmCategory, HarmBlockThreshold
                        safety_settings = {
                            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                        }
                        model_kwargs["safety_settings"] = safety_settings
                    except ImportError:
                        pass

                    model = genai.GenerativeModel(**model_kwargs)

                    response = await asyncio.wait_for(
                        model.generate_content_async(
                            messages,
                            generation_config=genai.types.GenerationConfig(
                                temperature=float(self.config["temperature"])
                            )
                        ),
                        timeout=120
                    )

                    self.current_api_key_index = i

                    if response.text:
                        return response.text
                    else:
                        raise ValueError("Empty response from Gemini")

                except Exception as e:
                    if i == len(api_keys) - 1:
                        raise e
                    continue

            return None

        async def _should_send_as_file(self, response_text):
            max_length = self.config.get("max_response_length", 1500)
            return len(response_text) > max_length

        async def _send_as_file(self, event, prompt, response):
            file_content = f"Вопрос: {prompt}\n\nОтвет Gemini:\n{response}"

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"gemini_response_{timestamp}.txt"

            file = io.BytesIO(file_content.encode('utf-8'))
            file.name = filename

            await event.delete()
            await event.respond(
                file=file,
                caption=f"💬 Ответ Gemini слишком длинный ({len(response)} символов)"
            )

        async def _send_inline_response(self, event, prompt, response_text):
            cleaned_prompt = self._clean_text(prompt)
            escaped_prompt = html.escape(cleaned_prompt)

            if len(cleaned_prompt) > 200:
                question_html = f"<blockquote expandable>{escaped_prompt}</blockquote>"
            else:
                question_html = f"<blockquote>{escaped_prompt}</blockquote>"

            response = self._format_response(response_text)

            if self.config.get("use_expandable", True) and (len(response) > 200 or response.count('\n') > 3):
                response_html = f"<blockquote expandable>{response}</blockquote>"
            else:
                response_html = f"<blockquote>{response}</blockquote>"

            base_text = f"💬 <b>Запрос:</b>\n{question_html}\n\n✨ <b>Gemini:</b>\n{response_html}"

            if self.config.get("show_buttons", True) and self.config.get("inline_bot_username"):
                query = f"{base_text} | 🔧 Настройки:.gcfg | 🧹 Очистить:.gclear | 📝 Промпт:.gprompt | 🔄 Перегенерация:.gres"

                try:
                    bot_username = self.config["inline_bot_username"]
                    await event.delete()

                    results = await self.client.inline_query(bot_username, query)
                    if results:
                        await results[0].click(event.chat_id)
                        return
                except Exception as e:
                    print(f"Инлайн ошибка: {e}")
                    pass

            if len(base_text) > 4096:
                await self._send_as_file(event, prompt, response_text)
            else:
                await event.edit(base_text, parse_mode='HTML')

        async def gg_command(self, event):
            if not GOOGLE_AVAILABLE:
                await event.edit("❌ Google Generative AI не установлен.")
                return

            if not self.config["api_keys"]:
                await event.edit("❗️ Api ключ(и) не настроен(ы).")
                return

            await event.edit("⌛️ Обработка...")

            try:
                prompt = await self._prepare_prompt(event)

                if not prompt:
                    await event.edit("⚠️ Нужен текст или ответ на медиа/файл.")
                    return

                response_text = await self._call_gemini_api(prompt, event.chat_id)

                if not response_text:
                    await event.edit("❌ Не удалось получить ответ от Gemini")
                    return

                self._update_conversation_history(event.chat_id, prompt, response_text)
                await self.save_data("conversations")

                if await self._should_send_as_file(response_text):
                    await self._send_as_file(event, prompt, response_text)
                    return

                await self._send_inline_response(event, prompt, response_text)

            except Exception as e:
                error_msg = str(e)
                await event.edit(f"❗️ Ошибка: {html.escape(error_msg[:200])}")

        async def gclear_command(self, event):
            args = (event.pattern_match.group(1) or "").strip()

            if args == "auto":
                if str(event.chat_id) in self.gauto_conversations:
                    self._clear_conversation_history(event.chat_id, gauto=True)
                    await self.save_data("gauto")
                    await event.edit("🧹 Память gauto в этом чате очищена.")
                else:
                    await event.edit("ℹ️ В этом чате нет истории gauto.")
            else:
                if str(event.chat_id) in self.conversations:
                    self._clear_conversation_history(event.chat_id, gauto=False)
                    await self.save_data("conversations")
                    await event.edit("🧹 Память диалога очищена.")
                else:
                    await event.edit("ℹ️ В этом чате нет истории.")

        async def gauto_command(self, event):
            args = (event.pattern_match.group(1) or "").strip().lower()

            if args == "on":
                self.impersonation_chats.add(event.chat_id)
                await self.save_data("impersonation")
                chance = int(float(self.config["impersonation_reply_chance"]) * 100)
                await event.edit(f"🎭 Режим авто-ответа включен в этом чате.\nВероятность ответа: {chance}%.")
            elif args == "off":
                self.impersonation_chats.discard(event.chat_id)
                await self.save_data("impersonation")
                await event.edit("🎭 Режим авто-ответа выключен в этом чате.")
            else:
                await event.edit("ℹ️ Использование: .gauto on/off")

        async def gmodel_command(self, event):
            args = (event.pattern_match.group(1) or "").strip()

            if args:
                self.config["model"] = args
                await self.save_config()
                await event.edit(f"✅ Модель изменена на: {args}")
            else:
                await event.edit(f"📋 Текущая модель: {self.config['model']}")

        async def gprompt_command(self, event):
            args = (event.pattern_match.group(1) or "").strip()

            if args == "-c":
                self.config["system_prompt"] = ""
                await self.save_config()
                await event.edit("🗑 Системный промпт очищен.")
                return

            if args:
                self.config["system_prompt"] = args
                await self.save_config()
                await event.edit(f"✅ Системный промпт обновлен!\nДлина: {len(args)} симв.")
            else:
                system_prompt = self.config["system_prompt"]
                if system_prompt:
                    await event.edit(f"📝 Текущий системный промпт:\n<code>{html.escape(system_prompt[:4000])}</code>")
                else:
                    await event.edit("ℹ️ Использование: .gprompt <текст>")

        async def gres_command(self, event):
            args = (event.pattern_match.group(1) or "").strip()

            if args == "auto":
                self.gauto_conversations.clear()
                await self.save_data("gauto")
                await event.edit("🧹 Вся память gauto очищена")
            else:
                chat_key = str(event.chat_id)
                if chat_key in self.conversations and len(self.conversations[chat_key]) >= 2:
                    self.conversations[chat_key] = self.conversations[chat_key][:-2]
                    await self.save_data("conversations")
                    await event.edit("🔄 Последний ответ удален, используйте .gg для нового запроса")
                else:
                    await event.edit("ℹ️ Нет истории для перегенерации")

        async def gconfig_command(self, event):
            args = (event.pattern_match.group(1) or "").strip()

            if not args:
                await event.edit("ℹ️ Использование: .gconfig <переменная> <значение>")
                return

            parts = args.split(maxsplit=2)

            if len(parts) >= 2:
                key = parts[0]
                value = parts[1] if len(parts) == 2 else parts[1] + " " + parts[2]

                if key not in self.config:
                    await event.edit(f"❌ Настройка не найдена: {key}")
                    return

                try:
                    if key == "api_keys":
                        new_keys = [k.strip() for k in value.split(",") if k.strip()]
                        self.config[key] = new_keys
                    elif key == "temperature":
                        new_val = float(value)
                        if not 0.0 <= new_val <= 2.0:
                            raise ValueError("Temperature must be between 0.0 and 2.0")
                        self.config[key] = new_val
                    elif key == "max_history_length":
                        new_val = int(value)
                        if new_val < 0:
                            raise ValueError("Max history length must be >= 0")
                        self.config[key] = new_val
                    elif key == "impersonation_reply_chance":
                        new_val = float(value)
                        if not 0.0 <= new_val <= 1.0:
                            raise ValueError("Reply chance must be between 0.0 and 1.0")
                        self.config[key] = new_val
                    elif key == "gauto_in_pm":
                        if value.lower() in ["true", "1", "yes", "on"]:
                            self.config[key] = True
                        elif value.lower() in ["false", "0", "no", "off"]:
                            self.config[key] = False
                        else:
                            raise ValueError("Must be true/false")
                    elif key == "use_expandable":
                        if value.lower() in ["true", "1", "yes", "on"]:
                            self.config[key] = True
                        elif value.lower() in ["false", "0", "no", "off"]:
                            self.config[key] = False
                        else:
                            raise ValueError("Must be true/false")
                    elif key == "max_response_length":
                        new_val = int(value)
                        if new_val < 100:
                            raise ValueError("Max response length must be >= 100")
                        self.config[key] = new_val
                    elif key == "use_inline":
                        if value.lower() in ["true", "1", "yes", "on"]:
                            self.config[key] = True
                        elif value.lower() in ["false", "0", "no", "off"]:
                            self.config[key] = False
                        else:
                            raise ValueError("Must be true/false")
                    elif key == "show_buttons":
                        if value.lower() in ["true", "1", "yes", "on"]:
                            self.config[key] = True
                        elif value.lower() in ["false", "0", "no", "off"]:
                            self.config[key] = False
                        else:
                            raise ValueError("Must be true/false")
                    elif key == "inline_bot_username":
                        self.config[key] = value.strip()
                    else:
                        self.config[key] = value

                    await self.save_config()
                    await event.edit(f"✅ Настройка обновлена:\n{key} = {self.config[key]}")

                except Exception as e:
                    await event.edit(f"❌ Некорректное значение для {key}: {str(e)}")
            else:
                await event.edit("ℹ️ Использование: .gconfig <переменная> <значение>")

        async def gcfg_command(self, event):
            await event.delete()

            config_text = f"""<b>⚙️ Настройки Gemini</b>

📋 <b>Текущие настройки:</b>
• Модель: <code>{self.config['model']}</code>
• Температура: <code>{self.config['temperature']}</code>
• История: <code>{self.config['max_history_length']} сообщений</code>
• Инлайн-режим: <code>{'✅' if self.config.get('use_inline', True) else '❌'}</code>
• Кнопки: <code>{'✅' if self.config.get('show_buttons', True) else '❌'}</code>
• Бот: <code>{self.config.get('inline_bot_username', 'Не настроен')}</code>

<b>Используйте команды для изменения:</b>
<code>.gconfig <переменная> <значение></code>"""


            if self.config.get("use_inline", True) and self.config.get("inline_bot_username"):
                try:
                    bot_username = self.config["inline_bot_username"]
                    query = f"{config_text} | 📝 Модель:.gmodel | 🌡 Температура:.gconfig temperature | 🔘 Кнопки:.gconfig show_buttons | 🤖 Бот:.gconfig inline_bot_username"

                    results = await self.client.inline_query(bot_username, query)
                    if results:
                        await results[0].click(event.chat_id)
                        return
                except Exception as e:
                    print(f"Инлайн ошибка в gcfg: {e}")

            await event.respond(config_text, parse_mode='HTML')

        async def ghelp_command(self, event):
            await event.delete()

            help_text = """<b>📖 Модуль Gemini - Справка</b>

<b>Основные команды:</b>
• <code>.gg [текст]</code> - запрос к Gemini
• <code>.gclear [auto]</code> - очистка памяти
• <code>.gauto on/off</code> - авто-ответ
• <code>.gmodel [модель]</code> - смена модели
• <code>.gprompt [текст]</code> - системный промпт
• <code>.gres [auto]</code> - перегенерация/очистка
• <code>.gconfig [переменная] [значение]</code> - настройка
• <code>.gcfg</code> - инлайн-настройки
• <code>.ghelp</code> - эта справка

<b>Настройка инлайн-бота:</b>
1. Получите username инлайн-бота (например <code>@onionGram_r1Z7y_robot</code>)
2. Настройте: <code>.gconfig inline_bot_username @onionGram_r1Z7y_robot</code>
3. Включите кнопки: <code>.gconfig show_buttons true</code>

<b>Примеры:</b>
<code>.gg Привет, как дела?</code>
<code>.gg (ответ на сообщение)</code>
<code>.gconfig api_keys ключ1,ключ2</code>"""

            # Проверяем, есть ли инлайн-бот
            if self.config.get("use_inline", True) and self.config.get("inline_bot_username"):
                try:
                    bot_username = self.config["inline_bot_username"]
                    query = f"{help_text} | 🔧 Настройки:.gcfg | 🧹 Очистить:.gclear | 🤖 Авто-ответ:.gauto"

                    results = await self.client.inline_query(bot_username, query)
                    if results:
                        await results[0].click(event.chat_id)
                        return
                except Exception as e:
                    print(f"Инлайн ошибка в ghelp: {e}")

            # Если инлайн не работает, отправляем обычное сообщение
            await event.respond(help_text, parse_mode='HTML')

    gemini = GeminiModule(client)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.gg(?: (.+))?'))
    async def gg_handler(event):
        await gemini.gg_command(event)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.gclear(?: (.+))?'))
    async def gclear_handler(event):
        await gemini.gclear_command(event)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.gauto(?: (.+))?'))
    async def gauto_handler(event):
        await gemini.gauto_command(event)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.gmodel(?: (.+))?'))
    async def gmodel_handler(event):
        await gemini.gmodel_command(event)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.gprompt(?: (.+))?'))
    async def gprompt_handler(event):
        await gemini.gprompt_command(event)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.gres(?: (.+))?'))
    async def gres_handler(event):
        await gemini.gres_command(event)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.gconfig(?: (.+))?'))
    async def gconfig_handler(event):
        await gemini.gconfig_command(event)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.gcfg$'))
    async def gcfg_handler(event):
        await gemini.gcfg_command(event)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ghelp$'))
    async def ghelp_handler(event):
        await gemini.ghelp_command(event)

    asyncio.create_task(gemini.initialize())
    print("✅ Модуль Gemini загружен")
