# author: plfkasdopfkdsofkdp
# version: 1.0.0
# description: Переводчик текста ч

import asyncio
import urllib.parse
import urllib.request
import json

def register(kernel):
    client = kernel.client
    EMOJI_LOADING = '<tg-emoji emoji-id="5323463142775202324">🏓</tg-emoji>'

    kernel.config.setdefault('tr_lang', 'ru')

    async def translate_text(text, dest='ru'):
        try:
            encoded_text = urllib.parse.quote(text)
            url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={dest}&dt=t&q={encoded_text}"

            loop = asyncio.get_event_loop()

            def sync_translate():
                req = urllib.request.Request(
                    url,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    }
                )
                with urllib.request.urlopen(req, timeout=10) as response:
                    data = json.loads(response.read().decode('utf-8'))
                    if data and len(data) > 0:
                        translated_parts = []
                        for sentence in data[0]:
                            if sentence[0]:
                                translated_parts.append(sentence[0])
                        return ''.join(translated_parts)
                    return text

            return await loop.run_in_executor(None, sync_translate)

        except Exception as e:
            return f"Ошибка: {str(e)}"

    @kernel.register_command('tr')
    # [lang/None] [text/get_reply_message]
    async def tr_handler(event):
        try:
            args = event.text.split()
            reply = await event.get_reply_message()
            text_to_translate = None
            lang = kernel.config.get('tr_lang', 'ru')

            if len(args) > 1:
                first = args[1]
                if len(first) == 2 and first.isalpha():
                    lang = first
                    text_to_translate = ' '.join(args[2:])
                else:
                    text_to_translate = ' '.join(args[1:])

            if not text_to_translate and reply and reply.text:
                text_to_translate = reply.text
            elif not text_to_translate:
                await event.edit(f"{EMOJI_LOADING} Укажите текст или ответьте на сообщение", parse_mode='html')
                return

            await event.edit(f"{EMOJI_LOADING} Перевожу...", parse_mode='html')

            translated = await translate_text(text_to_translate, dest=lang)
            await event.edit(translated)

        except Exception as e:
            await kernel.handle_error(e, source="tr_handler", event=event)
            await event.edit(f"{EMOJI_LOADING} Ошибка перевода", parse_mode='html')
