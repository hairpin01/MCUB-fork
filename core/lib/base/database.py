# author: @Hairpin00
# version: 1.0.1
# description: Менеджер для работы с SQLite базой данных юзербота.
import aiosqlite
import json
import re

class DatabaseManager:
    """Менеджер для работы с SQLite базой данных юзербота."""

    ALLOWED_OPERATIONS = {"SELECT", "PRAGMA", "EXPLAIN"}
    FORBIDDEN_PATTERNS = [
        r"\bDROP\b",
        r"\bDELETE\b",
        r"\bUPDATE\b",
        r"\bINSERT\b",
        r"\bALTER\b",
        r"\bCREATE\b",
        r"\bTRUNCATE\b",
        r"\bATTACH\b",
        r"\bDETACH\b",
    ]

    def __init__(self, kernel):
        self.kernel = kernel
        self.conn = None
        self.logger = kernel.logger

    def _validate_query(self, query: str) -> bool:
        """Валидация SQL запроса на безопасность."""
        query_upper = query.upper().strip()
        
        for pattern in self.FORBIDDEN_PATTERNS:
            if re.search(pattern, query_upper):
                self.logger.warning(f"db_query: blocked forbidden operation: {query[:50]}...")
                return False
        
        for op in self.ALLOWED_OPERATIONS:
            if query_upper.startswith(op):
                return True
        
        self.logger.warning(f"db_query: operation not in whitelist: {query[:50]}...")
        return False

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

    def _validate_identifier(self, value: str) -> bool:
        """Валидация идентификатора (имя модуля, ключ)."""
        if not value:
            return False
        if len(value) > 64:
            return False
        return bool(re.match(r'^[a-zA-Z0-9_]+$', value))

    async def db_set(self, module: str, key: str, value: str):
        """Сохранить значение для модуля."""
        if not self.conn:
            raise Exception("База данных не инициализирована")
        
        if not self._validate_identifier(module) or not self._validate_identifier(key):
            raise ValueError("Invalid module or key name. Use only alphanumeric and underscore.")
        
        await self.conn.execute(
            "INSERT OR REPLACE INTO module_data VALUES (?, ?, ?)",
            (module, key, str(value))
        )
        await self.conn.commit()

    async def db_get(self, module: str, key: str) -> str | None:
        """Получить значение для модуля."""
        if not self.conn:
            raise Exception("База данных не инициализирована")
        
        if not self._validate_identifier(module) or not self._validate_identifier(key):
            raise ValueError("Invalid module or key name. Use only alphanumeric and underscore.")
        
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
        
        if not self._validate_identifier(module) or not self._validate_identifier(key):
            raise ValueError("Invalid module or key name. Use only alphanumeric and underscore.")
        
        await self.conn.execute(
            "DELETE FROM module_data WHERE module = ? AND key = ?",
            (module, key)
        )
        await self.conn.commit()

    async def db_query(self, query: str, parameters: tuple):
        """Выполнить произвольный SQL‑запрос (только SELECT/PRAGMA/EXPLAIN)."""
        if not self.conn:
            raise Exception("База данных не инициализирована")
        
        if not self._validate_query(query):
            raise PermissionError("Query blocked by security policy. Only SELECT, PRAGMA, and EXPLAIN are allowed.")
        
        cursor = await self.conn.execute(query, parameters)
        rows = await cursor.fetchall()
        return rows
