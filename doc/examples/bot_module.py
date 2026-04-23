# Example: Bot commands module (via Telegram bot, not userbot)

from __future__ import annotations

from telethon import events

from core.lib.loader.module_base import ModuleBase, bot_command, command


class BotModule(ModuleBase):
    name = "BotCommands"
    version = "1.0.0"
    author = "@yourname"
    description = {"ru": "Команды бота", "en": "Bot commands"}

    strings: dict[str, dict[str, str]] = {
        "ru": {
            "start_text": "👋 Привет! Я бот MCUB.\n\nДоступные команды:\n/start - Начать\n/help - Помощь\n/stats - Статистика",
            "help_text": "📖 Помощь по боту\n\nВсе команды доступны через /menu",
            "stats_title": "📊 Статистика",
            "users_count": "Пользователей: {count}",
            "uptime": "Время работы: {time}",
        },
        "en": {
            "start_text": "👋 Hello! I'm MCUB bot.\n\nAvailable commands:\n/start - Start\n/help - Help\n/stats - Stats",
            "help_text": "📖 Bot help\n\nAll commands available via /menu",
            "stats_title": "📊 Statistics",
            "users_count": "Users: {count}",
            "uptime": "Uptime: {time}",
        },
    }

    @bot_command("start", doc_ru="Старт", doc_en="Start")
    async def bot_start(self, event: events.NewMessage.Event) -> None:
        await event.reply(self.strings["start_text"])

    @bot_command("help", doc_ru="Помощь", doc_en="Help")
    async def bot_help(self, event: events.NewMessage.Event) -> None:
        await event.reply(self.strings["help_text"])

    @bot_command("stats", doc_ru="Статистика", doc_en="Statistics")
    async def bot_stats(self, event: events.NewMessage.Event) -> None:
        user_count_raw: str | None = await self.db.db_get(self.name, "user_count")
        user_count: int = int(user_count_raw) if user_count_raw else 0

        await event.reply(
            f"{self.strings['stats_title']}\n\n"
            f"{self.strings('users_count', count=user_count)}\n"
            f"{self.strings('uptime', time='N/A')}"
        )

    @command("menu", doc_ru="Меню", doc_en="Menu")
    async def cmd_menu(self, event: events.NewMessage.Event) -> None:
        text: str = self.strings["start_text"]

        btn_help = self.Button.inline("📖 Help", self.bot_help)
        btn_stats = self.Button.inline("📊 Stats", self.bot_stats)

        await self.kernel.inline_form(
            event.chat_id,
            text,
            buttons=[[btn_help, btn_stats]],
        )

    async def on_load(self) -> None:
        self.log.info(f"{self.name} loaded")
