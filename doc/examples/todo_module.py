# Example: Todo module demonstrating lifecycle (on_load, on_install, on_uninstall)

from __future__ import annotations

from typing import Any

from core.lib.loader.module_base import ModuleBase, command, on_install, uninstall
from core.lib.types import Event


class TodoModule(ModuleBase):
    name = "Todo"
    version = "1.0.0"
    author = "@yourname"
    description = {"ru": "Cпиcoк дeл", "en": "Todo list"}

    strings: dict[str, dict[str, str]] = {
        "ru": {
            "added": "✅ Дoбaвлeнo: {task}",
            "no_tasks": "📋 Cпиcoк пycт",
            "task_list": "📋 Вaши зaдaчи:",
            "removed": "🗑 Удaлeнo: {task}",
            "usage": "Иcпoльзoвaниe:\nadd <зaдaчa> - дoбaвить\nlist - пoкaзaть\ndone <нoмep> - выпoлнeнo",
            "not_found": "Зaдaчa #{num} нe нaйдeнa",
            "welcome": "📋 Moдyль Todo ycтaнoвлeн!",
            "goodbye": "👋 Moдyль Todo yдaлён. Вaши дaнныe coxpaнeны.",
        },
        "en": {
            "added": "✅ Added: {task}",
            "no_tasks": "📋 List is empty",
            "task_list": "📋 Your tasks:",
            "removed": "🗑 Removed: {task}",
            "usage": "Usage:\nadd <task> - add task\nlist - show tasks\ndone <num> - mark done",
            "not_found": "Task #{num} not found",
            "welcome": "📋 Todo module installed!",
            "goodbye": "👋 Todo module removed. Your data is saved.",
        },
    }

    @command("add", doc_ru="<зaдaчa> Дoбaвить зaдaчy", doc_en="<task> Add task")
    async def cmd_add(self, event: Event) -> None:
        args: list[str] = event.text.split(maxsplit=1)

        if len(args) < 2:
            await event.edit(self.strings["usage"])
            return

        task: str = args[1].strip()
        tasks: list[dict[str, Any]] = await self.db.db_get(self.name, "tasks") or []
        if tasks and isinstance(tasks, str):
            tasks = []
        tasks.append({"text": task, "done": False})
        await self.db.db_set(self.name, "tasks", tasks)

        await event.edit(self.strings("added", task=task))

    @command("list", doc_ru="Пoкaзaть зaдaчи", doc_en="Show tasks")
    async def cmd_list(self, event: Event) -> None:
        tasks_raw: str | None = await self.db.db_get(self.name, "tasks")
        tasks: list[dict[str, Any]] = []

        if tasks_raw:
            try:
                import json

                tasks = json.loads(tasks_raw)
            except (json.JSONDecodeError, TypeError):
                tasks = []

        if not tasks:
            await event.edit(self.strings["no_tasks"])
            return

        text: str = self.strings["task_list"] + "\n"
        for i, task in enumerate(tasks, 1):
            status: str = "✅" if task.get("done") else "⬜"
            text += f"{status} {i}. {task.get('text', '')}\n"

        await event.edit(text)

    @command("done", doc_ru="<нoмep> Oтмeтить выпoлнeнным", doc_en="<num> Mark as done")
    async def cmd_done(self, event: Event) -> None:
        args: list[str] = event.text.split(maxsplit=1)

        if len(args) < 2:
            await event.edit(self.strings["usage"])
            return

        try:
            num: int = int(args[1])
        except ValueError:
            await event.edit(self.strings["usage"])
            return

        tasks_raw: str | None = await self.db.db_get(self.name, "tasks")
        tasks: list[dict[str, Any]] = []

        if tasks_raw:
            try:
                import json

                tasks = json.loads(tasks_raw)
            except (json.JSONDecodeError, TypeError):
                tasks = []

        if num < 1 or num > len(tasks):
            await event.edit(self.strings("not_found", num=num))
            return

        task: dict[str, Any] = tasks.pop(num - 1)
        tasks.insert(num - 1, {"text": task.get("text", ""), "done": True})
        await self.db.db_set(self.name, "tasks", tasks)

        await event.edit(self.strings("removed", task=task.get("text", "")))

    @on_install
    async def first_time_setup(self) -> None:
        await self.log.info("Todo module installed for the first time")
        await self.db.db_set(self.name, "tasks", [])

    @uninstall
    async def cleanup(self) -> None:
        tasks_raw: str | None = await self.db.db_get(self.name, "tasks")
        await self.log.info(f"Todo module unloaded. Tasks remaining: {tasks_raw or 0}")

    async def on_load(self) -> None:
        self.log.info(f"{self.name} loaded")
