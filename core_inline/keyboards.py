from telethon import Button

from .strings import get_strings


class InlineKeyboards:
    def __init__(self, kernel):
        self.kernel = kernel
        self.lang = get_strings(kernel)

    async def handle_confirm_yes(self, event):

        sender = await event.get_sender()
        chat_id = event.chat_id
        confirm_key = f"{chat_id}_{sender.id}"

        if confirm_key in self.kernel.pending_confirmations:
            saved_command = self.kernel.pending_confirmations[confirm_key]
            del self.kernel.pending_confirmations[confirm_key]

            await event.answer(f"✅ {self.lang['confirm_yes']}")
            await event.edit(
                f"✅ **{self.lang['command_confirmed']}**\n\n{self.lang['executing']}: `{saved_command}`"
            )

            await self.kernel.client.send_message(chat_id, saved_command)
        else:
            await event.answer(f"❌ {self.lang['command_not_found']}")
            await event.edit(f"❌ {self.lang['command_not_found_or_executed']}")

    async def handle_confirm_no(self, event):

        sender = await event.get_sender()
        chat_id = event.chat_id
        confirm_key = f"{chat_id}_{sender.id}"

        if confirm_key in self.kernel.pending_confirmations:
            del self.kernel.pending_confirmations[confirm_key]
            await event.answer(f"❌ {self.lang['confirm_no']}")
            await event.edit(f"❌ {self.lang['command_cancelled']}")
        else:
            await event.answer(f"❌ {self.lang['nothing_to_cancel']}")
            await event.edit(f"❌ {self.lang['nothing_to_cancel']}")

    async def handle_catalog_page(self, event):
        try:
            data_str = event.data.decode("utf-8")
        except Exception:
            await event.answer(f"⚠️ {self.lang['data_error']}", alert=True)
            return

        try:
            page = int(data_str.split("_")[1])
        except (IndexError, ValueError):
            await event.answer(f"⚠️ {self.lang['invalid_format']}", alert=True)
            return

        await event.answer()

        if not hasattr(self.kernel, "catalog_cache") or not self.kernel.catalog_cache:
            await event.edit(f"❌ {self.lang['catalog_not_loaded']}")
            return

        catalog = self.kernel.catalog_cache
        modules_list = list(catalog.items())
        per_page = 5
        total_pages = (len(modules_list) + per_page - 1) // per_page

        if page < 1:
            page = 1
        if page > total_pages:
            page = total_pages

        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_modules = modules_list[start_idx:end_idx]

        msg = f"📚 <b>{self.lang['catalog_title']}</b> ({self.lang['page']}. {page}/{total_pages})\n\n"
        for module_name, info in page_modules:
            msg += f"• <b>{module_name}</b>\n"
            msg += f"  {info.get('description', self.lang['no_description'])}\n"
            if "author" in info:
                msg += f"  👤 {self.lang['author']}: @{info['author']}\n"
            if "commands" in info:
                msg += f"  {self.lang['commands']}: {', '.join(info['commands'])}\n"
            msg += "\n"

        msg += f"\n{self.lang['use_dlm']}: <code>{self.kernel.custom_prefix}dlm название</code>"

        buttons = []
        nav_buttons = []
        if page > 1:
            nav_buttons.append(
                Button.inline(f"⬅️ {self.lang['nav_back']}", f"dlml_{page - 1}".encode())
            )
        if page < total_pages:
            nav_buttons.append(
                Button.inline(
                    f"➡️ {self.lang['nav_forward']}", f"dlml_{page + 1}".encode()
                )
            )

        if nav_buttons:
            buttons.append(nav_buttons)

        await event.edit(msg, buttons=buttons if buttons else None, parse_mode="html")
