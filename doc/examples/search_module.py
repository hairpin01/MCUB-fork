# Example: Inline search module with callbacks

from __future__ import annotations

from typing import Any

from telethon import events

from core.lib.loader.module_base import ModuleBase, callback, command, inline


class SearchModule(ModuleBase):
    name = "Search"
    version = "1.0.0"
    author = "@yourname"
    description = {"ru": "Поиск по базе знаний", "en": "Knowledge base search"}
    strings = {
        "ru": {
            "search_placeholder": "Введите запрос для поиска...",
            "no_results": "Ничего не найдено по запросу: {query}",
            "results_count": "Найдено {count} результатов",
            "loading": "Загрузка...",
        },
        "en": {
            "search_placeholder": "Enter search query...",
            "no_results": "No results for: {query}",
            "results_count": "Found {count} results",
            "loading": "Loading...",
        },
    }

    @inline("search")
    async def inline_search(self, event: events.InlineQuery.Event) -> None:
        query: str = event.args.strip()

        if not query:
            article = event.builder.article(
                title=self.strings["search_placeholder"],
                text=self.strings["search_placeholder"],
            )
            await event.answer([article])
            return

        results: list[dict[str, Any]] = await self._perform_search(query)

        if not results:
            await event.answer(
                [
                    event.builder.article(
                        title=self.strings("no_results", query=query),
                        text=self.strings("no_results", query=query),
                    )
                ],
            )
            return

        articles: list[Any] = []
        for item in results[:10]:
            btn = self.Button.inline(
                f"View: {item['title']}",
                self.show_item,
                data={"id": item["id"]},
            )
            articles.append(
                event.builder.article(
                    title=item["title"],
                    text=f"{item['title']}\n\n{item['description'][:200]}...",
                    buttons=[[btn]],
                )
            )

        await event.answer(articles)

    @callback()
    async def show_item(
        self, event: events.CallbackQuery.Event, data: dict[str, Any] | None = None
    ) -> None:
        item_id: str | None = data.get("id") if data else None
        item: dict[str, Any] | None = await self._get_item(item_id)

        if not item:
            await event.answer("Item not found", alert=True)
            return

        await event.answer(
            f"📄 {item['title']}\n\n{item['content']}",
            alert=True,
        )

    @command("search", doc_ru="<запрос> Поиск", doc_en="<query> Search")
    async def cmd_search(self, event: events.NewMessage.Event) -> None:
        args: list[str] = event.text.split(maxsplit=1)

        if len(args) < 2:
            await event.edit(self.strings["search_placeholder"])
            return

        query: str = args[1].strip()
        await event.edit(self.strings["loading"])

        results: list[dict[str, Any]] = await self._perform_search(query)

        if not results:
            await event.edit(self.strings("no_results", query=query))
            return

        text: str = self.strings("results_count", count=len(results)) + "\n\n"
        for item in results[:5]:
            text += f"📌 {item['title']}\n"

        await event.edit(text)

    async def _perform_search(self, query: str) -> list[dict[str, Any]]:
        return []

    async def _get_item(self, item_id: str | None) -> dict[str, Any] | None:
        return None
