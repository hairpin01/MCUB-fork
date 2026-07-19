# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

from __future__ import annotations

import asyncio
import contextlib
import inspect
import json
import os
import traceback
from html import escape
from typing import Any

from telethon import Button, events
from telethon.tl.types import (
    DocumentAttributeImageSize,
    InputMediaWebPage,
    InputWebDocument,
)

import utils
from core.lib.loader.module_base import ModuleBase, command, inline
from core.lib.loader.module_config import (
    Boolean,
    ConfigValue,
    Integer,
    ModuleConfig,
    String,
)
from core.lib.types import InlineMessage
from utils.strings import Strings

CUSTOM_EMOJI = {
    "crystal": '<tg-emoji emoji-id="5332762073388578651">🎮</tg-emoji>',
    "dna": '<tg-emoji emoji-id="5332762073388578651">❔</tg-emoji>',
    "alembic": '<tg-emoji emoji-id="5411243692960810848">🤔</tg-emoji>',
    "snowflake": '<tg-emoji emoji-id="5431895003821513760">❄️</tg-emoji>',
    "blocked": '<tg-emoji emoji-id="5332439413970469607">🚫</tg-emoji>',
    "pancake": '<tg-emoji emoji-id="5303396278179210513">👾</tg-emoji>',
    "confused": '<tg-emoji emoji-id="5408830797513784663">❓</tg-emoji>',
    "map": '<tg-emoji emoji-id="5332373172689860602">🚫</tg-emoji>',
    "tot": '<tg-emoji emoji-id="5404696015318054899">▪️</tg-emoji>',
    "eye_off": '<tg-emoji emoji-id="5228686859663585439">👁</tg-emoji>',
    "bot": '<tg-emoji emoji-id="5372981976804366741">🤖</tg-emoji>',
}

ZERO_WIDTH_CHAR = "\u2060"

_METADATA_CACHE: dict[str, tuple[float, dict]] = {}
_METADATA_LOCKS: dict[int, asyncio.Lock] = {}


def _get_metadata_lock() -> asyncio.Lock:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.Lock()
    loop_id = id(loop)
    lock = _METADATA_LOCKS.get(loop_id)
    if lock is None:
        lock = asyncio.Lock()
        _METADATA_LOCKS[loop_id] = lock
    return lock


