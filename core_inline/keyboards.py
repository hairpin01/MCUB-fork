from telethon import Button


class InlineKeyboards:
    def __init__(self, kernel):
        self.kernel = kernel

    async def handle_confirm_yes(self, event):

        sender = await event.get_sender()
        chat_id = event.chat_id
        confirm_key = f"{chat_id}_{sender.id}"

        if confirm_key in self.kernel.pending_confirmations:
            saved_command = self.kernel.pending_confirmations[confirm_key]
            del self.kernel.pending_confirmations[confirm_key]

            await event.answer("✅ Подтверждено")
            await event.edit(
                f"✅ **Команда подтверждена**\n\nВыполняю: `{saved_command}`"
            )

            await self.kernel.client.send_message(chat_id, saved_command)
        else:
            await event.answer("❌ Команда не найдена")
            await event.edit("❌ Команда не найдена или уже выполнена")

    async def handle_confirm_no(self, event):

        sender = await event.get_sender()
        chat_id = event.chat_id
        confirm_key = f"{chat_id}_{sender.id}"

        if confirm_key in self.kernel.pending_confirmations:
            del self.kernel.pending_confirmations[confirm_key]
            await event.answer("❌ Отменено")
            await event.edit("❌ Команда отменена")
        else:
            await event.answer("❌ Нечего отменять")
            await event.edit("❌ Нечего отменять")

    async def handle_catalog_page(self, event):
        try:
            data_str = event.data.decode("utf-8")
        except Exception:
            await event.answer("⚠️ Ошибка данных", alert=True)
            return

        try:
            page = int(data_str.split("_")[1])
        except (IndexError, ValueError):
            await event.answer("⚠️ Неверный формат данных", alert=True)
            return

        await event.answer()

        if not hasattr(self.kernel, "catalog_cache") or not self.kernel.catalog_cache:
            await event.edit("❌ Каталог не загружен")
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

        msg = f"📚 <b>Каталог модулей</b> (Стр. {page}/{total_pages})\n\n"
        for module_name, info in page_modules:
            msg += f"• <b>{module_name}</b>\n"
            msg += f'  {info.get("description", "Описание отсутствует")}\n'
            if "author" in info:
                msg += f'  👤 Автор: @{info["author"]}\n'
            if "commands" in info:
                msg += f'  Команды: {", ".join(info["commands"])}\n'
            msg += "\n"

        msg += f"\nИспользуйте: <code>{self.kernel.custom_prefix}dlm название</code>"

        buttons = []
        nav_buttons = []
        if page > 1:
            nav_buttons.append(Button.inline("⬅️ Назад", f"dlml_{page-1}".encode()))
        if page < total_pages:
            nav_buttons.append(Button.inline("➡️ Вперёд", f"dlml_{page+1}".encode()))

        if nav_buttons:
            buttons.append(nav_buttons)

        await event.edit(msg, buttons=buttons if buttons else None, parse_mode="html")
