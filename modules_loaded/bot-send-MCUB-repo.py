# requires:
# author: @Hairpin00
# version: 1.0.2
# description: отправить соо ботом
from telethon import events, Button
from utils.arg_parser import parse_arguments

def register(kernel):
    client = kernel.client
    bot = kernel.bot_client
    @kernel.register.command('bot') # <msg> - ваше соо (html поддерживает)
    async def bot_cmd(event):
        parser = parse_arguments(event.text, kernel.custom_prefix)
        args = parser.args
        reply = None

        if event.reply_to_msg_id:
            replied_message = await event.get_reply_message()
            if replied_message and replied_message.reply_to_msg_id:
                reply = event.reply_to_msg_id
            else:
                reply = event.reply_to_msg_id

        buttons = [
            [Button.inline('on', b'botik_on')],
            [Button.inline('off', b'botik_off')]
            ]

        if not args:
            await event.edit("напиши соо хотяб")
            return
        message = " ".join(map(str, args))
        try:
            await bot.send_message(
                event.chat_id,
                message,
                reply_to=reply,
                parse_mode='html',
                buttons=buttons
            )
            await event.delete()
        except Exception as e:
            await kernel.handle_error(e, source="bot_cmd", event=event)
            await event.edit(f"Ошибко: {e}")
    async def bot_on_callback(event):
        data = event.data
        if data == b'botik_on':
            await event.edit("<blockquote>кнопко</blockquote>", parse_mode='html')
        else:
            await event.answer("шо тибе")
    kernel.register_callback_handler("botik", bot_on_callback)
