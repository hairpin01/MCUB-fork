# requires:
# author: @Hairpin00
# version: 1.0.2
# description: menu inline test
from telethon import Button

def register(kernel):
    client = kernel.client # client
    bot = kernel.bot_client # inline bot
    @kernel.register.command('menu_button')
    # menu inline
    async def menu_cmd(event):
        # register command: {kernel.custom_prefix}menu_button. '' <- yes. "" <- no usage
        buttons = [
            {"text": "1", "type": "callback", "data": "menu_page_1"},
            {"text": "2", "type": "callback", "data": "menu_page_2"}
        ]
        success = await kernel.inline_form(
            event.chat_id,
            "menu <tg-emoji emoji-id=\"5404728536810398694\">🧊</tg-emoji>",
            buttons=buttons
        )
        if success:
            await event.delete()


    async def menu_callback_handler(event):
        data = event.data # data buttons callback

        if data == b'menu_page_1':
            buttons = [
                [
                    Button.inline("edit test", b"menu_edit_1", style="primary")
                ],
                [
                    Button.inline("<-", b"menu_main")
                ]
            ]
            await event.edit(
                "menu 1 page <tg-emoji emoji-id=\"5404728536810398694\">🧊</tg-emoji>",
                buttons=buttons,
                parse_mode='html'
            )
        elif data == b'menu_page_2':
            buttons = [
                [
                    Button.inline("edit test", b"menu_edit_2")
                ],
                [
                    Button.inline("<-", b"menu_main")
                ]
            ]
            await event.edit(
                "menu 2 page <tg-emoji emoji-id=\"5404728536810398694\">🧊</tg-emoji>",
                buttons=buttons,
                parse_mode='html'
            )
        elif data == b'menu_edit_1':
            buttons = [
                [
                    Button.inline("<-", b"menu_main")
                ]
            ]
            await event.edit(
                "hello word <tg-emoji emoji-id=\"5404728536810398694\">🧊</tg-emoji>",
                buttons=buttons,
                parse_mode='html'
                )
        elif data == b'menu_edit_2':
            buttons = [
                [
                    Button.inline("<-", b"menu_main")
                ]
            ]
            await event.edit(
                "Привет мир <tg-emoji emoji-id=\"5404728536810398694\">🧊</tg-emoji>",
                buttons=buttons,
                parse_mode='html'
                )

        else:
            buttons = [
            [
                Button.inline("1", b"menu_page_1")
            ],
            [
                Button.inline("2", b"menu_page_2")
            ]
            ]
            await event.edit(
                "menu <tg-emoji emoji-id=\"5404728536810398694\">🧊</tg-emoji>",
                buttons=buttons,
                parse_mode='html'
            )
    # register callback
    kernel.register_callback_handler("menu_", menu_callback_handler)
