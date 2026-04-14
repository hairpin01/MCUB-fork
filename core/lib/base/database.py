# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

# author: @Hairpin00
# version: 1.0.3
# description: SQLite database manager for the userbot.
import aiosqlite
import os
import re
from typing import Any

from utils.security import ensure_locked_after_write


class DatabaseManager:
    """SQLite database manager for the userbot."""

    DEFAULT_DB_FILE = "userbot.db"
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

    def _resolve_db_file(self) -> str:
        """Resolve database path from kernel settings with a safe fallback."""

        def _normalize_path(value) -> str | None:
            if isinstance(value, str):
                value = value.strip()
                return value or None
            if isinstance(value, os.PathLike):
                path = os.fspath(value).strip()
                return path or None
            return None

        kernel_db_file = getattr(self.kernel, "__dict__", {}).get("DB_FILE")
        normalized_kernel_file = _normalize_path(kernel_db_file)
        if normalized_kernel_file:
            return normalized_kernel_file

        config = getattr(self.kernel, "__dict__", {}).get("config")
        if isinstance(config, dict):
            config_db_file = config.get("db_file") or config.get("database_file")
            normalized_config_file = _normalize_path(config_db_file)
            if normalized_config_file:
                return normalized_config_file

        api_id = getattr(self.kernel, "API_ID", None)
        api_hash = getattr(self.kernel, "API_HASH", None)
        if api_id and api_hash:
            from utils.security import get_mcub_dir

            mcub_dir = get_mcub_dir(api_id, api_hash)
            return os.path.join(mcub_dir, self.DEFAULT_DB_FILE)

        return self.DEFAULT_DB_FILE

    def _validate_query(self, query: str) -> bool:
        """Validate SQL query against security policy."""
        query_upper = query.upper().strip()

        for pattern in self.FORBIDDEN_PATTERNS:
            if re.search(pattern, query_upper):
                self.logger.warning(
                    f"db_query: blocked forbidden operation: {query[:50]}..."
                )
                return False

        for op in self.ALLOWED_OPERATIONS:
            if query_upper.startswith(op):
                return True

        self.logger.warning(f"db_query: operation not in whitelist: {query[:50]}...")
        return False

    async def init_db(self):
        """Initialize the database connection."""
        self.logger.debug("[DB] init_db start")
        try:
            db_file = self._resolve_db_file()
            self.logger.debug(f"[DB] init_db connecting to {db_file}")
            self.conn = await aiosqlite.connect(db_file)
            await self._create_tables()
            # Lock the DB file right after creation/open
            ensure_locked_after_write(db_file, self.logger)
            self.logger.info(f"=> Database initialized: {db_file}")
            self.logger.debug("[DB] init_db done")
            return True
        except Exception as e:
            self.logger.error(f"=X Database initialization error: {e}")
            return False

    async def _create_tables(self):
        """Create required tables."""
        await self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS module_data (
                module TEXT,
                key TEXT,
                value TEXT,
                PRIMARY KEY (module, key)
            )
        """
        )
        await self.conn.commit()

    def _validate_identifier(self, value: str) -> bool:
        """Validate identifier (module name or key)."""
        if not value:
            return False
        if len(value) > 64:
            return False
        return bool(re.match(r"^[a-zA-Z0-9_.\-]+$", value))

    async def db_set(self, module: str, key: str, value: Any):
        """Save value for a module key."""
        self.logger.debug(f"[DB] db_set module={module} key={key}")
        if not self.conn:
            raise RuntimeError("Database is not initialized")

        if not self._validate_identifier(module) or not self._validate_identifier(key):
            raise ValueError(
                "Invalid module or key name. Use only alphanumeric and underscore."
            )

        await self.conn.execute(
            "INSERT OR REPLACE INTO module_data VALUES (?, ?, ?)",
            (module, key, str(value)),
        )
        await self.conn.commit()
        self.logger.debug(f"[DB] db_set done")

    async def db_get(self, module: str, key: str) -> str | None:
        """Get value for a module key."""
        self.logger.debug(f"[DB] db_get module={module} key={key}")
        if not self.conn:
            raise RuntimeError("Database is not initialized")

        if not self._validate_identifier(module) or not self._validate_identifier(key):
            raise ValueError(
                "Invalid module or key name. Use only alphanumeric and underscore."
            )

        cursor = await self.conn.execute(
            "SELECT value FROM module_data WHERE module = ? AND key = ?", (module, key)
        )
        row = await cursor.fetchone()
        await cursor.close()
        result = row[0] if row else None
        self.logger.debug(f"[DB] db_get result={'found' if result else 'none'}")
        return result

    async def db_delete(self, module: str, key: str):
        """Delete key from module storage."""
        if not self.conn:
            raise RuntimeError("Database is not initialized")

        if not self._validate_identifier(module) or not self._validate_identifier(key):
            raise ValueError(
                "Invalid module or key name. Use only alphanumeric and underscore."
            )

        await self.conn.execute(
            "DELETE FROM module_data WHERE module = ? AND key = ?", (module, key)
        )
        await self.conn.commit()

    async def db_query(self, query: str, parameters: tuple = ()):
        """Execute custom SQL query (SELECT/PRAGMA/EXPLAIN only)."""
        if not self.conn:
            raise RuntimeError("Database is not initialized")

        if parameters is None:
            parameters = ()

        if not self._validate_query(query):
            raise PermissionError(
                "Query blocked by security policy. Only SELECT, PRAGMA, and EXPLAIN are allowed."
            )

        cursor = await self.conn.execute(query, parameters)
        rows = await cursor.fetchall()
        await cursor.close()
        return rows

    async def db_get_module_keys(self, module: str) -> list[str]:
        """Get all keys for a given module."""
        if not self.conn:
            raise RuntimeError("Database is not initialized")

        if not self._validate_identifier(module):
            raise ValueError("Invalid module name")

        cursor = await self.conn.execute(
            "SELECT key FROM module_data WHERE module = ?", (module,)
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return [row[0] for row in rows]

    async def db_get_config_modules(self) -> list[str]:
        """Get all module names that have configs stored (for module_configs table)."""
        if not self.conn:
            raise RuntimeError("Database is not initialized")

        cursor = await self.conn.execute(
            "SELECT key, value FROM module_data WHERE module = 'module_configs'"
        )
        rows = await cursor.fetchall()
        await cursor.close()

        result = []
        for row in rows:
            key = row[0]
            value = row[1]
            if value and value.strip() not in ("{}", "[]", "null", '""', "''"):
                result.append(key)
        return result
