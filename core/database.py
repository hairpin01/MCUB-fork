# author: @Hairpin00
# version: 1.0.1
# description: Менеджер для работы с SQLite базой данных юзербота.
import aiosqlite
import json

class DatabaseManager:
    """Менеджер для работы с SQLite базой данных юзербота."""

    def __init__(self, kernel):
        self.kernel = kernel
        self.conn = None
        self.logger = kernel.logger

    async def init_db(self):
        """Инициализация базы данных"""
        try:
            self.conn = await aiosqlite.connect("userbot.db")
            await self._create_tables()
            self.logger.info("=> База данных инициализирована")
            return True
        except Exception as e:
            self.logger.error(f"=X Ошибка инициализации БД: {e}")
            return False

    async def _create_tables(self):
        """Создание необходимых таблиц"""
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS module_data (
                module TEXT,
                key TEXT,
                value TEXT,
                PRIMARY KEY (module, key)
            )
        """)
        await self.conn.commit()

    async def db_set(self, module: str, key: str, value: str):
        """Сохранить значение для модуля."""
        if not self.conn:
            raise Exception("База данных не инициализирована")
        await self.conn.execute(
            "INSERT OR REPLACE INTO module_data VALUES (?, ?, ?)",
            (module, key, str(value))
        )
        await self.conn.commit()

    async def db_get(self, module: str, key: str) -> str | None:
        """Получить значение для модуля."""
        if not self.conn:
            raise Exception("База данных не инициализирована")
        cursor = await self.conn.execute(
            "SELECT value FROM module_data WHERE module = ? AND key = ?",
            (module, key)
        )
        row = await cursor.fetchone()
        return row[0] if row else None

    async def db_delete(self, module: str, key: str):
        """Удалить ключ из хранилища модуля."""
        if not self.conn:
            raise Exception("База данных не инициализирована")
        await self.conn.execute(
            "DELETE FROM module_data WHERE module = ? AND key = ?",
            (module, key)
        )
        await self.conn.commit()

    async def db_query(self, query: str, parameters: tuple):
        """Выполнить произвольный SQL‑запрос."""
        if not self.conn:
            raise Exception("База данных не инициализирована")
        cursor = await self.conn.execute(query, parameters)
        rows = await cursor.fetchall()
        return rows