class ManModule(ModuleBase):
    name = "man"
    version = "1.1.1"
    author = "@hairpin00"
    description = {
        "ru": "Список модулей, и их описание",
        "en": "List of modules and their descriptions",
    }

    strings: dict | Strings = {"name": "man"}

    config = ModuleConfig(
        ConfigValue(
            "man_quote_media",
            True,
            description="Send media in quotes",
            validator=Boolean(default=True),
        ),
        ConfigValue(
            "man_banner_url",
            "",
            description="Banner image URL for inline preview",
            validator=String(default=""),
        ),
        ConfigValue(
            "man_invert_media",
            False,
            description="Invert media colors",
            validator=Boolean(default=False),
        ),
        ConfigValue(
            "man_emoji_system_list",
            "▫️",
            description="emoji for list system module",
            validator=String(default="▫️"),
        ),
        ConfigValue(
            "man_emoji_user_list",
            "▪️",
            description="emoji for list user module",
            validator=String(default="▪️"),
        ),
        ConfigValue(
            "man_emoji",
            CUSTOM_EMOJI["crystal"],
            description="emoji main inline panel",
            validator=String(default=str(CUSTOM_EMOJI["crystal"])),
        ),
        ConfigValue(
            "man_emoji_no_command",
            "❔",
            description="emoji for No command module",
            validator=String(default="❔"),
        ),
        ConfigValue(
            "man_modules_per_page",
            10,
            description="module count per inline man page",
            validator=Integer(default=10, min=1, max=50),
        ),
        ConfigValue(
            "man_emoji_author",
            CUSTOM_EMOJI["alembic"],
            description="emoji for about module",
            validator=String(default=CUSTOM_EMOJI["alembic"]),
        ),
        ConfigValue(
            "man_emoji_bot",
            CUSTOM_EMOJI["bot"],
            description="emoji for inline commands",
            validator=String(default=str(CUSTOM_EMOJI["bot"])),
        ),
        ConfigValue(
            "man_emoji_error",
            CUSTOM_EMOJI["blocked"],
            description="emoji for errors and not found messages",
            validator=String(default=str(CUSTOM_EMOJI["blocked"])),
        ),
    )

    async def on_load(self) -> None:
        config_dict = await self.kernel.get_module_config(
            self.name,
            {
                "man_quote_media": True,
                "man_banner_url": "",
                "man_invert_media": False,
                "man_emoji_user_list": "▪️",
                "man_emoji_system_list": "▫️",
                "man_emoji": CUSTOM_EMOJI["crystal"],
                "man_emoji_no_command": "❔",
                "man_modules_per_page": 60,
                "man_emoji_author": CUSTOM_EMOJI["alembic"],
                "man_emoji_bot": CUSTOM_EMOJI["bot"],
                "man_emoji_error": CUSTOM_EMOJI["blocked"],
            },
        )
        self.config.from_dict(config_dict)
        config_dict_clean = {
            k: v for k, v in self.config.to_dict().items() if v is not None
        }
        if config_dict_clean:
            await self.kernel.save_module_config(self.name, config_dict_clean)
        self.kernel.store_module_config_schema(self.name, self.config)

    @staticmethod
    def _make_thumb(url: str) -> InputWebDocument:
        return InputWebDocument(
            url=url,
            size=0,
            mime_type="image/jpeg",
            attributes=[DocumentAttributeImageSize(w=0, h=0)],
        )

    def _format_inline_cmds(self, inline_commands: list) -> str:
        emoji = self.config.get("man_emoji_bot") or CUSTOM_EMOJI["bot"]
        text = ", ".join(
            f"{emoji} <code>{cmd}</code>" for cmd, _ in inline_commands[:3]
        )
        if len(inline_commands) > 3:
            text += f" (+{len(inline_commands) - 3})"
        return text

    def _add_inline_banner_preview(self, message_html: str) -> str:
        cfg = self.config
        banner_url = cfg.get("man_banner_url") if cfg else ""
        quote_media = cfg.get("man_quote_media", False) if cfg else False
        if not (
            quote_media
            and isinstance(banner_url, str)
            and banner_url.startswith(("http://", "https://"))
        ):
            return message_html
        return f'<a href="{escape(banner_url, quote=True)}">{ZERO_WIDTH_CHAR}</a>{message_html}'

    async def _get_hidden_modules(self) -> list[str]:
        data = await self.kernel.db_get("man", "hidden_modules")
        if not data:
            return []
        try:
            if isinstance(data, str):
                return json.loads(data)
            return json.loads(str(data))
        except Exception:
            return []

    async def _save_hidden_modules(self, hidden: list[str]) -> None:
        await self.kernel.db_set("man", "hidden_modules", json.dumps(hidden))

    def _resolve_module_path(self, name: str, typ: str) -> str:
        if typ == "system":
            return f"{self.kernel.MODULES_DIR}/{name}.py"
        resolved = self.kernel._loader.get_module_path(name)
        if resolved:
            return resolved
        package_dir = f"{self.kernel.MODULES_LOADED_DIR}/{name}"
        if os.path.isdir(package_dir):
            init_file = os.path.join(package_dir, "__init__.py")
            if os.path.exists(init_file):
                return init_file
        return f"{self.kernel.MODULES_LOADED_DIR}/{name}.py"

    async def _load_module_metadata(self, name: str, typ: str) -> dict:
        def _fallback_metadata() -> dict:
            return {
                "commands": {},
                "description": s["no_description"],
                "description_i18n": {},
                "version": "?.?.?",
                "author": s["unknown"],
                "banner_url": None,
            }

        def _merge_runtime_metadata(metadata: dict) -> dict:
            system_modules = getattr(self.kernel, "system_modules", {}) or {}
            loaded_modules = getattr(self.kernel, "loaded_modules", {}) or {}
            if typ == "library":
                module_obj = self._find_hikka_library(name)
            else:
                module_obj = (
                    system_modules.get(name)
                    if typ == "system"
                    else loaded_modules.get(name)
                )
            class_instance = getattr(module_obj, "_class_instance", None)
            target = class_instance or module_obj
            if target is None:
                return metadata

            if metadata.get("version") in (None, "", "?.?.?"):
                runtime_version = getattr(target, "version", None)
                if isinstance(runtime_version, str) and runtime_version.strip():
                    metadata["version"] = runtime_version.strip()
                elif isinstance(runtime_version, tuple):
                    metadata["version"] = ".".join(map(str, runtime_version))

            author = metadata.get("author")
            if (
                not isinstance(author, str)
                or not author.strip()
                or author == s["unknown"]
            ):
                runtime_author = getattr(target, "author", None)
                if isinstance(runtime_author, str) and runtime_author.strip():
                    metadata["author"] = runtime_author.strip()

            desc_i18n = metadata.get("description_i18n")
            if not isinstance(desc_i18n, dict) or not desc_i18n:
                runtime_desc = getattr(target, "description", None)
                if isinstance(runtime_desc, dict):
                    metadata["description_i18n"] = runtime_desc
                    metadata["description"] = self.kernel._loader.pick_localized_text(
                        runtime_desc,
                        self.kernel.config.get("language", "ru"),
                        s["no_description"],
                    )
                elif isinstance(runtime_desc, str) and runtime_desc.strip():
                    metadata["description"] = runtime_desc.strip()

            if not metadata.get("banner_url"):
                for attr in ("banner_url", "banner", "image", "photo"):
                    runtime_banner = getattr(target, attr, None)
                    if isinstance(runtime_banner, str) and runtime_banner.strip():
                        metadata["banner_url"] = runtime_banner.strip()
                        break

            return metadata

        file_path = self._resolve_module_path(name, typ)
        s = self.strings
        if typ == "library":
            return _merge_runtime_metadata(_fallback_metadata())
        try:
            mtime = os.path.getmtime(file_path)
        except OSError:
            return _merge_runtime_metadata(_fallback_metadata())

        lock = _get_metadata_lock()
        async with lock:
            cached = _METADATA_CACHE.get(file_path)
            if cached and cached[0] == mtime:
                return cached[1]

        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                code = f.read()
            metadata = await self.kernel.get_module_metadata(code)
        except Exception:
            metadata = _fallback_metadata()

        metadata = _merge_runtime_metadata(metadata)

        async with lock:
            _METADATA_CACHE[file_path] = (mtime, metadata)

        return metadata

    def _get_module_commands(self, module_name: str) -> tuple[dict, dict, dict]:
        if self._find_hikka_library(module_name) is not None:
            return {}, {}, {}
        lang = self.kernel.config.get("language", "ru")
        return self.kernel._loader.get_module_commands(module_name, lang)

    def _iter_hikka_libraries(self) -> list[Any]:
        libraries = getattr(self.kernel, "_hikka_compat_libraries", []) or []
        return list(libraries) if isinstance(libraries, (list, tuple, set)) else []

    def _hikka_library_names(self, library: Any) -> set[str]:
        class_name = library.__class__.__name__
        names = {
            str(getattr(library, "name", "") or "").lower(),
            class_name.lower(),
        }
        if class_name.endswith("Lib"):
            names.add(class_name[:-3].lower())
        return {name for name in names if name}

    def _find_hikka_library(self, name: str, module: Any | None = None) -> Any | None:
        wanted = str(name).lower()
        for library in self._iter_hikka_libraries():
            if module is library or wanted in self._hikka_library_names(library):
                return library
        return None

    def _type_module_strings(self):
        return self.strings("type_module")

    def _detect_native_module_style(self, name: str, module: Any, target: Any) -> str:
        type_strings = self._type_module_strings()
        if target is not module or isinstance(target, ModuleBase):
            return type_strings("module_style_class")

        loader = getattr(self.kernel, "_loader", None)
        module_name = getattr(module, "__name__", name)
        cache = getattr(loader, "_module_type_cache", {}) or {}
        cached_type = cache.get(module_name) or cache.get(name)
        if cached_type in {"class", "new", "old", "method"}:
            style_key = {
                "class": "module_style_class",
                "new": "module_style_kernel",
                "old": "module_style_client_old",
                "method": "module_style_kernel",
            }[cached_type]
            return type_strings(style_key)

        register = getattr(module, "register", None)
        if callable(register):
            iter_methods = getattr(loader, "_iter_register_methods", None)
            with contextlib.suppress(Exception):
                if callable(iter_methods) and iter_methods(register):
                    return type_strings("module_style_kernel")
            with contextlib.suppress(TypeError, ValueError):
                params = list(inspect.signature(register).parameters.values())
                if params:
                    style_key = (
                        "module_style_kernel"
                        if params[0].name == "kernel"
                        else "module_style_client_old"
                    )
                    return type_strings(style_key)

        return type_strings("module_style_kernel")

    def _build_module_type_text(
        self,
        name: str,
        typ: str,
        module: Any,
        *,
        hikka_compat: bool = False,
        hikka_library: bool = False,
    ) -> str:
        type_strings = self._type_module_strings()
        if hikka_library or typ == "library" or self._find_hikka_library(name, module):
            return type_strings("module_type_hikka_library")

        target = getattr(module, "_class_instance", None) or module
        if hikka_compat or getattr(target, "_hikka_compat", False):
            return type_strings("module_type_hikka")

        style = self._detect_native_module_style(name, module, target)
        return type_strings("module_type_native", style=style)

    @staticmethod
    def _count_module_config_keys(config: Any) -> int:
        if config is None:
            return 0
        for attr in ("_values", "_config"):
            values = getattr(config, attr, None)
            if isinstance(values, dict):
                return len(values)
        schema = getattr(config, "schema", None)
        if isinstance(schema, list):
            return len(schema)
        if isinstance(config, dict):
            return len([key for key in config if key != "__mcub_config__"])
        keys = getattr(config, "keys", None)
        if callable(keys):
            with contextlib.suppress(Exception):
                return len([key for key in keys() if key != "__mcub_config__"])
        return 0

    def _module_config_key_count(self, name: str, module: Any | None = None) -> int:
        live_configs = getattr(self.kernel, "_live_module_configs", {}) or {}
        candidates = [live_configs.get(name)]
        target = getattr(module, "_class_instance", None) or module
        if target is not None:
            target_name = getattr(target, "name", None)
            class_name = target.__class__.__name__
            candidates.extend(
                [
                    getattr(target, "config", None),
                    live_configs.get(target_name) if target_name else None,
                    live_configs.get(class_name),
                ]
            )
        for config in candidates:
            count = self._count_module_config_keys(config)
            if count:
                return count
        return 0

    def _build_module_config_text(self, name: str, module: Any | None = None) -> str:
        count = self._module_config_key_count(name, module)
        if not count:
            return ""
        return self._type_module_strings()("module_config_info", count=count)

    def _gather_all_modules(
        self, show_hidden: bool, hidden: list[str]
    ) -> dict[str, tuple[str, object]]:
        all_modules: dict[str, tuple[str, object]] = {}
        for name, module in self.kernel.system_modules.items():
            all_modules[name] = ("system", module)
        for name, module in self.kernel.loaded_modules.items():
            all_modules[name] = ("user", module)
        for library in self._iter_hikka_libraries():
            library_name = getattr(library, "name", None) or library.__class__.__name__
            all_modules[str(library_name)] = ("library", library)
        if not show_hidden:
            all_modules = {k: v for k, v in all_modules.items() if k not in hidden}
        return all_modules

    async def _generate_detailed_page(
        self, search_term: str, show_hidden: bool = False
    ) -> tuple[str, str | None]:
        search_term_clean = search_term.lower()
        exact_match = None
        similar_modules = []
        s = self.strings

        hidden = await self._get_hidden_modules()
        all_modules = self._gather_all_modules(show_hidden, hidden)

        for name, (typ, module) in all_modules.items():
            if name.lower() == search_term_clean:
                exact_match = (name, typ, module)
                break

        if exact_match:
            return await self._build_module_detail(exact_match)

        seen = set()
        for name, (typ, module) in all_modules.items():
            if search_term_clean in name.lower():
                if name not in seen:
                    similar_modules.append((name, typ, module))
                    seen.add(name)
            else:
                commands, _, _ = self._get_module_commands(name)
                for cmd in commands:
                    if search_term_clean in cmd.lower():
                        if name not in seen:
                            similar_modules.append((name, typ, module))
                            seen.add(name)
                        break

        if len(similar_modules) == 1:
            return await self._build_module_detail(similar_modules[0])

        main_emoji = self.config.get("man_emoji") or CUSTOM_EMOJI["crystal"]
        error_emoji = self.config.get("man_emoji_error") or CUSTOM_EMOJI["blocked"]
        if similar_modules:
            msg = f"{main_emoji} <b>{s['found_modules']}:</b>\n<blockquote expandable>"
            for name, typ, module in similar_modules[:5]:
                commands, _, _ = self._get_module_commands(name)
                hidden_mark = f" {CUSTOM_EMOJI['eye_off']}" if name in hidden else ""
                if commands:
                    cmd_text = ", ".join(
                        f"<code>{self.kernel.custom_prefix}{cmd}</code>"
                        for cmd in commands[:2]
                    )
                    msg += f"<b>{name}</b>{hidden_mark}: {cmd_text}\n"
            msg += "</blockquote>"
            if len(similar_modules) > 5:
                msg += f"... {s['and_more'].format(count=len(similar_modules) - 5)} {CUSTOM_EMOJI['tot']}\n"
            msg += f"\n<blockquote><i>{s['no_exact_match']}</i> {CUSTOM_EMOJI['map']}</blockquote>"
        else:
            msg = f"<blockquote expandable>{error_emoji} {s['module_not_found']}</blockquote>"
        return msg, None

    async def _build_module_detail(
        self, match_tuple: tuple[str, str, Any]
    ) -> tuple[str, str | None]:
        name, typ, _module = match_tuple
        s = self.strings

        is_system = typ == "system"

        class_instance = getattr(_module, "_class_instance", None)
        if class_instance is not None:
            display_name = getattr(type(class_instance), "name", name)
        else:
            display_name = name

        commands, aliases_info, descriptions = self._get_module_commands(name)
        metadata = await self._load_module_metadata(name, typ)

        lang = self.get_lang()
        i18n = metadata.get("description_i18n")
        fallback = metadata.get("description", s["no_description"])
        description = self.kernel._loader.pick_localized_text(i18n, lang, fallback)

        module_emoji = self.config.get("man_emoji") or CUSTOM_EMOJI["dna"]
        author_emoji = self.config.get("man_emoji_author") or CUSTOM_EMOJI["alembic"]
        msg = f"<blockquote>{module_emoji} <b>{display_name}</b> <i>(v{metadata.get('version', '1.0.0')})</i></blockquote>\n"
        msg += (
            f"<blockquote expandable>{author_emoji} <i>{description}</i></blockquote>\n"
        )
        module_type_text = self._build_module_type_text(name, typ, _module)
        if module_type_text:
            msg += f"<blockquote>{CUSTOM_EMOJI['tot']} <i>{escape(module_type_text)}</i></blockquote>\n"
        module_config_text = self._build_module_config_text(name, _module)
        if module_config_text:
            msg += f"<blockquote>{CUSTOM_EMOJI['tot']} <i>{escape(module_config_text)}</i></blockquote>\n"
        msg += "\n"
        msg += "<blockquote expandable>"
        if commands:
            # Use list + join for O(n) instead of O(n²) string concatenation
            cmd_lines = []
            for cmd in commands:
                cmd_desc = (
                    descriptions.get(cmd)
                    or metadata.get("commands", {}).get(cmd)
                    or f"{CUSTOM_EMOJI['confused']} {s['no_description']}"
                )
                line = f"{self.config.get('man_emoji_system_list', CUSTOM_EMOJI['tot']) if is_system else self.config.get('man_emoji_user_list', CUSTOM_EMOJI['tot'])} <code>{self.kernel.custom_prefix}{cmd}</code> - <b>{cmd_desc}</b>"

                if cmd in aliases_info:
                    aliases = aliases_info[cmd]
                    if isinstance(aliases, str):
                        aliases = [aliases]
                    if aliases:
                        alias_text = ", ".join(
                            f"<code>{self.kernel.custom_prefix}{a}</code>"
                            for a in aliases
                        )
                        line += f" | {s['aliases']}: {alias_text}"
                cmd_lines.append(line)
            msg += "\n".join(cmd_lines) + "\n"
        else:
            no_command_emoji = (
                self.config.get("man_emoji_no_command") or CUSTOM_EMOJI["snowflake"]
            )
            msg += f"{no_command_emoji} {s['no_commands']}\n"
        msg += "</blockquote>"

        inline_commands = self.kernel.get_module_inline_commands(name)
        if inline_commands:
            inline_emoji = self.config.get("man_emoji_bot") or CUSTOM_EMOJI["bot"]
            # Use list + join for O(n) instead of O(n²) string concatenation
            inline_lines = []
            for cmd, desc in inline_commands:
                if desc:
                    inline_lines.append(
                        f"{inline_emoji} <code>@{self.kernel.config.get('inline_bot_username', 'bot')} {cmd}</code> - <b>{desc}</b>"
                    )
                else:
                    inline_lines.append(
                        f"{inline_emoji} <code>@{self.kernel.config.get('inline_bot_username', 'bot')} {cmd}</code>"
                    )
            msg += (
                "<blockquote expandable>" + "\n".join(inline_lines) + "\n</blockquote>"
            )

        author_emoji = self.config.get("man_emoji_author") or CUSTOM_EMOJI["alembic"]
        msg += f"<blockquote>{author_emoji} <b>{s['author']}:</b> <i>{metadata.get('author', s['unknown'])}</i></blockquote>"
        placeholder_docs = utils.config_placeholders(name)
        if placeholder_docs:
            msg += (
                f"\n<blockquote expandable>{CUSTOM_EMOJI['map']} <b>{s['placeholders_title']}:</b>"
                f"\n<i>{escape(placeholder_docs)}</i></blockquote>"
            )
        if is_system:
            msg += (
                "\n<blockquote>"
                + self.strings(
                    "system_module_note",
                    blocked=self.config.get("man_emoji_error")
                    or CUSTOM_EMOJI["blocked"],
                )
                + "</blockquote>"
            )
        return msg, metadata.get("banner_url")

    async def _man_close_cb(self, cb_event: InlineMessage) -> None:
        try:
            peer = cb_event.input_chat
            if peer:
                result = await self.kernel.client.delete_messages(
                    peer, cb_event.message_id
                )
                affected = sum(r.pts_count for r in result)
                if affected == 0:
                    self.kernel.logger.error(
                        'delete man message "%s", "%s" failed!',
                        cb_event.chat_id,
                        cb_event.message_id,
                    )
                self.kernel.logger.debug("Delete (pts_count=%s)", affected)
            else:
                await cb_event.edit(self.strings["closed"])
        except Exception as e:
            self.kernel.logger.error(
                "Error in _man_close_cb:\n%s", traceback.format_exc()
            )
            self.kernel.handle_error(
                e, message="Failed delete man message!", event=cb_event
            )

    async def _man_page_cb(self, cb_event: InlineMessage, page: int) -> None:
        try:
            hidden = await self._get_hidden_modules()
            msg, buttons = self._get_paginated_data(
                page,
                hidden_list=hidden,
                page_cb=self._man_page_cb,
                close_cb=self._man_close_cb,
            )
            invert_media = (
                self.config.get("man_invert_media", False) if self.config else False
            )
            try:
                await cb_event.edit(
                    self._add_inline_banner_preview(msg),
                    buttons=buttons,
                    parse_mode="html",
                    invert_media=invert_media,
                )
            except TypeError:
                await cb_event.edit(
                    self._add_inline_banner_preview(msg),
                    buttons=buttons,
                    parse_mode="html",
                )
        except Exception as e:
            await cb_event.answer(
                f"{self.strings['page_error']}: {str(e)[:50]}", alert=True
            )

    def _get_paginated_data(
        self,
        page: int,
        hidden_list: list[str] | None = None,
        show_hidden: bool = False,
        *,
        page_cb=None,
        close_cb=None,
        ttl: int = 900,
    ) -> tuple[str, list]:
        if hidden_list is None:
            hidden_list = []
        s = self.strings
        kernel = self.kernel
        cfg = self.config

        def filter_modules(names: list) -> list:
            if show_hidden:
                return names
            return [n for n in names if n not in hidden_list]

        sys_modules = sorted(filter_modules(list(kernel.system_modules.keys())))
        usr_modules = sorted(filter_modules(list(kernel.loaded_modules.keys())))

        def render_module_line(name: str) -> str:
            module_obj = kernel.loaded_modules.get(name)
            class_instance = getattr(module_obj, "_class_instance", None)
            if class_instance is not None:
                display_name = getattr(type(class_instance), "name", name)
            else:
                display_name = name
            if name in sys_modules:
                emoji = cfg.get("man_emoji_system_list", "▫️")
            else:
                emoji = cfg.get("man_emoji_user_list", "▪️")
            commands, aliases_info, _ = self._get_module_commands(name)
            hidden_mark = (
                f" {CUSTOM_EMOJI['eye_off']}"
                if (show_hidden and name in hidden_list)
                else ""
            )
            inline_commands = kernel.get_module_inline_commands(name)

            if commands:
                cmd_display = []
                for cmd in commands[:3]:
                    display_cmd = f"<code>{kernel.custom_prefix}{cmd}</code>"
                    if cmd in aliases_info:
                        aliases = aliases_info[cmd]
                        if isinstance(aliases, list):
                            alias_text = ", ".join(
                                f"<code>{kernel.custom_prefix}{a}</code>"
                                for a in aliases[:2]
                            )
                            if len(aliases) > 2:
                                alias_text += f" (+{len(aliases) - 2})"
                            display_cmd += f" [{alias_text}]"
                        elif isinstance(aliases, str):
                            display_cmd += f" [{kernel.custom_prefix}{aliases}]"
                    cmd_display.append(display_cmd)

                cmd_text = ", ".join(cmd_display)
                if len(commands) > 3:
                    cmd_text += f" (+{len(commands) - 3})"

                if inline_commands:
                    cmd_text += f" {self._format_inline_cmds(inline_commands)}"

                return f"{emoji} <code>{display_name}</code>{hidden_mark}: {cmd_text}\n"
            elif inline_commands:
                inline_cmds = self._format_inline_cmds(inline_commands)
                return f"<code>{display_name}</code>{hidden_mark}: {inline_cmds}\n"
            else:
                no_cmd_emoji = (
                    cfg.get("man_emoji_no_command") or CUSTOM_EMOJI["snowflake"]
                )
                return f"{no_cmd_emoji} <code>{display_name}</code>{hidden_mark}: <i>{s.get('no_commands', 'no commands')}</i>\n"

        def get_modules_per_page() -> int:
            try:
                return max(1, min(50, int(cfg.get("man_modules_per_page", 60))))
            except (TypeError, ValueError):
                return 10

        def chunk_by_modules(items: list) -> list[list]:
            per_page = get_modules_per_page()
            return [items[i : i + per_page] for i in range(0, len(items), per_page)]

        emoji_man = cfg.get("man_emoji", CUSTOM_EMOJI["crystal"])
        usr_chunks = chunk_by_modules(usr_modules)
        total_pages = max(1, len(usr_chunks))
        page = max(0, min(page, total_pages - 1))

        if page == 0:
            msg = f"{emoji_man} <b>{s['system_modules']}:</b> <code>{len(sys_modules)}</code> | <code>{len(usr_modules)}</code>"
            if sys_modules:
                msg += "<blockquote expandable>"
                for name in sys_modules:
                    msg += render_module_line(name)
                msg += "</blockquote>"
            if usr_chunks:
                msg += "<blockquote expandable>"
                for name in usr_chunks[0]:
                    msg += render_module_line(name)

                if len(usr_chunks) > 1:
                    remaining = sum(len(c) for c in usr_chunks[1:])
                    msg += f"<i>... +{remaining}</i>"
                msg += "</blockquote>"

        else:
            current_chunk = usr_chunks[page] if page < len(usr_chunks) else []
            msg = f"{emoji_man} <b>{s['user_modules_page'].format(page=page + 1, count=len(usr_modules))}:</b>"
            msg += "<blockquote expandable>"
            for name in current_chunk:
                msg += render_module_line(name)
            msg += "</blockquote>"

        buttons = []
        page_buttons = []

        prev_page = max(0, page - 1)
        next_page = min(total_pages - 1, page + 1)
        if page_cb:
            page_buttons.append(
                self.Button.inline("<", page_cb, args=[prev_page], ttl=ttl)
            )
        else:
            page_buttons.append(Button.inline("<", data=f"man_page_{prev_page}"))

        max_page_buttons = 7
        if total_pages <= max_page_buttons:
            for i in range(total_pages):
                text = "•" if i == page else str(i + 1)
                if page_cb:
                    page_buttons.append(
                        self.Button.inline(text, page_cb, args=[i], ttl=ttl)
                    )
                else:
                    page_buttons.append(Button.inline(text, data=f"man_page_{i}"))
        else:
            start_idx = max(0, page - 3)
            end_idx = min(total_pages, start_idx + max_page_buttons)
            if end_idx - start_idx < max_page_buttons:
                start_idx = max(0, end_idx - max_page_buttons)

            if start_idx > 0:
                if page_cb:
                    page_buttons.append(
                        self.Button.inline("1", page_cb, args=[0], ttl=ttl)
                    )
                else:
                    page_buttons.append(Button.inline("1", data="man_page_0"))
                if start_idx > 1:
                    page_buttons.append(Button.inline("...", data="noop"))

            for i in range(start_idx, end_idx):
                text = "•" if i == page else str(i + 1)
                if page_cb:
                    page_buttons.append(
                        self.Button.inline(text, page_cb, args=[i], ttl=ttl)
                    )
                else:
                    page_buttons.append(Button.inline(text, data=f"man_page_{i}"))

            if end_idx < total_pages:
                if end_idx < total_pages - 1:
                    page_buttons.append(Button.inline("...", data="noop"))
                if page_cb:
                    page_buttons.append(
                        self.Button.inline(
                            str(total_pages),
                            page_cb,
                            args=[total_pages - 1],
                            ttl=ttl,
                            allow_user=None,
                        )
                    )
                else:
                    page_buttons.append(
                        Button.inline(
                            str(total_pages), data=f"man_page_{total_pages - 1}"
                        )
                    )

        if page_cb:
            page_buttons.append(
                self.Button.inline(">", page_cb, args=[next_page], ttl=ttl)
            )
        else:
            page_buttons.append(Button.inline(">", data=f"man_page_{next_page}"))

        buttons.append(page_buttons)

        if close_cb:
            buttons.append([self.Button.inline("❌ " + s["close"], close_cb, ttl=ttl)])
        else:
            buttons.append([Button.inline("❌ " + s["close"], data="man_close")])

        if self.kernel.load_kernel:
            if self.kernel.load_kernel != "full":
                msg += f"<blockquote>{self.strings('kernel_not_full_loaded', status=self.kernel.load_kernel)}</blockquote>"

        return msg, buttons

    @command(
        "man",
        doc_ru="<name/None> пoкaзaть инфopмaцию o мoдyлe или cпиcoк мoдyлeй",
        doc_en="<name/None> show module info or list modules",
    )
    async def cmd_man(self, event: events.NewMessage.Event) -> None:
        try:
            args = self.args_raw(event).split()
            show_hidden = "-f" in args
            clean_args = [a for a in args if a != "-f"]

            if getattr(event, "piped", False) and not clean_args:
                kernel = self.kernel
                cmds_by_mod = {}

                for cmd, _handler in kernel.command_handlers.items():
                    mod_name = kernel.command_owners.get(cmd, "unknown")
                    if mod_name not in cmds_by_mod:
                        cmds_by_mod[mod_name] = []
                    cmds_by_mod[mod_name].append(cmd)

                lines = []
                for mod_name in sorted(cmds_by_mod.keys()):
                    cmds = cmds_by_mod[mod_name]
                    lines.append(f"{mod_name} ({', '.join(cmds)})")

                result_text = "\n".join(lines) if lines else "Heт мoдyлeй c кoмaндaми"
                await self.edit(event, result_text)
                return

            if not clean_args:
                hidden = await self._get_hidden_modules()
                _usr = sorted(
                    n
                    for n in self.kernel.loaded_modules.keys()
                    if show_hidden or n not in hidden
                )
                try:
                    _per_page = max(
                        1, min(50, int(self.config.get("man_modules_per_page", 10)))
                    )
                except (TypeError, ValueError):
                    _per_page = 10
                _chunks = (
                    [_usr[i : i + _per_page] for i in range(0, len(_usr), _per_page)]
                    if _usr
                    else [[]]
                )
                _total_pages = max(1, len(_chunks))

                if _total_pages == 1:
                    page_msg, _ = self._get_paginated_data(
                        0,
                        hidden_list=hidden,
                        show_hidden=show_hidden,
                    )
                    try:
                        if self.config.get("man_quote_media", False):
                            await self.edit(
                                event,
                                page_msg,
                                file=InputMediaWebPage(
                                    self.config.get(
                                        "man_banner_url",
                                        "https://google.com",
                                    ),
                                    optional=True,
                                ),
                                parse_mode="html",
                                invert_media=self.config.get(
                                    "man_invert_media",
                                    False,
                                ),
                            )
                        elif self.config.get("man_banner_url"):
                            await self.edit(
                                event,
                                page_msg,
                                file=self.config.get("man_banner_url"),
                                parse_mode="html",
                                invert_media=self.config.get(
                                    "man_invert_media",
                                    False,
                                ),
                            )
                        else:
                            await self.edit(event, page_msg, parse_mode="html")
                    except TypeError:
                        await self.edit(event, page_msg, parse_mode="html")
                    return

                try:
                    success, sent = await self.kernel.inline_query_and_click(
                        chat_id=event.chat_id,
                        query="man",
                        reply_to=event.reply_to_msg_id,
                    )
                    if not success:
                        await self.edit(
                            event, self.strings["no_inline_results"], as_html=True
                        )
                        return
                    else:
                        await self.client.delete_messages(event.chat_id, [event.id])
                        if self.config.get("man_banner_url", False) and self.config.get(
                            "man_quote_media", False
                        ):
                            await sent.click(1)

                    if self.config.get("man_invert_media", False):
                        try:
                            page_msg, page_buttons = self._get_paginated_data(
                                0,
                                hidden_list=hidden,
                                show_hidden=show_hidden,
                                page_cb=self._man_page_cb,
                                close_cb=self._man_close_cb,
                            )
                            page_msg = self._add_inline_banner_preview(page_msg)
                            sent_id = (
                                sent[0].id
                                if isinstance(sent, list) and sent
                                else getattr(sent, "id", None)
                            )
                            if sent_id:
                                await self.client.edit_message(
                                    event.chat_id,
                                    sent_id,
                                    page_msg,
                                    buttons=page_buttons,
                                    parse_mode="html",
                                    invert_media=True,
                                )
                        except Exception:
                            pass

                except Exception as e:
                    await self.kernel.handle_error(
                        e, message="Man inline error", event=event
                    )
                    await self.edit(
                        event, f"{self.strings['error']}: {str(e)[:100]}", as_html=True
                    )
            else:
                search_term = " ".join(clean_args)
                msg, banner_url = await self._generate_detailed_page(
                    search_term, show_hidden=show_hidden
                )
                if banner_url and banner_url.startswith(("http://", "https://")):
                    try:
                        media = InputMediaWebPage(banner_url, optional=True)
                        await self.edit(
                            event, msg, file=media, parse_mode="html", invert_media=True
                        )
                    except Exception as e:
                        await self.kernel.handle_error(e, message="Man banner error")
                        await self.edit(event, msg, parse_mode="html")
                else:
                    await self.edit(event, msg, parse_mode="html")

        except Exception as e:
            await self.kernel.handle_error(e, message="Man command error", event=event)

    @command(
        "manhide",
        doc_ru="<name> cкpыть мoдyль из cпиcкa man",
        doc_en="<name> hide module from man list",
    )
    async def cmd_manhide(self, event: events.NewMessage.Event) -> None:
        try:
            module_name = self.args_raw(event).strip()
            if not module_name:
                await self.edit(event, self.strings["manhide_usage"], parse_mode="html")
                return
            s = self.strings

            all_modules = set(self.kernel.system_modules.keys()) | set(
                self.kernel.loaded_modules.keys()
            )
            if module_name not in all_modules:
                matches = [m for m in all_modules if module_name.lower() in m.lower()]
                if len(matches) == 1:
                    module_name = matches[0]
                else:
                    await self.edit(
                        event,
                        f"{self.config.get('man_emoji_error') or CUSTOM_EMOJI['blocked']} {s['module_not_found']}",
                        parse_mode="html",
                    )
                    return

            hidden = await self._get_hidden_modules()
            if module_name in hidden:
                await self.edit(event, s["module_already_hidden"], parse_mode="html")
                return

            hidden.append(module_name)
            await self._save_hidden_modules(hidden)
            await self.edit(
                event,
                f"{s['module_hidden']}\n<code>{module_name}</code>",
                parse_mode="html",
            )
        except Exception as e:
            await self.kernel.handle_error(
                e, message="Manhide command error", event=event
            )

    @command(
        "manunhide",
        doc_ru="<name> пoкaзaть мoдyль в cпиcкe man",
        doc_en="<name> unhide module from man list",
    )
    async def cmd_manunhide(self, event: events.NewMessage.Event) -> None:
        try:
            module_name = self.args_raw(event).strip()
            if not module_name:
                await self.edit(
                    event, self.strings["manunhide_usage"], parse_mode="html"
                )
                return
            s = self.strings

            hidden = await self._get_hidden_modules()

            if module_name not in hidden:
                matches = [m for m in hidden if module_name.lower() in m.lower()]
                if len(matches) == 1:
                    module_name = matches[0]
                else:
                    await self.edit(event, s["module_not_hidden"], parse_mode="html")
                    return

            hidden.remove(module_name)
            await self._save_hidden_modules(hidden)
            await self.edit(
                event,
                f"{s['module_unhidden']}\n<code>{module_name}</code>",
                parse_mode="html",
            )
        except Exception as e:
            await self.kernel.handle_error(
                e, message="Manunhide command error", event=event
            )

    @command("help", doc_ru="пepeнaпpaвляeт нa man", doc_en="redirects to man")
    async def cmd_help(self, event: events.NewMessage.Event) -> None:
        await self.cmd_man(event)

    @inline("man")
    async def inline_man(self, event) -> None:
        query = event.text.strip()
        s = self.strings

        if query == "man":
            thumb1 = self._make_thumb("https://kappa.lol/6plQLz")
            hidden = await self._get_hidden_modules()
            msg1, buttons = self._get_paginated_data(
                0,
                hidden_list=hidden,
                page_cb=self._man_page_cb,
                close_cb=self._man_close_cb,
            )
            article1 = event.builder.article(
                title="Module Manager",
                description="Browse all modules",
                text=self._add_inline_banner_preview(msg1),
                buttons=buttons,
                parse_mode="html",
                thumb=thumb1,
            )

            thumb2 = self._make_thumb("https://kappa.lol/wujauv")
            article2 = event.builder.article(
                title="Search Modules",
                description="Type 'man [name]' to search",
                text=f"<b>{s['search_hint']}</b>",
                parse_mode="html",
                thumb=thumb2,
            )

            await event.answer([article1, article2])
            return

        if query.startswith("man "):
            search_term = query[4:].strip()
            if search_term:
                try:
                    (
                        exact_matches,
                        similar_modules,
                    ) = await self._search_modules_for_inline(search_term)
                    articles = []

                    if exact_matches or similar_modules:
                        thumb_search = self._make_thumb("https://kappa.lol/LOuqBO")

                        result_count = len(exact_matches) + len(similar_modules)
                        search_header = event.builder.article(
                            title=f"Search: {search_term}",
                            description=f"Found {result_count} modules",
                            text=f'<b>🔍 {s["search_results"]}: "{search_term}"</b>\n'
                            f"<i>Haйдeнo {result_count} мoдyлeй</i>\n\n",
                            parse_mode="html",
                            thumb=thumb_search,
                        )
                        articles.append(search_header)

                        for module_info in exact_matches[:10]:
                            name, typ, _ = module_info
                            msg = await self._generate_module_article(module_info)
                            thumb_module = self._make_thumb("https://kappa.lol/POFDmQ")
                            article = event.builder.article(
                                title=f"📦 {name}",
                                description="Exact match",
                                text=msg,
                                parse_mode="html",
                                thumb=thumb_module,
                            )
                            articles.append(article)

                        for module_info in similar_modules[:10]:
                            name, _typ, _ = module_info
                            msg = await self._generate_module_article(module_info)
                            thumb_module = self._make_thumb("https://kappa.lol/POFDmQ")
                            article = event.builder.article(
                                title=f"🔍 {name}",
                                description="Similar match",
                                text=msg,
                                parse_mode="html",
                                thumb=thumb_module,
                            )
                            articles.append(article)

                    else:
                        thumb_not_found = self._make_thumb("https://kappa.lol/N5jMQR")
                        error_emoji = (
                            self.config.get("man_emoji_error")
                            or CUSTOM_EMOJI["blocked"]
                        )
                        not_found_article = event.builder.article(
                            title="Module not found",
                            description=f"No results for '{search_term}'",
                            text=f"<b>{error_emoji} {s['module_not_found']}</b>\n\n"
                            f'<i>Пo зaпpocy "{search_term}" ничeгo нe нaйдeнo.</i>\n'
                            f"{s['not_found_hint']}",
                            parse_mode="html",
                            thumb=thumb_not_found,
                        )
                        articles.append(not_found_article)

                    await event.answer(articles[:50])
                    return

                except Exception as e:
                    thumb_error = self._make_thumb("https://kappa.lol/N5jMQR")
                    error_emoji = (
                        self.config.get("man_emoji_error") or CUSTOM_EMOJI["blocked"]
                    )
                    error_article = event.builder.article(
                        title=s["search_error"],
                        description=s["search_error_desc"],
                        text=f"<b>{error_emoji} {s['error']}</b>\n\n"
                        f"<code>{str(e)[:200]}</code>",
                        parse_mode="html",
                        thumb=thumb_error,
                    )
                    await event.answer([error_article])
                    return

        builder = event.builder.article(
            title="Module Manager",
            description="Type 'man' or 'man [module]'",
            text=f"{self.config.get('man_emoji') or CUSTOM_EMOJI['crystal']} <b>{s['module_manager']}</b>",
            parse_mode="html",
        )
        await event.answer([builder])

    async def _search_modules_for_inline(
        self, search_term: str, show_hidden: bool = False
    ) -> tuple[list, list]:
        search_term = search_term.lower().strip()
        hidden = await self._get_hidden_modules()
        all_modules = self._gather_all_modules(show_hidden, hidden)

        search_words = search_term.split()
        concatenated = "".join(search_words)
        underscored = "_".join(search_words)
        camel_cased = "".join(w.capitalize() for w in search_words)

        scored_modules: list[tuple[int, tuple]] = []

        for name, (typ, module) in all_modules.items():
            name_lower = name.lower()
            score = 0

            if name_lower == search_term:
                scored_modules.append((1000, (name, typ, module)))
                continue

            if name_lower.startswith(search_term):
                score += 500
            elif search_term in name_lower:
                score += 300
            elif concatenated in name_lower:
                score += 250
            elif underscored in name_lower or camel_cased.lower() in name_lower:
                score += 220
            else:
                words = search_words
                if all(w in name_lower for w in words):
                    score += 200

            if score > 0:
                scored_modules.append((score, (name, typ, module)))
                continue

            commands, _, _descriptions = self._get_module_commands(name)
            cmd_match = False
            for cmd in commands:
                cmd_lower = cmd.lower()
                if cmd_lower == search_term:
                    scored_modules.append((900, (name, typ, module)))
                    cmd_match = True
                    break
                elif cmd_lower.startswith(search_term):
                    score = 600
                elif concatenated in cmd_lower:
                    score = 550
                elif underscored in cmd_lower or camel_cased.lower() in cmd_lower:
                    score = 520
                elif search_term in cmd_lower:
                    score = 400

                if score > 0:
                    scored_modules.append((score, (name, typ, module)))
                    cmd_match = True
                    break
            if cmd_match:
                continue

            metadata = await self._load_module_metadata(name, typ)

            desc = metadata.get("description", "").lower()
            if desc and search_term in desc:
                scored_modules.append((100, (name, typ, module)))
                continue

            for cmd, cmd_desc in metadata.get("commands", {}).items():
                if (
                    cmd_desc
                    and isinstance(cmd_desc, str)
                    and search_term in cmd_desc.lower()
                ):
                    scored_modules.append((50, (name, typ, module)))
                    break

        scored_modules.sort(key=lambda x: -x[0])
        seen = set()
        exact_matches = []
        similar_modules = []
        for score, (name, typ, module) in scored_modules:
            if name in seen:
                continue
            seen.add(name)
            if score >= 900:
                exact_matches.append((name, typ, module))
            else:
                similar_modules.append((name, typ, module))

        return exact_matches, similar_modules

    async def _generate_module_article(self, module_info: tuple) -> str:
        name, typ, _module = module_info
        s = self.strings
        commands, _aliases_info, descriptions = self._get_module_commands(name)
        metadata = await self._load_module_metadata(name, typ)

        module_emoji = self.config.get("man_emoji") or CUSTOM_EMOJI["dna"]
        author_emoji = self.config.get("man_emoji_author") or CUSTOM_EMOJI["alembic"]
        no_command_emoji = (
            self.config.get("man_emoji_no_command") or CUSTOM_EMOJI["snowflake"]
        )

        msg = f"<blockquote>{module_emoji} <b>{s['module']}</b> <code>{name}</code></blockquote>\n"
        msg += f"<blockquote expandable>{author_emoji} <b>{s['description']}:</b> <i>{metadata.get('description', s['no_description'])}</i>\n</blockquote>"

        if commands:
            msg += f"\n<b>{s['command']}:</b>\n"
            msg += "<blockquote expandable>"
            for cmd in commands[:5]:
                cmd_desc = (
                    descriptions.get(cmd)
                    or metadata.get("commands", {}).get(cmd)
                    or f"{CUSTOM_EMOJI['confused']} {s['no_description']}"
                )
                msg += f"• <code>{self.kernel.custom_prefix}{cmd}</code> - {cmd_desc}\n"
            if len(commands) > 5:
                msg += f"... {s['and_more_commands'].format(count=len(commands) - 5)}\n"
        else:
            msg += f"\n{no_command_emoji} {s['no_commands']}\n"
        msg += "</blockquote>"

        msg += f"\n<blockquote>{CUSTOM_EMOJI['snowflake']} <b>{s['version']}:</b> <code>{metadata.get('version', '1.0.0')}</code>"
        msg += f"\n{author_emoji} <b>{s['author']}:</b> <i>{metadata.get('author', s['unknown'])}</i></blockquote>"

        if typ == "system":
            msg += (
                "\n<blockquote>"
                + self.strings(
                    "system_module_note",
                    blocked=self.config.get("man_emoji_error")
                    or CUSTOM_EMOJI["blocked"],
                )
                + "</blockquote>"
            )

        return msg
