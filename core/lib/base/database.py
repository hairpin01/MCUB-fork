# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

from __future__ import annotations

import os
import re
from typing import Any

# author: @Hairpin00
# version: 1.0.3
# description: SQLite database manager for the userbot.
try:
    import aiosqlite
except ImportError:
    aiosqlite = None
    print(
        "\033[93m⚠  Degraded: aiosqlite not installed - DB read/write will fail\033[0m"
    )

try:
    from utils.security import ensure_locked_after_write
except ImportError:

    def ensure_locked_after_write(*a, **kw):
        pass

    print(
        "\033[93m⚠  Degraded: utils.security.ensure_locked_after_write not available\033[0m"
    )


class DatabaseManager:
    """SQLite database manager for the userbot."""

    DEFAULT_DB_FILE = "userbot.db"
    ALLOWED_OPERATIONS = {"SELECT", "EXPLAIN"}
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
    DANGEROUS_PRAGMAS = {
        "writable_schema",
        "journal_mode",
        "synchronous",
        "locking_mode",
        "recursive_triggers",
        "reverse_unordered_selects",
        "cell_size_check",
    }
    _VALID_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_.\-:]+$")

    SENSITIVE_KEY_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r"token", re.IGNORECASE),
        re.compile(r"password|passwd", re.IGNORECASE),
        re.compile(r"secret", re.IGNORECASE),
        re.compile(r"session", re.IGNORECASE),
        re.compile(r"api[_\s]?(?:id|key|hash|secret)", re.IGNORECASE),
        re.compile(r"auth", re.IGNORECASE),
        re.compile(r"private[_\s]key", re.IGNORECASE),
        re.compile(r"access[_\s]token", re.IGNORECASE),
        re.compile(r"refresh[_\s]token", re.IGNORECASE),
    ]

    @staticmethod
    def mask_key(key: str) -> str:
        """Mask a key if it looks sensitive - keeps first + last char.

        Used in log messages to avoid leaking sensitive key names.
        """
        for pattern in DatabaseManager.SENSITIVE_KEY_PATTERNS:
            if pattern.search(key):
                if len(key) <= 4:
                    return "***"
                return key[0] + "***" + key[-1]
        return key

    def __init__(self, kernel):
        self.kernel = kernel
        self.conn = None
        self.logger = kernel.logger
        # Write-through cache for db_get: { "module:key": value }
        # Cleared on any db_set/db_delete for the same module:key.
        self._get_cache: dict[str, str | None] = {}

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

    def _strip_comments(self, query: str) -> str:
        """Remove SQL comments from query before validation."""
        query = re.sub(r"/\*.*?\*/", " ", query, flags=re.DOTALL)
        query = re.sub(r"--[^\n]*", "", query, flags=re.MULTILINE)
        return query

    def _validate_query(self, query: str) -> bool:
        """Validate SQL query against security policy."""
        cleaned = self._strip_comments(query).strip()
        # Remove string contents to check structure
        no_strings = re.sub(r"'[^']*'", "''", cleaned)
        no_strings = re.sub(r'"[^"]*"', '""', no_strings)

        # Multi-statement detection: allow only trailing semicolons
        stripped = no_strings.rstrip(";").strip()
        if ";" in stripped:
            self.logger.warning(
                f"db_query: multiple statements blocked: {query[:80]}..."
            )
            return False

        query_upper = stripped.upper()

        # Block access to sqlite schema tables
        if re.search(r"\bSQLITE_(MASTER|TEMP_MASTER)\b", query_upper):
            self.logger.warning(
                f"db_query: sqlite_master access blocked: {query[:80]}..."
            )
            return False

        # Block dangerous operations
        for pattern in self.FORBIDDEN_PATTERNS:
            if re.search(pattern, query_upper):
                self.logger.warning(
                    f"db_query: forbidden operation blocked: {query[:80]}..."
                )
                return False

        # Block dangerous PRAGMAs (assignments or known dangerous ones)
        if re.match(r"\s*PRAGMA\b", query_upper):
            m_pragma = re.match(r"\s*PRAGMA\b\s*(.*)", query_upper, re.DOTALL)
            pragma_rest = m_pragma.group(1) if m_pragma else ""
            # Block assignments like PRAGMA journal_mode=WAL
            if "=" in pragma_rest:
                self.logger.warning(
                    f"db_query: PRAGMA assignment blocked: {query[:80]}..."
                )
                return False
            # Block known dangerous pragmas (schema modification, etc.)
            for dangerous in self.DANGEROUS_PRAGMAS:
                if re.search(
                    rf"\b{re.escape(dangerous)}\b", pragma_rest, re.IGNORECASE
                ):
                    self.logger.warning(
                        f"db_query: dangerous PRAGMA blocked: {query[:80]}..."
                    )
                    return False
            # Safe read-only PRAGMA (e.g. table_info, index_list) - allow
            return True

        # Only allow read-only operations
        first_word = query_upper.split()[0] if query_upper.split() else ""
        if first_word in self.ALLOWED_OPERATIONS:
            return True

        self.logger.warning(f"db_query: operation not in whitelist: {query[:80]}...")
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
        return bool(self._VALID_ID_PATTERN.match(value))

    @staticmethod
    def sanitize_key(value: str) -> str:
        """Replace characters not allowed in identifiers with underscores."""
        return re.sub(r"[^a-zA-Z0-9_.\-:]+", "_", value)

    async def db_set(self, module: str, key: str, value: Any):
        """Save value for a module key (write-through cache invalidate)."""
        self.logger.debug(f"[DB] db_set module={module} key={self.mask_key(key)}")
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
        self._get_cache.pop(f"{module}:{key}", None)
        self.logger.debug("[DB] db_set done")

    async def db_get(self, module: str, key: str) -> str | None:
        """Get value for a module key (cached)."""
        self.logger.debug(f"[DB] db_get module={module} key={self.mask_key(key)}")
        if not self.conn:
            raise RuntimeError("Database is not initialized")

        if not self._validate_identifier(module) or not self._validate_identifier(key):
            raise ValueError(
                "Invalid module or key name. Use only alphanumeric and underscore."
            )

        cache_key = f"{module}:{key}"
        cached = self._get_cache.get(cache_key, ...)
        if cached is not ...:
            self.logger.debug(f"[DB] db_get cache-hit key={self.mask_key(cache_key)}")
            return cached

        cursor = await self.conn.execute(
            "SELECT value FROM module_data WHERE module = ? AND key = ?", (module, key)
        )
        row = await cursor.fetchone()
        await cursor.close()
        result = row[0] if row else None
        self._get_cache[cache_key] = result
        self.logger.debug(f"[DB] db_get result={'found' if result else 'none'}")
        return result

    async def db_delete(self, module: str, key: str):
        """Delete key from module storage (write-through cache invalidate)."""
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
        self._get_cache.pop(f"{module}:{key}", None)

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
