# requires:
# author: @Hairpin00
# version: 1.0.3
# description: Translator using Google Translate API

import asyncio
import json
from urllib.parse import quote
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError


def register(kernel):
    client = kernel.client

    language = kernel.config.get('language', 'en')

    strings = {
        'ru': {
            'loading': 'Перевожу...',
            'no_args': 'No args',
            'specify_text': 'Укажите текст для перевода или ответьте на сообщение',
            'no_text': 'Не указан текст для перевода',
            'translation_error': 'Ошибка перевода',
            'network_error': 'Ошибка сети:',
            'translation_failed': 'Не удалось получить перевод',
            'request_timeout': 'Таймаут запроса',
            'decode_error': 'Ошибка декодирования ответа',
            'translation_error_generic': 'Ошибка перевода:',
        },
        'en': {
            'loading': 'Translating...',
            'no_args': 'No args',
            'specify_text': 'Specify text for translation or reply to message',
            'no_text': 'No text specified for translation',
            'translation_error': 'Translation error',
            'network_error': 'Network error:',
            'translation_failed': 'Failed to get translation',
            'request_timeout': 'Request timeout',
            'decode_error': 'Response decode error',
            'translation_error_generic': 'Translation error:',
        }
    }

    lang_strings = strings.get(language, strings['en'])

    EMOJI_LOADING = '<tg-emoji emoji-id="5323463142775202324">🏓</tg-emoji>'
    EMOJI_SUCCESS = '<tg-emoji emoji-id="5118861066981344121">✅</tg-emoji>'
    EMOJI_ERROR = '<tg-emoji emoji-id="5388785832956016892">❌</tg-emoji>'

    if "tr_lang" not in kernel.config:
        kernel.config["tr_lang"] = "ru"
        kernel.save_config()

    async def translate_text(text: str, dest: str = "ru") -> str:
        try:
            encoded_text = quote(text)
            url = f"https://translate.googleapis.com/translate_a/single"

            params = {
                "client": "gtx",
                "sl": "auto",
                "tl": dest,
                "dt": "t",
                "q": encoded_text,
            }

            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            full_url = f"{url}?{query_string}"

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
            }

            req = Request(full_url, headers=headers)

            def sync_request():
                try:
                    with urlopen(req, timeout=10) as response:
                        data = response.read()
                        decoded_data = data.decode("utf-8")
                        return json.loads(decoded_data)
                except (URLError, HTTPError) as e:
                    raise Exception(f"{lang_strings['network_error']} {str(e)}")

            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, sync_request)

            if data and len(data) > 0 and data[0]:
                translated_parts = []
                for sentence in data[0]:
                    if sentence and len(sentence) > 0 and sentence[0]:
                        translated_parts.append(str(sentence[0]))
                return "".join(translated_parts)
            else:
                return lang_strings['translation_failed']

        except asyncio.TimeoutError:
            return lang_strings['request_timeout']
        except json.JSONDecodeError:
            return lang_strings['decode_error']
        except Exception as e:
            return f"{lang_strings['translation_error_generic']} {str(e)}"

    @kernel.register_command("tr")
    async def tr_handler(event):
        try:
            quote_text = None
            if event.reply_to and hasattr(event.reply_to, "quote_text"):
                quote_text = event.reply_to.quote_text

            args = event.text.split(maxsplit=2)

            target_lang = kernel.config.get("tr_lang", "ru")
            text_to_translate = None

            if quote_text:
                text_to_translate = quote_text

                if len(args) > 1:
                    lang_arg = args[1]
                    if len(lang_arg) == 2 and lang_arg.isalpha():
                        target_lang = lang_arg

                elif len(args) > 2:
                    lang_arg = args[1]
                    if len(lang_arg) == 2 and lang_arg.isalpha():
                        target_lang = lang_arg
                        text_to_translate = args[2]

            elif not text_to_translate:
                reply = await event.get_reply_message()
                reply_text = reply.text if reply else None

                if len(args) == 1:
                    if reply_text:
                        text_to_translate = reply_text
                    else:
                        await event.edit(lang_strings['no_args'])
                        return

                elif len(args) == 2:
                    arg1 = args[1]

                    if len(arg1) == 2 and arg1.isalpha():
                        if reply_text:
                            target_lang = arg1
                            text_to_translate = reply_text
                        else:
                            await event.edit(
                                f"{EMOJI_ERROR} <b>{lang_strings['specify_text']}</b>",
                                parse_mode="html",
                            )
                            return
                    else:
                        text_to_translate = arg1

                elif len(args) >= 3:
                    arg1 = args[1]
                    if len(arg1) == 2 and arg1.isalpha():
                        target_lang = arg1
                        text_to_translate = args[2]
                    else:
                        text_to_translate = " ".join(args[1:])

            if not text_to_translate:
                await event.edit(
                    f"{EMOJI_ERROR} <b>{lang_strings['no_text']}</b>",
                    parse_mode="html",
                )
                return

            status_msg = await event.edit(
                f"{EMOJI_LOADING} <b>{lang_strings['loading']}</b>", parse_mode="html"
            )

            translated = await translate_text(text_to_translate, target_lang)

            result_text = translated

            await status_msg.edit(result_text)

        except Exception as e:
            await kernel.handle_error(e, source="tr_handler", event=event)
            await event.edit(
                f"{EMOJI_ERROR} <b>{lang_strings['translation_error']}</b>\n<code>{str(e)[:200]}</code>",
                parse_mode="html",
            )
