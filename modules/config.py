from __future__ import annotations

# author: @Hairpin00
# version: 1.3.0
# description: config Kernel

import json
import html
import hashlib
import re
import uuid
import time
import asyncio
from telethon import Button, events, types
from telethon.tl.types import InputWebDocument, DocumentAttributeImageSize
from core.lib.loader.module_config import ModuleConfig, ValidationError


def is_module_config_like(obj) -> bool:
    """Check if object is a ModuleConfig-like (MCUB or Hikka compat)."""
    if isinstance(obj, ModuleConfig):
        return True
    if hasattr(obj, "_is_hikka_compat") and obj._is_hikka_compat:
        return True
    if hasattr(obj, "_config") and hasattr(obj, "_values"):
        return True
    return False


def update_live_config_schema(kernel, module_name, key=None, value=None):
    """Update live ModuleConfig schema after config change."""
    try:
        live_cfg = kernel._live_module_configs.get(module_name)
        if live_cfg and hasattr(live_cfg, "_values"):
            if key is not None and value is not None:
                live_cfg[key] = value
            return live_cfg
    except Exception:
        pass
    return None


CUSTOM_EMOJI = {
    "📁": '<tg-emoji emoji-id="5433653135799228968">📁</tg-emoji>',
    "📝": '<tg-emoji emoji-id="5334882760735598374">📝</tg-emoji>',
    "📚": '<tg-emoji emoji-id="5373098009640836781">📚</tg-emoji>',
    "📖": '<tg-emoji emoji-id="5226512880362332956">📖</tg-emoji>',
    "💼": '<tg-emoji emoji-id="5359785904535774578">💼</tg-emoji>',
    "🖨": '<tg-emoji emoji-id="5386494631112353009">🖨</tg-emoji>',
    "☑️": '<tg-emoji emoji-id="5454096630372379732">☑️</tg-emoji>',
    "➕": '<tg-emoji emoji-id="5226945370684140473">➕</tg-emoji>',
    "➖": '<tg-emoji emoji-id="5229113891081956317">➖</tg-emoji>',
    "💬": '<tg-emoji emoji-id="5465300082628763143">💬</tg-emoji>',
    "🗯": '<tg-emoji emoji-id="5465132703458270101">🗯</tg-emoji>',
    "✏️": '<tg-emoji emoji-id="5334673106202010226">✏️</tg-emoji>',
    "🧊": '<tg-emoji emoji-id="5404728536810398694">🧊</tg-emoji>',
    "❄️": '<tg-emoji emoji-id="5431895003821513760">❄️</tg-emoji>',
    "📎": '<tg-emoji emoji-id="5377844313575150051">📎</tg-emoji>',
    "🗳": '<tg-emoji emoji-id="5359741159566484212">🗳</tg-emoji>',
    "🗂": '<tg-emoji emoji-id="5431736674147114227">🗂</tg-emoji>',
    "📰": '<tg-emoji emoji-id="5433982607035474385">📰</tg-emoji>',
    "🔍": '<tg-emoji emoji-id="5429283852684124412">🔍</tg-emoji>',
    "📋": '<tg-emoji emoji-id="5431736674147114227">📋</tg-emoji>',
    "⚙️": '<tg-emoji emoji-id="5332654441508119011">⚙️</tg-emoji>',
    "🔢": '<tg-emoji emoji-id="5465154440287757794">🔢</tg-emoji>',
    "🔙": '<tg-emoji emoji-id="5332600281970517875">🔙</tg-emoji>',
    "✅": '<tg-emoji emoji-id="5118861066981344121">✅</tg-emoji>',
    "❌": '<tg-emoji emoji-id="5370843963559254781">❌</tg-emoji>',
    "🔄": '<tg-emoji emoji-id="5332600281970517875">🔄</tg-emoji>',
    "🧩": '<tg-emoji emoji-id="5359785904535774578">🧩</tg-emoji>',
    "🔧": '<tg-emoji emoji-id="5332654441508119011">🔧</tg-emoji>',
}

ITEMS_PER_PAGE = 16
MODULES_PER_PAGE = 12
INLINE_RESULTS_LIMIT = 50

TYPE_EMOJIS = {
    "str": "📝",
    "int": "🔢",
    "float": "🔢",
    "bool": "☑️",
    "list": "📚",
    "dict": "🗂",
    "NoneType": "🗳",
    "hidden": "🔒",
}


class InlineMessageManager:
    def __init__(self, kernel):
        self.kernel = kernel
        self.messages = {}  # {inline_msg_id: (chat_id, message_id, key_id, user_id)}

    def save_message(self, inline_msg_id, chat_id, message_id, key_id, user_id):
        self.messages[inline_msg_id] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "key_id": key_id,
            "user_id": user_id,
            "timestamp": time.time(),
        }
        asyncio.create_task(self.save_to_db())

    async def save_to_db(self):
        try:
            await self.kernel.db_set(
                "cfg_messages", "inline_messages", json.dumps(self.messages)
            )
        except Exception as e:
            self.kernel.logger.debug(f"Error saving inline messages: {e}")

    async def load_from_db(self):
        try:
            data = await self.kernel.db_get("cfg_messages", "inline_messages")
            if data:
                self.messages = json.loads(data)
        except Exception as e:
            self.kernel.logger.debug(f"Error loading inline messages: {e}")

    def get_message_info(self, inline_msg_id):
        return self.messages.get(inline_msg_id)

    def remove_message(self, inline_msg_id):
        if inline_msg_id in self.messages:
            del self.messages[inline_msg_id]
            asyncio.create_task(self.save_to_db())


async def init_module_config(kernel):
    default_config = {
        "use_premium_emoji": True,
        "items_per_page": 16,
        "modules_per_page": 12,
    }
    config = await kernel.get_module_config("config", None)

    if config is None:
        await kernel.save_module_config("config", default_config)
        config = default_config
    elif not isinstance(config, dict):
        await kernel.save_module_config("config", default_config)
        config = default_config

    return config


class EmojiProvider:
    def __init__(self, kernel, custom_emoji_dict):
        self.kernel = kernel
        self.custom_emoji_dict = custom_emoji_dict
        self._use_premium = True
        self._last_check = 0

    def _should_update_cache(self):
        current_time = time.time()
        if current_time - self._last_check > 60:
            self._last_check = current_time
            return True
        return False

    async def _update_cache(self):
        try:
            config = await self.kernel.get_module_config("config", {})
            self._use_premium = config.get("use_premium_emoji", True)
        except Exception:
            self._use_premium = True

    def __getitem__(self, emoji_char):
        if self._should_update_cache():
            try:
                import asyncio

                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self._update_cache())
            except Exception:
                pass

        if self._use_premium:
            return self.custom_emoji_dict.get(emoji_char, emoji_char)
        else:
            return emoji_char

    def get(self, emoji_char, default=None):
        try:
            return self[emoji_char]
        except Exception:
            return default if default is not None else emoji_char


class ConfigSettings:
    def __init__(self, kernel):
        self.kernel = kernel
        self._items_per_page = ITEMS_PER_PAGE
        self._modules_per_page = MODULES_PER_PAGE
        self._last_check = 0

    def _should_update_cache(self):
        current_time = time.time()
        if current_time - self._last_check > 60:
            self._last_check = current_time
            return True
        return False

    async def _update_cache(self):
        try:
            config = await self.kernel.get_module_config("config", {})
            self._items_per_page = config.get("items_per_page", ITEMS_PER_PAGE)
            self._modules_per_page = config.get("modules_per_page", MODULES_PER_PAGE)
        except Exception:
            self._items_per_page = ITEMS_PER_PAGE
            self._modules_per_page = MODULES_PER_PAGE

    @property
    def items_per_page(self):
        if self._should_update_cache():
            try:
                import asyncio

                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self._update_cache())
            except:
                pass
        return self._items_per_page

    @property
    def modules_per_page(self):
        if self._should_update_cache():
            try:
                import asyncio

                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self._update_cache())
            except:
                pass
        return self._modules_per_page


def register(kernel):
    language = kernel.config.get("language", "en")

    emoji_provider = EmojiProvider(kernel, CUSTOM_EMOJI)
    config_settings = ConfigSettings(kernel)

    config_initialized = {"value": False}

    MODULES_WITH_CONFIG_CACHE_TTL = 600

    def get_modules_with_config(force_refresh=False):
        """Get list of modules that have config (from live configs or cache)"""
        cache_key = "modules_with_config_list"
        cached = kernel.cache.get(cache_key)

        # Always include live configs - they are always up to date
        live_configs = getattr(kernel, "_live_module_configs", {})
        modules_with_config = set(live_configs.keys())

        # Add cached modules that might not be in live configs anymore
        if cached and not force_refresh:
            modules_with_config.update(cached)
            return sorted(list(modules_with_config))

        # Cache miss or refresh - rebuild from live configs
        result = sorted(list(modules_with_config))
        kernel.cache.set(cache_key, result, ttl=MODULES_WITH_CONFIG_CACHE_TTL)
        return result

    def add_module_to_config_cache(module_name):
        """Add a module to the config cache (called when config is saved)"""
        cache_key = "modules_with_config_list"
        cached = kernel.cache.get(cache_key)
        if cached is None:
            cached = []
        if module_name not in cached:
            cached.append(module_name)
            cached = sorted(cached)
            kernel.cache.set(cache_key, cached, ttl=MODULES_WITH_CONFIG_CACHE_TTL)

    async def ensure_config_initialized():
        if not config_initialized["value"]:
            try:
                config = await init_module_config(kernel)
                emoji_provider._use_premium = config.get("use_premium_emoji", True)
                config_settings._items_per_page = config.get(
                    "items_per_page", ITEMS_PER_PAGE
                )
                config_settings._modules_per_page = config.get(
                    "modules_per_page", MODULES_PER_PAGE
                )
                config_initialized["value"] = True
            except Exception as e:
                kernel.logger.debug(f"Error initializing config module config: {e}")

    strings = {
        "en": {
            "config_menu_text": "{menu_emoji} <b>Config Menu</b>\nChoose configuration section:",
            "btn_kernel_config": "🪄 Kernel Config",
            "btn_modules_config": "🚂 Modules Config",
            "kernel_config_title": "{pencil} <b>Kernel Config</b>\n{page_emoji} Page <b>{page}/{total_pages}</b> ({total_keys} keys)",
            "modules_config_title": "{puzzle} <b>Modules Config</b>\n{page_emoji} Page <b>{page}/{total_pages}</b> ({total_modules} modules)",
            "module_config_title": "{puzzle} <b>Module:</b> <code>{module_name}</code>\n{page_emoji} Page <b>{page}/{total_pages}</b> ({total_items} keys)",
            "key_view": "{note} <b>{key}</b> ({type_emoji} {value_type})\n{display_value}",
            "btn_back": "⬅️",
            "btn_next": "➡️",
            "btn_menu": "🔙 Menu",
            "btn_modules": "🔙 Modules",
            "btn_back_simple": "🔙 Back",
            "expired": "❌ Expired",
            "invalid_type": "❌ Invalid config type",
            "not_found": "❌ Not found",
            "no_config": "❌ Module has no config",
            "no_default": "❌ No default value",
            "not_module_config": "❌ Not a ModuleConfig",
            "not_boolean": "❌ Not boolean",
            "btn_reset_default": "♻️ Reset to default",
            "reset_success": "♻️ Reset to default",
            "changed_to": "✅ Changed to {value}",
            "error": "❌ Error: {error}",
            "cfg_usage": "{gear} <b>Config</b>: Use inline or <code>.cfg [key]</code> or <code>.cfg [now/hide/unhide] [key]</code>",
            "hidden_key": "{briefcase} <b>Hidden</b>: <code>{key}</code>",
            "key_not_found": "{ballot} <b>Not found</b>: <code>{key}</code>",
            "system_key": "{paperclip} <b>System key</b>",
            "visible_key": "{book} <b>Visible</b>: <code>{key}</code>",
            "fcfg_usage": "{gear} <code>.fcfg [set/del/add/dict/list] -m [modules]</code>",
            "specify_module": "{cross} Specify module name after -m",
            "not_enough_args": "{cross} Not enough arguments",
            "protected_key": "{cross} <b>Protected</b>",
            "set_success": "{check} <b>Set</b> <code>{key}</code> = <code>{value}</code>",
            "set_module_success": "{check} <b>Set</b> module <code>{module}</code> key <code>{key}</code> = <code>{value}</code>",
            "delete_success": "{ballot} <b>Deleted</b> <code>{key}</code>",
            "delete_module_success": "{ballot} <b>Deleted</b> module <code>{module}</code> key <code>{key}</code>",
            "not_found_in_module": "{cross} Not found in module config",
            "key_exists": "{cross} Exists",
            "add_success": "{check} <b>Added</b> <code>{key}</code>",
            "add_module_success": "{check} <b>Added</b> module <code>{module}</code> key <code>{key}</code>",
            "not_dict": "{cross} Key is not a dict",
            "dict_success": "{check} <b>Dict</b> <code>{key}[{subkey}]</code> updated",
            "dict_module_success": "{check} <b>Dict</b> module <code>{module}</code> key <code>{key}[{subkey}]</code> updated",
            "not_list": "{cross} Key is not a list",
            "list_success": "{check} <b>List</b> <code>{key}</code> appended",
            "list_module_success": "{check} <b>List</b> module <code>{module}</code> key <code>{key}</code> appended",
            "toggle_false": "❌ Set false",
            "toggle_true": "✅ Set true",
            "cfg_range_both": "Value must be between {min} and {max}",
            "cfg_range_min": "Value cannot be less than {min}",
            "cfg_range_max": "Value cannot exceed {max}",
            "cfg_len_both": "Length must be between {min} and {max} characters",
            "cfg_len_min": "Length must be at least {min} characters",
            "cfg_len_max": "Length must be no more than {max} characters",
            "cfg_type_bool": "Value must be boolean (true/false)",
            "cfg_choices": "Available options",
            "invalid_format": "❌ Invalid format",
            "btn_edit": "✏️ Edit",
            "btn_delete": "🗑️ Delete",
            "btn_reveal": "👁️ Reveal",
            "btn_list_add": "📝 Add to list",
            "btn_list_del": "🗑️ Remove from list",
            "btn_list_set": "✏️ Edit list element",
            "btn_dict_add": "🔑 Add to dict",
            "btn_dict_del": "🗑️ Remove dict key",
            "btn_dict_set": "✏️ Edit dict value",
            "fcfg_inline_usage": "Usage: fcfg set <key_id> <value> | fcfg list/dict <add/del/set> <key_id> [value] | fcfg module <module> ...",
            "fcfg_inline_only_set": "❌ Only set action is supported in inline mode",
            "fcfg_inline_no_module": "❌ Invalid module/key combination",
            "fcfg_inline_success": "✅ Key {key} changed to {value}",
            "fcfg_inline_id_not_found": "❌ Key ID not found or expired",
            "fcfg_inline_protected": "❌ This key is protected",
            "fcfg_confirm_title": "✅ Confirm Value",
            "fcfg_confirm_text": "Value will be passed to config",
            "fcfg_confirm_success": "✅ Config key {key} updated to {value}",
            "fcfg_confirm_error": "❌ Error updating config: {error}",
            "fcfg_confirm_expired": "❌ Confirmation expired or already used",
            "key_deleted": "🗑️ Key deleted",
            "value_inserted": "✅ Value inserted",
            "list_empty": "📭 List is empty",
            "dict_empty": "📭 Dictionary is empty",
            "list_add_confirm": "➕ Append: {value}",
            "list_remove_confirm": "🗑️ Remove element {index}: {value}",
            "list_set_confirm": "✏️ Replace element {index}: {old} → {new}",
            "dict_add_confirm": "🔑 Add key: {key} = {value}",
            "dict_remove_confirm": "🗑️ Remove key: {key}",
            "dict_set_confirm": "✏️ Set key {key}: {old} → {new}",
            "operation_success": "✅ Operation successful",
            "operation_failed": "❌ Operation failed: {error}",
            "btn_close": "❌ Close",
            "kernel_config_title_short": "Kernel Config - {page}",
            "modules_config_title_short": "Modules Config - {page}",
        },
        "ru": {
            "config_menu_text": "{menu_emoji} <b>Меню конфига</b>\nВыберите раздел:",
            "btn_kernel_config": "🪄 Конфиг ядра",
            "btn_modules_config": "🚂 Конфиг модулей",
            "kernel_config_title": "{pencil} <b>Конфиг ядра</b>\n{page_emoji} Страница <b>{page}/{total_pages}</b> ({total_keys} ключей)",
            "modules_config_title": "{puzzle} <b>Конфиг модулей</b>\n{page_emoji} Страница <b>{page}/{total_pages}</b> ({total_modules} модулей)",
            "module_config_title": "{puzzle} <b>Модуль:</b> <code>{module_name}</code>\n{page_emoji} Страница <b>{page}/{total_pages}</b> ({total_items} ключей)",
            "key_view": "{note} <b>{key}</b> ({type_emoji} {value_type})\n{display_value}",
            "btn_back": "⬅️",
            "btn_next": "➡️",
            "btn_menu": "🔙 Меню",
            "btn_modules": "🔙 Модули",
            "btn_back_simple": "🔙 Назад",
            "expired": "❌ Истекло",
            "invalid_type": "❌ Неверный тип конфига",
            "not_found": "❌ Не найдено",
            "no_config": "❌ У модуля нет конфига",
            "no_default": "❌ Нет значения по умолчанию",
            "not_module_config": "❌ Это не ModuleConfig",
            "not_boolean": "❌ Не булево значение",
            "btn_reset_default": "♻️ Сбросить на default",
            "reset_success": "♻️ Сброшено на default",
            "changed_to": "✅ Изменено на {value}",
            "error": "❌ Ошибка: {error}",
            "cfg_usage": "{gear} <b>Конфиг</b>: Используйте инлайн или <code>.cfg [ключ]</code> или <code>.cfg [now/hide/unhide] [ключ]</code>",
            "hidden_key": "{briefcase} <b>Скрытый</b>: <code>{key}</code>",
            "key_not_found": "{ballot} <b>Не найден</b>: <code>{key}</code>",
            "system_key": "{paperclip} <b>Системный ключ</b>",
            "visible_key": "{book} <b>Видимый</b>: <code>{key}</code>",
            "fcfg_usage": "{gear} <code>.fcfg [set/del/add/dict/list] -m [модули]</code>",
            "specify_module": "{cross} Укажите имя модуля после -m",
            "not_enough_args": "{cross} Недостаточно аргументов",
            "protected_key": "{cross} <b>Защищённый</b>",
            "set_success": "{check} <b>Установлено</b> <code>{key}</code> = <code>{value}</code>",
            "set_module_success": "{check} <b>Установлено</b> в модуле <code>{module}</code> ключ <code>{key}</code> = <code>{value}</code>",
            "delete_success": "{ballot} <b>Удалён</b> <code>{key}</code>",
            "delete_module_success": "{ballot} <b>Удалён</b> из модуля <code>{module}</code> ключ <code>{key}</code>",
            "not_found_in_module": "{cross} Не найдено в конфиге модуля",
            "key_exists": "{cross} Уже существует",
            "add_success": "{check} <b>Добавлен</b> <code>{key}</code>",
            "add_module_success": "{check} <b>Добавлен</b> в модуль <code>{module}</code> ключ <code>{key}</code>",
            "not_dict": "{cross} Ключ не является словарём",
            "dict_success": "{check} <b>Словарь</b> <code>{key}[{subkey}]</code> обновлён",
            "dict_module_success": "{check} <b>Словарь</b> в модуле <code>{module}</code> ключ <code>{key}[{subkey}]</code> обновлён",
            "not_list": "{cross} Ключ не является списком",
            "list_success": "{check} <b>Список</b> <code>{key}</code> дополнен",
            "list_module_success": "{check} <b>Список</b> в модуле <code>{module}</code> ключ <code>{key}</code> дополнен",
            "toggle_false": "❌ Установить false",
            "toggle_true": "✅ Установить true",
            "cfg_range_both": "Значение должно быть от {min} до {max}",
            "cfg_range_min": "Значение не может быть меньше {min}",
            "cfg_range_max": "Значение не может превышать {max}",
            "cfg_len_both": "Длина должна быть от {min} до {max} символов",
            "cfg_len_min": "Длина должна быть не менее {min} символов",
            "cfg_len_max": "Длина должна быть не более {max} символов",
            "cfg_type_bool": "Значение должно быть логическим (true/false)",
            "cfg_choices": "Доступные варианты",
            "invalid_format": "❌ Неверный формат",
            "btn_edit": "✏️ Изменить",
            "btn_delete": "🗑️ Удалить",
            "btn_reveal": "👁️ Показать",
            "btn_list_add": "📝 Добавить в список",
            "btn_list_del": "🗑️ Удалить из списка",
            "btn_list_set": "✏️ Изменить элемент списка",
            "btn_dict_add": "🔑 Добавить в словарь",
            "btn_dict_del": "🗑️ Удалить ключ словаря",
            "btn_dict_set": "✏️ Изменить значение словаря",
            "fcfg_inline_usage": "Использование: fcfg set <key_id> <value> | fcfg list/dict <add/del/set> <key_id> [value] | fcfg module <module> ...",
            "fcfg_inline_only_set": "❌ Только set действие поддерживается в инлайн режиме",
            "fcfg_inline_no_module": "❌ Неверная комбинация модуля/ключа",
            "fcfg_inline_success": "✅ Ключ {key} изменён на {value}",
            "fcfg_inline_id_not_found": "❌ ID ключа не найден или истёк",
            "fcfg_inline_protected": "❌ Этот ключ защищён",
            "fcfg_confirm_title": "✅ Подтвердите значение",
            "fcfg_confirm_text": "Значение будет передано в конфиг",
            "fcfg_confirm_success": "✅ Конфиг ключ {key} обновлён на {value}",
            "fcfg_confirm_error": "❌ Ошибка обновления конфига: {error}",
            "fcfg_confirm_expired": "❌ Подтверждение истекло или уже использовано",
            "key_deleted": "🗑️ Ключ удалён",
            "value_inserted": "✅ Значение вставлено",
            "list_empty": "📭 Список пуст",
            "dict_empty": "📭 Словарь пуст",
            "list_add_confirm": "➕ Добавить: {value}",
            "list_remove_confirm": "🗑️ Удалить элемент {index}: {value}",
            "list_set_confirm": "✏️ Заменить элемент {index}: {old} → {new}",
            "dict_add_confirm": "🔑 Добавить ключ: {key} = {value}",
            "dict_remove_confirm": "🗑️ Удалить ключ: {key}",
            "dict_set_confirm": "✏️ Установить ключ {key}: {old} → {new}",
            "operation_success": "✅ Операция успешна",
            "operation_failed": "❌ Операция не удалась: {error}",
            "btn_close": "❌ Закрыть",
            "kernel_config_title_short": "Конфиг ядра - {page}",
            "modules_config_title_short": "Конфиг модулей - {page}",
        },
    }

    lang_strings = strings.get(language, strings["en"])

    def t(string_key, **kwargs):
        if string_key not in lang_strings:
            return string_key
        return lang_strings[string_key].format(**kwargs)

    SENSITIVE_KEYS = ["inline_bot_token", "api_id", "api_hash", "phone"]

    msg_manager = InlineMessageManager(kernel)
    asyncio.create_task(msg_manager.load_from_db())

    class CustomJSONEncoder(json.JSONEncoder):
        def encode(self, o):
            result = super().encode(o)
            result = re.sub(r'(?<!\\)\\\\(n|t|r|f|b|")', r"\\\1", result)
            return result

    async def save_config():
        try:
            with open(kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(
                    kernel.config,
                    f,
                    ensure_ascii=False,
                    indent=2,
                    cls=CustomJSONEncoder,
                )
        except Exception as e:
            await kernel.handle_error(e, source="save_config")

    def parse_value(value_str, expected_type=None):
        value_str = value_str.strip()
        if value_str.lower() == "null":
            return None

        if expected_type:
            if expected_type == "bool":
                if value_str.lower() == "true":
                    return True
                elif value_str.lower() == "false":
                    return False
                else:
                    raise ValueError("Must be true or false")
            elif expected_type == "int":
                return int(value_str)
            elif expected_type == "float":
                return float(value_str)
            elif expected_type == "dict":
                return json.loads(value_str)
            elif expected_type == "list":
                return json.loads(value_str)
            elif expected_type == "str":
                value_str = re.sub(r"(?<!\\)\\n", "\n", value_str)
                value_str = re.sub(r"(?<!\\)\\t", "\t", value_str)
                value_str = re.sub(r"(?<!\\)\\r", "\r", value_str)
                value_str = re.sub(r"\\\\n", "\\n", value_str)
                value_str = re.sub(r"\\\\t", "\\t", value_str)
                return value_str

        if value_str.lower() == "true":
            return True
        elif value_str.lower() == "false":
            return False
        elif value_str.isdigit() or (
            value_str.startswith("-") and value_str[1:].isdigit()
        ):
            return int(value_str)
        elif value_str.replace(".", "", 1).isdigit() and value_str.count(".") == 1:
            return float(value_str)
        elif value_str.startswith("{") and value_str.endswith("}"):
            try:
                return json.loads(value_str)
            except:
                return value_str
        elif value_str.startswith("[") and value_str.endswith("]"):
            try:
                return json.loads(value_str)
            except:
                return value_str
        else:
            value_str = re.sub(r"(?<!\\)\\n", "\n", value_str)
            value_str = re.sub(r"(?<!\\)\\t", "\t", value_str)
            value_str = re.sub(r"(?<!\\)\\r", "\r", value_str)
            value_str = re.sub(r"\\\\n", "\\n", value_str)
            value_str = re.sub(r"\\\\t", "\\t", value_str)
            return value_str

    def strip_formatting(value_str):
        value_str = html.unescape(value_str)

        value_str = re.sub(
            r"\|\|(.+?)\|\|", r"\1", value_str, flags=re.DOTALL
        )  # ||spoiler||
        value_str = re.sub(
            r"```(?:\w+\n)?(.*?)```", r"\1", value_str, flags=re.DOTALL
        )  # ```code```
        value_str = re.sub(r"`(.+?)`", r"\1", value_str, flags=re.DOTALL)  # `code`
        value_str = re.sub(
            r"\*\*(.+?)\*\*", r"\1", value_str, flags=re.DOTALL
        )  # **bold**
        value_str = re.sub(
            r"__(.+?)__", r"\1", value_str, flags=re.DOTALL
        )  # __underline__
        value_str = re.sub(
            r"~~(.+?)~~", r"\1", value_str, flags=re.DOTALL
        )  # ~~strikethrough~~
        value_str = re.sub(r"\*(.+?)\*", r"\1", value_str, flags=re.DOTALL)  # *italic*
        value_str = re.sub(
            r"(?<!\w)_(.+?)_(?!\w)", r"\1", value_str, flags=re.DOTALL
        )  # _italic_
        return value_str

    def is_key_hidden(key):
        hidden_keys = kernel.config.get("hidden_keys", [])
        return key in SENSITIVE_KEYS or key in hidden_keys

    def get_visible_keys():
        visible_keys = []
        for key, value in kernel.config.items():
            if is_key_hidden(key):
                visible_keys.append((key, "*" * len(key)))
            else:
                visible_keys.append((key, value))
        return sorted(visible_keys, key=lambda x: x[0])

    def get_type_emoji(value_type):
        return TYPE_EMOJIS.get(value_type, "📎")

    def truncate_key(key, max_length=15):
        if len(key) > max_length:
            return key[: max_length - 3] + "..."
        return key

    def truncate_module_name(name, max_length=12):
        if len(name) > max_length:
            return name[: max_length - 3] + "..."
        return name

    def generate_key_id(key, page, config_type="kernel"):
        hash_obj = hashlib.md5(f"{config_type}_{key}_{page}".encode())
        return hash_obj.hexdigest()[:8]

    def format_key_value(key, value, reveal=False):
        value_type = type(value).__name__

        if is_key_hidden(key) and not reveal:
            display_value = "*" * len(key)
            value_type = "hidden"
            type_emoji = get_type_emoji("hidden")
        else:
            type_emoji = get_type_emoji(value_type)
            if isinstance(value, (dict, list)):
                formatted_value = json.dumps(value, ensure_ascii=False, indent=2)
                display_value = f"<pre>{html.escape(formatted_value)}</pre>"
            elif value is None:
                display_value = "<code>null</code>"
            elif isinstance(value, bool):
                display_value = (
                    "✔️ <code>true</code>" if value else "✖️ <code>false</code>"
                )
            elif isinstance(value, str):
                escaped_value = html.escape(value)
                display_value = f"<code>{escaped_value}</code>"
            else:
                display_value = f"<code>{html.escape(str(value))}</code>"

        text = t(
            "key_view",
            note=emoji_provider["📝"],
            key=key,
            type_emoji=type_emoji,
            value_type=value_type,
            display_value=display_value,
        )
        return text

    async def show_key_view(event, key_id, reveal=False):
        cached = kernel.cache.get(f"cfg_view_{key_id}")
        if not cached:
            await event.answer(t("expired"), alert=True)
            return None, None, None, None, None

        key, page, config_type = cached
        if config_type != "kernel":
            await event.answer(t("invalid_type"), alert=True)
            return None, None, None, None, None

        if key not in kernel.config:
            await event.answer(t("not_found"), alert=True)
            return None, None, None, None, None

        value = kernel.config[key]
        text = format_key_value(key, value, reveal)
        return text, key, page, config_type, key_id

    def create_kernel_buttons_grid(page_keys, page, total_pages):
        buttons = []
        row = []
        for i, (key, value) in enumerate(page_keys):
            display_key = truncate_key(key)
            key_id = generate_key_id(key, page, "kernel")
            kernel.cache.set(f"cfg_view_{key_id}", (key, page, "kernel"), ttl=86400)
            row.append(Button.inline(display_key, data=f"cfg_view_{key_id}".encode()))
            if len(row) == 4:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        nav_buttons = []
        if page > 0:
            nav_buttons.append(
                Button.inline(
                    t("btn_back"), data=f"config_kernel_page_{page - 1}".encode()
                )
            )
        if page < total_pages - 1:
            nav_buttons.append(
                Button.inline(
                    t("btn_next"), data=f"config_kernel_page_{page + 1}".encode()
                )
            )
        nav_buttons.append(Button.inline(t("btn_menu"), data="config_menu".encode()))
        if nav_buttons:
            buttons.append(nav_buttons)

        buttons.append([Button.inline("❌ Close", data=b"cfg_close", style="danger")])

        return buttons

    def create_modules_buttons_grid(modules, page, total_pages):
        buttons = []
        row = []
        for i, module_name in enumerate(modules):
            display_name = truncate_module_name(module_name)
            key_id = generate_key_id(module_name, page, "module")
            kernel.cache.set(f"module_select_{key_id}", (module_name, page), ttl=86400)
            row.append(
                Button.inline(display_name, data=f"module_select_{key_id}".encode())
            )
            if len(row) == 4:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        nav_buttons = []
        if page > 0:
            nav_buttons.append(
                Button.inline(
                    t("btn_back"), data=f"config_modules_page_{page - 1}".encode()
                )
            )
        if page < total_pages - 1:
            nav_buttons.append(
                Button.inline(
                    t("btn_next"), data=f"config_modules_page_{page + 1}".encode()
                )
            )
        nav_buttons.append(Button.inline(t("btn_menu"), data="config_menu".encode()))
        if nav_buttons:
            buttons.append(nav_buttons)

        buttons.append([Button.inline("❌ Close", data=b"cfg_close", style="danger")])

        return buttons

    def create_module_config_buttons(module_name, page_keys, page, total_pages):
        buttons = []
        row = []
        for i, (key, value) in enumerate(page_keys):
            display_key = truncate_key(key)
            key_id = generate_key_id(f"{module_name}__{key}", page, "module_cfg")
            kernel.cache.set(
                f"module_cfg_view_{key_id}", (module_name, key, page), ttl=86400
            )
            row.append(
                Button.inline(display_key, data=f"module_cfg_view_{key_id}".encode())
            )
            if len(row) == 4:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        nav_buttons = []
        if page > 0:
            nav_id = generate_key_id(module_name, page - 1, "module_nav")
            kernel.cache.set(f"module_nav_{nav_id}", (module_name, page - 1), ttl=86400)
            nav_buttons.append(
                Button.inline(
                    t("btn_back"),
                    data=f"module_cfg_page_nav_{nav_id}".encode(),
                )
            )
        if page < total_pages - 1:
            nav_id = generate_key_id(module_name, page + 1, "module_nav")
            kernel.cache.set(f"module_nav_{nav_id}", (module_name, page + 1), ttl=86400)
            nav_buttons.append(
                Button.inline(
                    t("btn_next"),
                    data=f"module_cfg_page_nav_{nav_id}".encode(),
                )
            )
        nav_buttons.append(
            Button.inline(t("btn_modules"), data="config_modules_page_0".encode())
        )
        if nav_buttons:
            buttons.append(nav_buttons)

        buttons.append([Button.inline("❌ Close", data=b"cfg_close", style="danger")])

        return buttons

    async def config_menu_handler(event):
        await ensure_config_initialized()
        text = t("config_menu_text", menu_emoji=emoji_provider["📋"])

        buttons = [
            [
                Button.inline(
                    t("btn_kernel_config"),
                    data=b"config_kernel_page_0",
                    style="primary",
                ),
                Button.inline(
                    t("btn_modules_config"),
                    data=b"config_modules_page_0",
                    style="primary",
                ),
            ],
            [Button.inline("❌ Close", data=b"cfg_close", style="danger")],
        ]
        thumb = InputWebDocument(
            url="https://kappa.lol/GaFZ9I",
            size=0,
            mime_type="image/jpeg",
            attributes=[DocumentAttributeImageSize(w=0, h=0)],
        )
        builder = event.builder.article(
            title="Config Menu",
            text=text,
            buttons=buttons,
            parse_mode="html",
            thumb=thumb,
        )
        await event.answer([builder])

    async def config_kernel_handler(event):
        await ensure_config_initialized()
        query = event.text.strip()
        visible_keys = get_visible_keys()
        total_keys = len(visible_keys)
        page = 0

        if query.startswith("config_kernel_"):
            try:
                parts = query.split("_")
                if len(parts) >= 4:
                    page_str = parts[3]
                    page = int(page_str)
            except:
                page = 0

        total_pages = (
            (total_keys + config_settings.items_per_page - 1)
            // config_settings.items_per_page
            if total_keys > 0
            else 1
        )
        if page < 0:
            page = 0
        if page >= total_pages:
            page = total_pages - 1

        start_idx = page * config_settings.items_per_page
        end_idx = start_idx + config_settings.items_per_page
        page_keys = visible_keys[start_idx:end_idx]

        text = t(
            "kernel_config_title",
            pencil=emoji_provider["✏️"],
            page_emoji=emoji_provider["📰"],
            page=page + 1,
            total_pages=total_pages,
            total_keys=total_keys,
        )

        buttons = create_kernel_buttons_grid(page_keys, page, total_pages)
        builder = event.builder.article(
            title=f"Kernel Config - {page + 1}",
            text=text,
            buttons=buttons,
            parse_mode="html",
        )
        await event.answer([builder])

    async def config_kernel_page(event, page):
        visible_keys = get_visible_keys()
        total_keys = len(visible_keys)
        total_pages = (
            (total_keys + config_settings.items_per_page - 1)
            // config_settings.items_per_page
            if total_keys > 0
            else 1
        )
        if page < 0:
            page = 0
        if page >= total_pages:
            page = total_pages - 1

        start_idx = page * config_settings.items_per_page
        end_idx = start_idx + config_settings.items_per_page
        page_keys = visible_keys[start_idx:end_idx]

        text = t(
            "kernel_config_title",
            pencil=emoji_provider["✏️"],
            page_emoji=emoji_provider["📰"],
            page=page + 1,
            total_pages=total_pages,
            total_keys=total_keys,
        )

        buttons = create_kernel_buttons_grid(page_keys, page, total_pages)
        try:
            await event.edit(text, buttons=buttons, parse_mode="html")
        except:
            pass

    async def config_modules_handler(event):
        await ensure_config_initialized()
        query = event.text.strip()
        all_modules = list(kernel.system_modules.keys()) + list(
            kernel.loaded_modules.keys()
        )
        all_modules = sorted(list(set(all_modules)))

        page = 0
        if query.startswith("config_modules_"):
            try:
                parts = query.split("_")
                if len(parts) >= 4:
                    page_str = parts[3]
                    page = int(page_str)
            except:
                page = 0

        total_modules = len(all_modules)
        total_pages = (
            (total_modules + config_settings.modules_per_page - 1)
            // config_settings.modules_per_page
            if total_modules > 0
            else 1
        )
        if page < 0:
            page = 0
        if page >= total_pages:
            page = total_pages - 1

        start_idx = page * config_settings.modules_per_page
        end_idx = start_idx + config_settings.modules_per_page
        page_modules = all_modules[start_idx:end_idx]

        text = t(
            "modules_config_title",
            puzzle=emoji_provider["🧩"],
            page_emoji=emoji_provider["📰"],
            page=page + 1,
            total_pages=total_pages,
            total_modules=total_modules,
        )

        buttons = create_modules_buttons_grid(page_modules, page, total_pages)
        thumb = InputWebDocument(
            url="https://kappa.lol/GaFZ9I",
            size=0,
            mime_type="image/jpeg",
            attributes=[DocumentAttributeImageSize(w=0, h=0)],
        )
        builder = event.builder.article(
            title=f"Modules Config - {page + 1}",
            text=text,
            buttons=buttons,
            parse_mode="html",
            thumb=thumb,
        )
        await event.answer([builder])

    async def show_module_config_view(event, module_name, page=0):
        try:
            module_config = await kernel.get_module_config(module_name, None)
            if module_config is None:
                await event.answer(t("no_config"), alert=True)
                return

            if is_module_config_like(module_config):
                items = list(module_config.items())
            elif isinstance(module_config, dict) and module_config.get(
                "__mcub_config__"
            ):
                items = [
                    (k, v) for k, v in module_config.items() if k != "__mcub_config__"
                ]
            else:
                # Old format - plain dict
                items = list(module_config.items())

            total_items = len(items)
            total_pages = (
                (total_items + config_settings.items_per_page - 1)
                // config_settings.items_per_page
                if total_items > 0
                else 1
            )

            if page < 0:
                page = 0
            if page >= total_pages:
                page = total_pages - 1

            start_idx = page * config_settings.items_per_page
            end_idx = start_idx + config_settings.items_per_page
            page_keys = items[start_idx:end_idx]

            text = t(
                "module_config_title",
                puzzle=emoji_provider["🧩"],
                module_name=module_name,
                page_emoji=emoji_provider["📰"],
                page=page + 1,
                total_pages=total_pages,
                total_items=total_items,
            )

            buttons = create_module_config_buttons(
                module_name, page_keys, page, total_pages
            )
            await event.edit(text, buttons=buttons, parse_mode="html")

        except Exception as e:
            await event.answer(t("error", error=str(e)[:50]), alert=True)

    async def show_module_key_view(event, module_name, key, page):
        try:
            module_config = await kernel.get_module_config(module_name, {})
            is_module_config = is_module_config_like(module_config)
            is_dict_config = isinstance(module_config, dict) and module_config.get(
                "__mcub_config__"
            )

            if is_module_config:
                if key not in module_config.keys():
                    await event.answer(t("not_found"), alert=True)
                    return
                value = module_config[key]
                config_value = module_config._values.get(key)
                is_hidden = config_value.hidden if config_value else False
                is_secret = (
                    hasattr(config_value.validator, "secret") if config_value else False
                )
            elif is_dict_config:
                if key not in module_config or key == "__mcub_config__":
                    await event.answer(t("not_found"), alert=True)
                    return
                value = module_config[key]
                is_hidden = False
                is_secret = False
                config_value = None
            else:
                # Old format - plain dict
                if key not in module_config:
                    await event.answer(t("not_found"), alert=True)
                    return
                value = module_config[key]
                is_hidden = False
                is_secret = False
                config_value = None

            # Even when stored config is a plain dict, the live ModuleConfig schema
            # (with description, choices, validators) lives in the module instance.
            # Try to get it from there so we can display metadata.
            if config_value is None:
                try:
                    live_cfg = getattr(kernel, "_live_module_configs", {}).get(
                        module_name
                    )
                    if live_cfg is None:
                        live_mod = kernel.loaded_modules.get(
                            module_name
                        ) or kernel.system_modules.get(module_name)
                        if live_mod is not None:
                            live_cfg = getattr(live_mod, "config", None)
                    if is_module_config_like(live_cfg):
                        config_value = live_cfg._values.get(key)
                        if config_value is not None:
                            is_hidden = is_hidden or config_value.hidden
                            is_secret = is_secret or hasattr(
                                config_value.validator, "secret"
                            )
                            # Also extract choices if available
                            if choices is None:
                                choices = getattr(
                                    config_value.validator, "choices", None
                                )
                except Exception:
                    pass

            value_type = type(value).__name__
            type_emoji = get_type_emoji(value_type)

            # Handle display based on hidden/secret status
            if is_hidden or is_secret:
                display_value = "<code>••••••••</code>"
            elif isinstance(value, (dict, list)):
                formatted_value = json.dumps(value, ensure_ascii=False, indent=2)
                display_value = f"<pre>{html.escape(formatted_value)}</pre>"
            elif value is None:
                if config_value is not None and config_value.default is not None:
                    default_str = str(config_value.default)
                    display_value = (
                        f"<code>{html.escape(default_str)}</code> <i>(default)</i>"
                    )
                else:
                    display_value = "<code>null</code>"
            elif isinstance(value, bool):
                display_value = (
                    "✔️ <code>true</code>" if value else "✖️ <code>false</code>"
                )
            elif isinstance(value, str):
                escaped_value = html.escape(value)
                display_value = f"<code>{escaped_value}</code>"
            else:
                display_value = f"<code>{html.escape(str(value))}</code>"

            text = t(
                "key_view",
                note=emoji_provider["📝"],
                key=key,
                type_emoji=type_emoji,
                value_type=value_type,
                display_value=display_value,
            )

            # Append ModuleConfig metadata if available (works for both live and dict-stored configs)
            choices = None
            # Final fallback - try to get choices from live config directly
            if choices is None:
                try:
                    live_cfg = getattr(kernel, "_live_module_configs", {}).get(
                        module_name
                    )
                    if live_cfg is None:
                        live_mod = kernel.loaded_modules.get(
                            module_name
                        ) or kernel.system_modules.get(module_name)
                        if live_mod is not None:
                            live_cfg = getattr(live_mod, "config", None)
                    if is_module_config_like(live_cfg):
                        cv = live_cfg._values.get(key)
                        if cv and hasattr(cv, "validator"):
                            choices = getattr(cv.validator, "choices", None)
                except Exception:
                    pass

            if config_value:
                validator = config_value.validator
                description = config_value.description
                if description:
                    text += f"\n\n{emoji_provider['📖']} <blockquote expandable><i>{html.escape(str(description))}</i></blockquote>"
                choices = getattr(validator, "choices", None)
                if choices:
                    choices_str = ", ".join(f"<code>{c}</code>" for c in choices)
                    text += f"\n{emoji_provider['📋']} <b>{t('cfg_choices')}</b>: {choices_str}"
                v_min = getattr(validator, "min", None)
                v_max = getattr(validator, "max", None)
                if v_min is not None or v_max is not None:
                    if v_min is not None and v_max is not None:
                        text += f"\n{emoji_provider['🔢']} <b>{t('cfg_range_both', min=v_min, max=v_max)}</b>"
                    elif v_min is not None:
                        text += f"\n{emoji_provider['🔢']} <b>{t('cfg_range_min', min=v_min)}</b>"
                    elif v_max is not None:
                        text += f"\n{emoji_provider['🔢']} <b>{t('cfg_range_max', max=v_max)}</b>"
                min_len = getattr(validator, "min_len", None)
                max_len = getattr(validator, "max_len", None)
                if min_len is not None or max_len is not None:
                    if min_len is not None and max_len is not None:
                        text += f"\n{emoji_provider['📝']} <b>{t('cfg_len_both', min=min_len, max=max_len)}</b>"
                    elif min_len is not None:
                        text += f"\n{emoji_provider['📝']} <b>{t('cfg_len_min', min=min_len)}</b>"
                    elif max_len is not None:
                        text += f"\n{emoji_provider['📝']} <b>{t('cfg_len_max', max=max_len)}</b>"
                if value_type == "bool":
                    text += f"\n{emoji_provider['☑️']} <b>{t('cfg_type_bool')}</b>"

            buttons = []

            # Bool toggle button
            if value_type == "bool":
                toggle_text = t("toggle_false") if value else t("toggle_true")
                toggle_style = "danger" if value else "success"
                bool_id = generate_key_id(f"{module_name}__{key}", page, "bool")
                kernel.cache.set(
                    f"module_bool_{bool_id}", (module_name, key, page), ttl=86400
                )
                buttons.append(
                    [
                        Button.inline(
                            toggle_text,
                            data=f"cfg_modules_bool_{bool_id}".encode(),
                            style=toggle_style,
                        )
                    ]
                )
            else:
                # Edit button for non-bool values (if not hidden/secret and no choices)
                if not is_hidden and not is_secret and not choices:
                    # Create key_id for inline editing
                    key_id = generate_key_id(
                        f"{module_name}__{key}", page, "module_cfg"
                    )
                    kernel.cache.set(
                        f"module_cfg_view_{key_id}", (module_name, key, page), ttl=86400
                    )

                    buttons.append(
                        [
                            Button.switch_inline(
                                text=t("btn_edit"),
                                query=f"fcfg module {module_name} set {key_id} ",
                                same_peer=True,
                                style="primary",
                            )
                        ]
                    )

            # Choice buttons - replace edit button with inline choice buttons
            if choices and not is_hidden and not is_secret:
                choice_id = generate_key_id(f"{module_name}__{key}", page, "choice")
                cache_key = f"module_choice_{choice_id}"
                kernel.cache.set(
                    cache_key,
                    (module_name, key, page, list(choices)),
                    ttl=86400,
                )
                choice_buttons = []
                row = []
                for i, choice in enumerate(choices):
                    is_selected = choice == value
                    btn_text = f"{'☑️' if is_selected else '🔘'} {choice}"
                    row.append(
                        Button.inline(
                            btn_text,
                            data=f"cfg_module_choice_{choice_id}-{i}".encode(),
                        )
                    )
                    if len(row) == 3:
                        choice_buttons.append(row)
                        row = []
                if row:
                    choice_buttons.append(row)
                for row in choice_buttons:
                    buttons.append(row)

            # List/Dict operation buttons
            if value_type == "list" and not is_hidden and not is_secret:
                key_id = generate_key_id(f"{module_name}__{key}", page, "module_cfg")
                kernel.cache.set(
                    f"module_cfg_view_{key_id}", (module_name, key, page), ttl=86400
                )

                buttons.append(
                    [
                        Button.switch_inline(
                            text=t("btn_list_add"),
                            query=f"fcfg module {module_name} list add {key_id} ",
                            same_peer=True,
                            style="success",
                        )
                    ]
                )
                buttons.append(
                    [
                        Button.switch_inline(
                            text=t("btn_list_del"),
                            query=f"fcfg module {module_name} list del {key_id}",
                            same_peer=True,
                            style="danger",
                        )
                    ]
                )
                buttons.append(
                    [
                        Button.switch_inline(
                            text=t("btn_list_set"),
                            query=f"fcfg module {module_name} list set {key_id} ",
                            same_peer=True,
                            style="primary",
                        )
                    ]
                )
            elif value_type == "dict" and not is_hidden and not is_secret:
                key_id = generate_key_id(f"{module_name}__{key}", page, "module_cfg")
                kernel.cache.set(
                    f"module_cfg_view_{key_id}", (module_name, key, page), ttl=86400
                )

                buttons.append(
                    [
                        Button.switch_inline(
                            text=t("btn_dict_add"),
                            query=f"fcfg module {module_name} dict add {key_id} ",
                            same_peer=True,
                            style="success",
                        )
                    ]
                )
                buttons.append(
                    [
                        Button.switch_inline(
                            text=t("btn_dict_del"),
                            query=f"fcfg module {module_name} dict del {key_id}",
                            same_peer=True,
                            style="danger",
                        )
                    ]
                )
                buttons.append(
                    [
                        Button.switch_inline(
                            text=t("btn_dict_set"),
                            query=f"fcfg module {module_name} dict set {key_id} ",
                            same_peer=True,
                            style="primary",
                        )
                    ]
                )

            # Reveal button for hidden/secret values
            if is_hidden or is_secret:
                key_id = generate_key_id(f"{module_name}__{key}", page, "module_cfg")
                kernel.cache.set(
                    f"module_cfg_view_{key_id}", (module_name, key, page), ttl=86400
                )
                buttons.append(
                    [
                        Button.inline(
                            t("btn_reveal"),
                            data=f"cfg_module_reveal_{key_id}".encode(),
                            style="primary",
                        )
                    ]
                )
                # Edit button for secret values (even when hidden)
                if is_secret and not is_hidden:
                    key_id = generate_key_id(
                        f"{module_name}__{key}", page, "module_cfg"
                    )
                    buttons.append(
                        [
                            Button.switch_inline(
                                text=t("btn_edit"),
                                query=f"fcfg module {module_name} set {key_id} ",
                                same_peer=True,
                                style="primary",
                            )
                        ]
                    )

            # Create key_id for refresh button
            key_id = generate_key_id(f"{module_name}__{key}", page, "module_cfg")
            kernel.cache.set(
                f"module_cfg_view_{key_id}", (module_name, key, page), ttl=86400
            )

            # Reset to default button - show if config_value exists and value differs from default
            if config_value is not None and hasattr(config_value, "default"):
                show_reset = (value is None and config_value.default is not None) or (
                    value is not None and value != config_value.default
                )
                if show_reset:
                    reset_id = generate_key_id(f"{module_name}__{key}", page, "reset")
                    kernel.cache.set(
                        f"module_cfg_reset_{reset_id}",
                        (module_name, key, page),
                        ttl=86400,
                    )
                    buttons.append(
                        [
                            Button.inline(
                                t("btn_reset_default"),
                                data=f"cfg_module_reset_{reset_id}".encode(),
                                style="danger",
                            )
                        ]
                    )

            # Navigation buttons
            back_nav_id = generate_key_id(module_name, page, "module_nav")
            kernel.cache.set(
                f"module_nav_{back_nav_id}", (module_name, page), ttl=86400
            )
            nav_buttons = [
                Button.inline(
                    t("btn_back_simple"),
                    data=f"module_cfg_page_nav_{back_nav_id}".encode(),
                ),
                Button.inline(
                    "🔄",
                    data=f"module_cfg_view_{key_id}".encode(),
                ),
            ]
            buttons.append(nav_buttons)

            buttons.append(
                [Button.inline("❌ Close", data=b"cfg_close", style="danger")]
            )

            await event.edit(text, buttons=buttons, parse_mode="html")

        except Exception as e:
            await event.answer(t("error", error=str(e)[:50]), alert=True)

    async def toggle_module_bool_key(event, module_name, key, page):
        try:
            module_config = await kernel.get_module_config(module_name, {})

            is_module_config = is_module_config_like(module_config)
            is_dict_config = isinstance(module_config, dict) and module_config.get(
                "__mcub_config__"
            )

            if is_module_config:
                if key not in module_config.keys():
                    await event.answer(t("not_found"), alert=True)
                    return
                value = module_config[key]
                if not isinstance(value, bool):
                    await event.answer(t("not_boolean"), alert=True)
                    return
                module_config[key] = not value
                await kernel.save_module_config(
                    module_name,
                    (
                        module_config.to_dict()
                        if hasattr(module_config, "to_dict")
                        else module_config
                    ),
                )
            elif is_dict_config:
                if key not in module_config or key == "__mcub_config__":
                    await event.answer(t("not_found"), alert=True)
                    return
                value = module_config[key]
                if not isinstance(value, bool):
                    await event.answer(t("not_boolean"), alert=True)
                    return
                module_config[key] = not value
                await kernel.save_module_config(module_name, module_config)
                add_module_to_config_cache(module_name)
            else:
                # Old format - plain dict
                if key not in module_config:
                    await event.answer(t("not_found"), alert=True)
                    return
                value = module_config[key]
                if not isinstance(value, bool):
                    await event.answer(t("not_boolean"), alert=True)
                    return
                module_config[key] = not value
                await kernel.save_module_config(module_name, module_config)
                add_module_to_config_cache(module_name)

            await show_module_key_view(event, module_name, key, page)
            module_config = await kernel.get_module_config(module_name, {})
            new_value = module_config[key]
            await event.answer(t("changed_to", value=new_value), alert=False)

        except Exception as e:
            await event.answer(t("error", error=str(e)[:50]), alert=True)

    async def generate_simple_set_article(
        event,
        key_id,
        key,
        value_str,
        scope="kernel",
        module_name=None,
        expected_type=None,
    ):
        try:
            user_id = getattr(event, "sender_id", None)
            if user_id is None and getattr(event, "sender", None):
                user_id = event.sender.id

            value = parse_value(value_str, expected_type)
            confirm_id = str(uuid.uuid4())[:8]

            cache_key = f"fcfg_confirm_{confirm_id}"
            kernel.cache.set(
                cache_key,
                {
                    "action": "set",
                    "scope": scope,
                    "module_name": module_name,
                    "cache_scope": (
                        "module_cfg_view" if scope == "module" else "cfg_view"
                    ),
                    "key_id": key_id,
                    "key": key,
                    "value": value,
                    "user_id": user_id,
                    "value_str": value_str[:50],
                },
                ttl=300,
            )

            scope_prefix = (
                f"[{module_name}] " if scope == "module" and module_name else ""
            )
            builder = event.builder.article(
                id=confirm_id,
                title=f"✅ Set: {scope_prefix}{key} = {value_str[:50]}",
                description=f"✅ Set: {scope_prefix}{key} = {value_str[:50]}",
                text=t("fcfg_confirm_text"),
                parse_mode="html",
            )

            await event.answer([builder])
        except Exception as e:
            await event.answer(
                [event.builder.article("Error", text=f"❌ Ошибка: {str(e)[:50]}")]
            )

    async def generate_add_articles(
        event,
        data_type,
        key_id,
        key,
        current_value,
        value_str,
        scope="kernel",
        module_name=None,
    ):
        try:
            user_id = getattr(event, "sender_id", None)
            if user_id is None and getattr(event, "sender", None):
                user_id = event.sender.id

            if data_type == "list":
                value = parse_value(value_str)
                confirm_id = str(uuid.uuid4())[:8]

                cache_key = f"fcfg_confirm_{confirm_id}"
                kernel.cache.set(
                    cache_key,
                    {
                        "action": "list_add",
                        "scope": scope,
                        "module_name": module_name,
                        "cache_scope": (
                            "module_cfg_view" if scope == "module" else "cfg_view"
                        ),
                        "key_id": key_id,
                        "key": key,
                        "value": value,
                        "user_id": user_id,
                        "value_str": value_str[:50],
                    },
                    ttl=300,
                )

                builder = event.builder.article(
                    id=confirm_id,
                    title=t("list_add_confirm", value=value_str[:50]),
                    description=t("list_add_confirm", value=value_str[:50]),
                    text=t("fcfg_confirm_text"),
                    parse_mode="html",
                )

                await event.answer([builder])

            elif data_type == "dict":
                subkey_parts = value_str.split(maxsplit=1)
                if len(subkey_parts) < 2:
                    await event.answer(
                        [
                            event.builder.article(
                                "Error",
                                text="❌ Укажите ключ и значение: fcfg dict add <key_id> <subkey> <value>",
                            )
                        ],
                    )
                    return

                subkey, dict_value_str = subkey_parts[0], subkey_parts[1]
                dict_value = parse_value(dict_value_str)

                confirm_id = str(uuid.uuid4())[:8]
                cache_key = f"fcfg_confirm_{confirm_id}"
                kernel.cache.set(
                    cache_key,
                    {
                        "action": "dict_add",
                        "scope": scope,
                        "module_name": module_name,
                        "cache_scope": (
                            "module_cfg_view" if scope == "module" else "cfg_view"
                        ),
                        "key_id": key_id,
                        "key": key,
                        "subkey": subkey,
                        "value": dict_value,
                        "user_id": user_id,
                        "value_str": f"{subkey}: {dict_value_str[:50]}",
                    },
                    ttl=300,
                )

                builder = event.builder.article(
                    id=confirm_id,
                    title=t("dict_add_confirm", key=subkey, value=dict_value_str[:30]),
                    description=t(
                        "dict_add_confirm", key=subkey, value=dict_value_str[:30]
                    ),
                    text=t("fcfg_confirm_text"),
                    parse_mode="html",
                )

                await event.answer([builder])

        except Exception as e:
            await event.answer(
                [event.builder.article("Error", text=f"❌ Ошибка: {str(e)[:50]}")]
            )

    async def generate_del_articles(
        event, data_type, key_id, key, current_value, scope="kernel", module_name=None
    ):
        builders = []
        user_id = getattr(event, "sender_id", None)
        if user_id is None and getattr(event, "sender", None):
            user_id = event.sender.id

        if data_type == "list":
            if not current_value:
                await event.answer(
                    [event.builder.article("Empty", text=t("list_empty"))]
                )
                return

            for index, item in enumerate(current_value):
                confirm_id = str(uuid.uuid4())[:8]
                cache_key = f"fcfg_confirm_{confirm_id}"

                kernel.cache.set(
                    cache_key,
                    {
                        "action": "list_del",
                        "scope": scope,
                        "module_name": module_name,
                        "cache_scope": (
                            "module_cfg_view" if scope == "module" else "cfg_view"
                        ),
                        "key_id": key_id,
                        "key": key,
                        "index": index,
                        "user_id": user_id,
                        "value_str": f"Индекс {index}: {str(item)[:30]}",
                    },
                    ttl=300,
                )

                builder = event.builder.article(
                    id=confirm_id,
                    title=t("list_remove_confirm", index=index, value=str(item)[:50]),
                    description=t(
                        "list_remove_confirm", index=index, value=str(item)[:50]
                    ),
                    text=t("fcfg_confirm_text"),
                    parse_mode="html",
                )
                builders.append(builder)

        elif data_type == "dict":
            if not current_value:
                await event.answer(
                    [event.builder.article("Empty", text=t("dict_empty"))]
                )
                return

            for subkey in current_value.keys():
                confirm_id = str(uuid.uuid4())[:8]
                cache_key = f"fcfg_confirm_{confirm_id}"

                kernel.cache.set(
                    cache_key,
                    {
                        "action": "dict_del",
                        "scope": scope,
                        "module_name": module_name,
                        "cache_scope": (
                            "module_cfg_view" if scope == "module" else "cfg_view"
                        ),
                        "key_id": key_id,
                        "key": key,
                        "subkey": subkey,
                        "user_id": user_id,
                        "value_str": f"Ключ: {subkey}",
                    },
                    ttl=300,
                )

                value = current_value[subkey]
                builder = event.builder.article(
                    id=confirm_id,
                    title=t("dict_remove_confirm", key=subkey),
                    description=f"Значение: {str(value)[:50]}...",
                    text=t("fcfg_confirm_text"),
                    parse_mode="html",
                )
                builders.append(builder)

        if builders:
            await event.answer(builders[:INLINE_RESULTS_LIMIT])
        else:
            await event.answer([event.builder.article("Empty", text=t("list_empty"))])

    async def generate_set_articles(
        event,
        data_type,
        key_id,
        key,
        current_value,
        value_str,
        scope="kernel",
        module_name=None,
    ):
        try:
            user_id = getattr(event, "sender_id", None)
            if user_id is None and getattr(event, "sender", None):
                user_id = event.sender.id

            new_value = parse_value(value_str)
            builders = []

            if data_type == "list":
                if not current_value:
                    await event.answer(
                        [event.builder.article("Empty", text=t("list_empty"))]
                    )
                    return

                for index, item in enumerate(current_value):
                    confirm_id = str(uuid.uuid4())[:8]
                    cache_key = f"fcfg_confirm_{confirm_id}"

                    kernel.cache.set(
                        cache_key,
                        {
                            "action": "list_set",
                            "scope": scope,
                            "module_name": module_name,
                            "cache_scope": (
                                "module_cfg_view" if scope == "module" else "cfg_view"
                            ),
                            "key_id": key_id,
                            "key": key,
                            "index": index,
                            "value": new_value,
                            "user_id": user_id,
                            "old_value": item,
                            "value_str": f"Заменить '{str(item)[:30]}' на '{value_str[:30]}'",
                        },
                        ttl=300,
                    )

                    builder = event.builder.article(
                        id=confirm_id,
                        title=t(
                            "list_set_confirm",
                            index=index,
                            old=str(item)[:30],
                            new=value_str[:30],
                        ),
                        description=t(
                            "list_set_confirm",
                            index=index,
                            old=str(item)[:30],
                            new=value_str[:30],
                        ),
                        text=t("fcfg_confirm_text"),
                        parse_mode="html",
                    )
                    builders.append(builder)

            elif data_type == "dict":
                if not current_value:
                    await event.answer(
                        [event.builder.article("Empty", text=t("dict_empty"))]
                    )
                    return

                for subkey in current_value.keys():
                    confirm_id = str(uuid.uuid4())[:8]
                    cache_key = f"fcfg_confirm_{confirm_id}"

                    old_value = current_value[subkey]
                    kernel.cache.set(
                        cache_key,
                        {
                            "action": "dict_set",
                            "scope": scope,
                            "module_name": module_name,
                            "cache_scope": (
                                "module_cfg_view" if scope == "module" else "cfg_view"
                            ),
                            "key_id": key_id,
                            "key": key,
                            "subkey": subkey,
                            "value": new_value,
                            "user_id": user_id,
                            "old_value": old_value,
                            "value_str": f"Ключ {subkey}: '{str(old_value)[:30]}' → '{value_str[:30]}'",
                        },
                        ttl=300,
                    )

                    builder = event.builder.article(
                        id=confirm_id,
                        title=t(
                            "dict_set_confirm",
                            key=subkey,
                            old=str(old_value)[:30],
                            new=value_str[:30],
                        ),
                        description=t(
                            "dict_set_confirm",
                            key=subkey,
                            old=str(old_value)[:30],
                            new=value_str[:30],
                        ),
                        text=t("fcfg_confirm_text"),
                        parse_mode="html",
                    )
                    builders.append(builder)

            if builders:
                await event.answer(builders[:INLINE_RESULTS_LIMIT])
            else:
                await event.answer(
                    [event.builder.article("Empty", text=t("list_empty"))]
                )

        except Exception as e:
            await event.answer(
                [event.builder.article("Error", text=f"❌ Ошибка: {str(e)[:50]}")]
            )

    async def chosen_result_handler(event):
        result_id = event.id
        user_id = event.user_id

        cache_key = f"fcfg_confirm_{result_id}"
        confirm_data = kernel.cache.get(cache_key)

        if not confirm_data:
            if hasattr(event, "answer"):
                await event.answer(t("fcfg_confirm_expired"), alert=True)
            return

        if confirm_data["user_id"] != user_id:
            kernel.logger.warning(
                f"FCFG confirm user mismatch: {user_id} != {confirm_data['user_id']}"
            )
            return

        action = confirm_data.get("action", "set")
        key = confirm_data["key"]
        scope = confirm_data.get("scope", "kernel")
        module_name = confirm_data.get("module_name")
        key_id = confirm_data.get("key_id")
        expected_scope = scope
        expected_module_name = module_name

        try:
            success = False
            message = ""

            module_cached = None
            kernel_cached = None

            # Hard routing by key_id cache mapping to avoid writing into wrong config.
            if key_id:
                module_cached = kernel.cache.get(f"module_cfg_view_{key_id}")
                kernel_cached = kernel.cache.get(f"cfg_view_{key_id}")

                if module_cached:
                    cached_module_name, cached_key, _ = module_cached
                    if cached_key != key:
                        raise ValueError("Module key mapping mismatch")
                    scope = "module"
                    module_name = cached_module_name
                elif kernel_cached:
                    cached_key, _, cached_type = kernel_cached
                    if cached_type != "kernel" or cached_key != key:
                        raise ValueError("Kernel key mapping mismatch")
                    scope = "kernel"
                else:
                    raise ValueError("Key mapping expired")

                # Strictly prevent cross-scope writes after confirmation
                if expected_scope == "module" and scope != "module":
                    raise ValueError(
                        "Refusing to write kernel config for module-scoped confirm"
                    )
                if expected_scope == "kernel" and scope != "kernel":
                    raise ValueError(
                        "Refusing to write module config for kernel-scoped confirm"
                    )
                if (
                    expected_scope == "module"
                    and expected_module_name
                    and module_name != expected_module_name
                ):
                    raise ValueError("Module mismatch in confirmation mapping")

            is_module_scope = scope == "module"
            target_config = kernel.config
            is_new_format = False

            if is_module_scope:
                if not module_name:
                    raise ValueError("Module name is not specified")
                target_config = await kernel.get_module_config(module_name, {})
                is_module_config = is_module_config_like(target_config)
                is_dict_config = isinstance(target_config, dict) and target_config.get(
                    "__mcub_config__"
                )

            def has_key(cfg_key):
                if is_module_scope and (is_module_config or is_dict_config):
                    if is_module_config:
                        return cfg_key in target_config.keys()
                    return cfg_key in target_config and cfg_key != "__mcub_config__"
                return cfg_key in target_config

            def get_value(cfg_key):
                return target_config[cfg_key]

            def set_value(cfg_key, cfg_value):
                target_config[cfg_key] = cfg_value

            if action == "set":
                value = confirm_data["value"]
                set_value(key, value)
                success = True
                message = t(
                    "fcfg_confirm_success", key=key, value=html.escape(str(value))
                )

            elif action == "list_add":
                value = confirm_data["value"]
                if has_key(key) and isinstance(get_value(key), list):
                    current_list = list(get_value(key))
                    current_list.append(value)
                    set_value(key, current_list)
                    success = True
                    message = t("list_add_confirm", value=html.escape(str(value)))
                else:
                    message = f"❌ Ключ {key} не является списком"

            elif action == "list_del":
                index = confirm_data["index"]
                if has_key(key) and isinstance(get_value(key), list):
                    current_list = list(get_value(key))
                    if 0 <= index < len(current_list):
                        removed = current_list.pop(index)
                        set_value(key, current_list)
                        success = True
                        message = t(
                            "list_remove_confirm",
                            index=index,
                            value=html.escape(str(removed)),
                        )
                    else:
                        message = f"❌ Индекс {index} вне диапазона"
                else:
                    message = f"❌ Ключ {key} не является списком"

            elif action == "list_set":
                index = confirm_data["index"]
                value = confirm_data["value"]
                if has_key(key) and isinstance(get_value(key), list):
                    current_list = list(get_value(key))
                    if 0 <= index < len(current_list):
                        old_value = current_list[index]
                        current_list[index] = value
                        set_value(key, current_list)
                        success = True
                        message = t(
                            "list_set_confirm",
                            index=index,
                            old=html.escape(str(old_value)),
                            new=html.escape(str(value)),
                        )
                    else:
                        message = f"❌ Индекс {index} вне диапазона"
                else:
                    message = f"❌ Ключ {key} не является списком"

            elif action == "dict_add":
                subkey = confirm_data["subkey"]
                value = confirm_data["value"]
                if has_key(key) and isinstance(get_value(key), dict):
                    current_dict = dict(get_value(key))
                    current_dict[subkey] = value
                    set_value(key, current_dict)
                    success = True
                    message = t(
                        "dict_add_confirm", key=subkey, value=html.escape(str(value))
                    )
                else:
                    message = f"❌ Ключ {key} не является словарем"

            elif action == "dict_del":
                subkey = confirm_data["subkey"]
                if has_key(key) and isinstance(get_value(key), dict):
                    current_dict = dict(get_value(key))
                    if subkey in current_dict:
                        current_dict.pop(subkey)
                        set_value(key, current_dict)
                        success = True
                        message = t("dict_remove_confirm", key=subkey)
                    else:
                        message = f"❌ Ключ {subkey} не найден в словаре"
                else:
                    message = f"❌ Ключ {key} не является словарем"

            elif action == "dict_set":
                subkey = confirm_data["subkey"]
                value = confirm_data["value"]
                if has_key(key) and isinstance(get_value(key), dict):
                    current_dict = dict(get_value(key))
                    if subkey in current_dict:
                        old_value = current_dict[subkey]
                        current_dict[subkey] = value
                        set_value(key, current_dict)
                        success = True
                        message = t(
                            "dict_set_confirm",
                            key=subkey,
                            old=html.escape(str(old_value)),
                            new=html.escape(str(value)),
                        )
                    else:
                        message = f"❌ Ключ {subkey} не найден в словаре"
                else:
                    message = f"❌ Ключ {key} не является словарем"

            if success:
                if is_module_scope:
                    if is_module_config:
                        await kernel.save_module_config(
                            module_name,
                            (
                                target_config.to_dict()
                                if hasattr(target_config, "to_dict")
                                else target_config
                            ),
                        )
                    else:
                        await kernel.save_module_config(module_name, target_config)
                    add_module_to_config_cache(module_name)
                    kernel.logger.info(
                        f"Module config updated via inline fcfg: {module_name}.{key} = {confirm_data.get('value', 'N/A')}"
                    )
                else:
                    await save_config()
                    kernel.logger.info(
                        f"Config updated via inline fcfg: {key} = {confirm_data.get('value', 'N/A')}"
                    )

                kernel.cache.set(cache_key, None, ttl=1)

                try:
                    if hasattr(event, "query") and hasattr(
                        event.query, "inline_message_id"
                    ):
                        inline_msg_id = event.query.inline_message_id

                        if is_module_scope:
                            if has_key(key):
                                new_text = format_key_value(
                                    key, get_value(key), reveal=True
                                )
                            else:
                                new_text = message
                        else:
                            if is_key_hidden(key):
                                new_text = t("value_inserted")
                            else:
                                new_text = format_key_value(
                                    key, kernel.config[key], reveal=True
                                )

                        if kernel.is_bot_available():
                            await kernel.bot_client.edit_message(
                                inline_message_id=inline_msg_id,
                                text=new_text,
                                parse_mode="html",
                            )

                except Exception as e:
                    kernel.logger.debug(f"Failed to edit inline message: {e}")

                if kernel.is_bot_available():
                    try:
                        await kernel.bot_client.send_message(
                            user_id, message, parse_mode="html"
                        )
                    except Exception as e:
                        kernel.logger.debug(f"Failed to send confirmation message: {e}")
            else:
                if kernel.is_bot_available():
                    try:
                        await kernel.bot_client.send_message(
                            user_id, message, parse_mode="html"
                        )
                    except Exception as e:
                        kernel.logger.debug(f"Failed to send error message: {e}")

        except Exception as e:
            kernel.logger.debug(f"FCFG confirm error: {e}")
            kernel.handle_error(e, source="FCFG:chosen_result_handler", event=event)

    async def fcfg_inline_handler(event):

        query = event.text.strip()
        parts = query.split()

        if len(parts) < 3:
            await event.answer(
                [event.builder.article("Usage", text=t("fcfg_inline_usage"))]
            )
            return

        module_mode = len(parts) >= 4 and parts[1].lower() == "module"
        module_name = parts[2] if module_mode else None

        if module_mode and len(parts) < 5:
            await event.answer(
                [event.builder.article("Usage", text=t("fcfg_inline_usage"))]
            )
            return

        action_type = parts[3].lower() if module_mode else parts[1].lower()

        async def resolve_target(key_id):
            if module_mode:
                cached = kernel.cache.get(f"module_cfg_view_{key_id}")
                if not cached:
                    await event.answer(
                        [],
                    )
                    return None, None, None

                cached_module_name, key, page = cached
                if cached_module_name != module_name:
                    await event.answer(
                        [
                            event.builder.article(
                                "Error", text=t("fcfg_inline_id_not_found")
                            )
                        ],
                    )
                    return None, None, None

                module_config = await kernel.get_module_config(module_name, {})
                is_new_format = is_module_config_like(module_config) or (
                    isinstance(module_config, dict)
                    and module_config.get("__mcub_config__")
                )

                if is_new_format:
                    if key not in module_config.keys():
                        await event.answer(
                            [event.builder.article("Not found", text=t("not_found"))]
                        )
                        return None, None, None
                    value = module_config[key]
                else:
                    if key not in module_config:
                        await event.answer(
                            [event.builder.article("Not found", text=t("not_found"))]
                        )
                        return None, None, None
                    value = module_config[key]

                return key, value, type(value).__name__

            cached = kernel.cache.get(f"cfg_view_{key_id}")
            if not cached:
                await event.answer(
                    [
                        event.builder.article(
                            "Not found", text=t("fcfg_inline_id_not_found")
                        )
                    ]
                )
                return None, None, None

            key, page, config_type = cached
            if config_type != "kernel":
                await event.answer(
                    [event.builder.article("Error", text=t("fcfg_inline_id_not_found"))]
                )
                return None, None, None

            if key in SENSITIVE_KEYS:
                await event.answer(
                    [
                        event.builder.article(
                            "Protected", text=t("fcfg_inline_protected")
                        )
                    ]
                )
                return None, None, None

            if key not in kernel.config:
                await event.answer(
                    [event.builder.article("Not found", text=t("not_found"))]
                )
                return None, None, None

            value = kernel.config[key]
            return key, value, type(value).__name__

        scope = "module" if module_mode else "kernel"

        if action_type == "set":
            if module_mode:
                parts_set = query.split(None, 5)
                if len(parts_set) < 6:
                    await event.answer(
                        [
                            event.builder.article(
                                "Usage", text="❌ Укажите key_id и значение"
                            )
                        ],
                    )
                    return
                key_id = parts_set[4]
                value_str = strip_formatting(parts_set[5])
            else:
                parts_set = query.split(None, 3)
                if len(parts_set) < 4:
                    await event.answer(
                        [
                            event.builder.article(
                                "Usage", text="❌ Укажите key_id и значение"
                            )
                        ],
                    )
                    return
                key_id = parts_set[2]
                value_str = strip_formatting(parts_set[3])

            key, current_value, current_type = await resolve_target(key_id)
            if key is None:
                return

            await generate_simple_set_article(
                event,
                key_id,
                key,
                value_str,
                scope=scope,
                module_name=module_name,
                expected_type=current_type,
            )

        elif action_type in ["list", "dict"]:
            data_type = action_type

            if module_mode:
                parts_op = query.split(None, 6)
                if len(parts_op) < 6:
                    await event.answer(
                        [event.builder.article("Usage", text=t("fcfg_inline_usage"))]
                    )
                    return
                action = parts_op[4].lower()
                key_id = parts_op[5]
                value_str = strip_formatting(parts_op[6]) if len(parts_op) > 6 else None
            else:
                parts_op = query.split(None, 4)
                if len(parts_op) < 4:
                    await event.answer(
                        [event.builder.article("Usage", text=t("fcfg_inline_usage"))]
                    )
                    return
                action = parts_op[2].lower()
                key_id = parts_op[3]
                value_str = strip_formatting(parts_op[4]) if len(parts_op) > 4 else None

            key, current_value, current_type = await resolve_target(key_id)
            if key is None:
                return

            if data_type == "list" and not isinstance(current_value, list):
                await event.answer(
                    [],
                )
                return
            if data_type == "dict" and not isinstance(current_value, dict):
                await event.answer(
                    [],
                )
                return

            if action == "add":
                if not value_str:
                    await event.answer(
                        [],
                    )
                    return
                await generate_add_articles(
                    event,
                    data_type,
                    key_id,
                    key,
                    current_value,
                    value_str,
                    scope=scope,
                    module_name=module_name,
                )

            elif action == "del":
                await generate_del_articles(
                    event,
                    data_type,
                    key_id,
                    key,
                    current_value,
                    scope=scope,
                    module_name=module_name,
                )

            elif action == "set":
                if not value_str:
                    await event.answer(
                        [],
                    )
                    return
                await generate_set_articles(
                    event,
                    data_type,
                    key_id,
                    key,
                    current_value,
                    value_str,
                    scope=scope,
                    module_name=module_name,
                )

            else:
                await event.answer(
                    [],
                )

        else:
            await event.answer(
                [],
            )

    async def config_callback_handler(event):
        data = event.data.decode()

        if data == "cfg_close":
            try:
                await kernel.client.delete_messages(event.chat_id, [event.message_id])
            except Exception as e:
                kernel.logger.debug(e)
                try:
                    await event.edit("❌ Closed")
                except Exception:
                    await event.answer("Closed", alert=False)
            return

        if data.startswith("cfg_module_reset_"):
            try:
                key_id = data[len("cfg_module_reset_") :]
                cached = kernel.cache.get(f"module_cfg_reset_{key_id}")
                if not cached:
                    await event.answer(t("expired"), alert=True)
                    return

                module_name, key, page = cached
                live_config = getattr(kernel, "_live_module_configs", {}).get(
                    module_name
                )
                if live_config is None:
                    live_mod = kernel.loaded_modules.get(
                        module_name
                    ) or kernel.system_modules.get(module_name)
                    if live_mod is not None:
                        live_config = getattr(live_mod, "config", None)

                if is_module_config_like(live_config):
                    config_value = live_config._values.get(key)
                    if config_value and hasattr(config_value, "default"):
                        default_val = config_value.default
                        live_config[key] = default_val
                        await kernel.save_module_config(
                            module_name, live_config.to_dict()
                        )
                        kernel.store_module_config_schema(module_name, live_config)
                        await show_module_key_view(event, module_name, key, page)
                        await event.answer(t("reset_success"), alert=True)
                    else:
                        await event.answer(t("no_default"), alert=True)
                else:
                    await event.answer(t("not_module_config"), alert=True)
            except Exception as e:
                await event.answer(t("error", error=str(e)[:50]), alert=True)
            return

        if data == "config_menu":
            text = t(
                "config_menu_text",
                menu_emoji='<tg-emoji emoji-id="5404451992456156919">🧬</tg-emoji>',
            )
            buttons = [
                [
                    Button.inline(
                        t("btn_kernel_config"),
                        data=b"config_kernel_page_0",
                        style="primary",
                    ),
                    Button.inline(
                        t("btn_modules_config"),
                        data=b"config_modules_page_0",
                        style="primary",
                    ),
                ],
                [Button.inline("❌ Close", data=b"cfg_close", style="danger")],
            ]
            try:
                await event.edit(text, buttons=buttons, parse_mode="html")
            except Exception as e:
                await event.answer(str(e)[:50], alert=True)

        elif data.startswith("config_kernel_page_"):
            try:
                page = int(data.split("_")[3])
                await config_kernel_page(event, page)
            except Exception as e:
                await event.answer(str(e)[:50], alert=True)

        elif data.startswith("config_modules_page_"):
            try:
                page = int(data.split("_")[3])
                all_modules = get_modules_with_config()

                total_modules = len(all_modules)
                total_pages = (
                    (total_modules + config_settings.modules_per_page - 1)
                    // config_settings.modules_per_page
                    if total_modules > 0
                    else 1
                )
                if page < 0:
                    page = 0
                if page >= total_pages:
                    page = total_pages - 1

                start_idx = page * config_settings.modules_per_page
                end_idx = start_idx + config_settings.modules_per_page
                page_modules = all_modules[start_idx:end_idx]

                text = t(
                    "modules_config_title",
                    puzzle=emoji_provider["🧩"],
                    page_emoji=emoji_provider["📰"],
                    page=page + 1,
                    total_pages=total_pages,
                    total_modules=total_modules,
                )
                buttons = create_modules_buttons_grid(page_modules, page, total_pages)
                await event.edit(text, buttons=buttons, parse_mode="html")
            except Exception as e:
                await event.answer(str(e)[:50], alert=True)

        elif data.startswith("module_select_"):
            try:
                key_id = data[14:]
                cached = kernel.cache.get(f"module_select_{key_id}")
                if not cached:
                    await event.answer(t("expired"), alert=True)
                    return

                module_name, page = cached
                await show_module_config_view(event, module_name, 0)
            except Exception as e:
                await event.answer(str(e)[:50], alert=True)

        elif data.startswith("module_cfg_page_"):
            try:
                if data.startswith("module_cfg_page_nav_"):
                    # New ID-based format — module_name encoded in cache
                    nav_id = data[20:]
                    cached = kernel.cache.get(f"module_nav_{nav_id}")
                    if not cached:
                        await event.answer(t("expired"), alert=True)
                        return
                    module_name, page = cached
                elif "__" in data:
                    # Legacy format: module_cfg_page_{module_name}__{page}
                    parts = data.split("__")
                    module_name = parts[0].replace("module_cfg_page_", "")
                    page = int(parts[1])
                else:
                    parts = data.split("_")
                    page_part = parts[-1]
                    if page_part.isdigit():
                        page = int(page_part)
                        module_name = "_".join(parts[3:-1])
                    else:
                        await event.answer(t("invalid_format"), alert=True)
                        return

                await show_module_config_view(event, module_name, page)
            except Exception as e:
                await event.answer(str(e)[:50], alert=True)

        elif data.startswith("module_cfg_view_"):
            try:
                key_id = data[16:]
                cached = kernel.cache.get(f"module_cfg_view_{key_id}")
                if not cached:
                    await event.answer(t("expired"), alert=True)
                    return

                module_name, key, page = cached
                await show_module_key_view(event, module_name, key, page)
            except Exception as e:
                await event.answer(str(e)[:50], alert=True)

        elif data.startswith("cfg_modules_bool_"):
            try:
                rest = data[17:]  # after "cfg_modules_bool_"
                # New ID-based format: rest is an 8-char hex ID with no "__"
                cached = kernel.cache.get(f"module_bool_{rest}")
                if cached:
                    module_name, key, page = cached
                elif "__" in rest:
                    # Legacy format: {module_name}__{key}__{page}
                    parts = rest.split("__")
                    if len(parts) >= 3:
                        module_name = parts[0]
                        key = parts[1]
                        page = int(parts[2])
                    else:
                        await event.answer(t("invalid_format"), alert=True)
                        return
                else:
                    await event.answer(t("expired"), alert=True)
                    return

                await toggle_module_bool_key(event, module_name, key, page)
            except Exception as e:
                await event.answer(str(e)[:50], alert=True)

        elif data.startswith("cfg_module_choice_"):
            try:
                kernel.logger.debug(f"DEBUG choice: data={data}")
                rest = data[17:]  # after "cfg_module_choice_"
                kernel.logger.debug(f"DEBUG choice: rest={rest}")
                idx = rest.rfind("-")
                kernel.logger.debug(f"DEBUG choice: idx={idx}")
                if idx == -1:
                    await event.answer(t("invalid_format"), alert=True)
                    return
                choice_id = rest[:idx]
                if choice_id.startswith("_"):
                    choice_id = choice_id[1:]
                choice_idx = int(rest[idx + 1 :])
                kernel.logger.debug(
                    f"DEBUG choice: choice_id={choice_id}, choice_idx={choice_idx}"
                )
                cached = kernel.cache.get(f"module_choice_{choice_id}")
                kernel.logger.debug(f"DEBUG choice: cached={cached is not None}")
                if not cached:
                    await event.answer(t("expired"), alert=True)
                    return
                module_name, key, page, choices = cached
                kernel.logger.debug(
                    f"Choice selected: {module_name}, {key}={choices[choice_idx]}, choices={choices}"
                )
                if choice_idx >= len(choices):
                    await event.answer(t("invalid_format"), alert=True)
                    return
                new_value = choices[choice_idx]
                module_config = await kernel.get_module_config(module_name, {})
                if isinstance(module_config, dict):
                    module_config[key] = new_value
                elif hasattr(module_config, "__setitem__"):
                    module_config[key] = new_value
                await kernel.save_module_config(
                    module_name,
                    (
                        module_config
                        if isinstance(module_config, dict)
                        else module_config.to_dict()
                    ),
                )
                await event.answer(t("changed_to", value=new_value), alert=False)
                await show_module_key_view(event, module_name, key, page)
            except Exception as e:
                import traceback

                kernel.logger.debug(f"Choice error: {e}\n{traceback.format_exc()}")
                await event.answer(str(e)[:50], alert=True)

        elif data.startswith("cfg_view_"):
            try:
                key_id = data[9:]
                result = await show_key_view(event, key_id, reveal=False)
                if result[0] is None:
                    return
                text, key, page, config_type, key_id = result

                if (
                    hasattr(event.query, "inline_message_id")
                    and event.query.inline_message_id
                ):
                    msg_manager.save_message(
                        inline_msg_id=event.query.inline_message_id,
                        chat_id=event.chat_id,
                        message_id=event.id,
                        key_id=key_id,
                        user_id=event.sender.id,
                    )

                buttons = []

                value = kernel.config.get(key)
                value_type = type(value).__name__ if value is not None else "NoneType"

                if value_type == "bool":
                    toggle_text = t("toggle_false") if value else t("toggle_true")
                    toggle_style = "danger" if value else "success"
                    toggle_style = "danger" if value else "success"
                    buttons.append(
                        [
                            Button.inline(
                                toggle_text,
                                data=f"cfg_bool_toggle_{key_id}".encode(),
                                style=toggle_style,
                            )
                        ]
                    )
                else:
                    if not is_key_hidden(key) or key not in SENSITIVE_KEYS:
                        buttons.append(
                            [
                                Button.switch_inline(
                                    text=t("btn_edit"),
                                    query=f"fcfg set {key_id} ",
                                    same_peer=True,
                                    style="primary",
                                )
                            ]
                        )

                if value_type == "list":
                    buttons.append(
                        [
                            Button.switch_inline(
                                text=t("btn_list_add"),
                                query=f"fcfg list add {key_id} ",
                                same_peer=True,
                                style="success",
                            )
                        ]
                    )
                    buttons.append(
                        [
                            Button.switch_inline(
                                text=t("btn_list_del"),
                                query=f"fcfg list del {key_id}",
                                same_peer=True,
                                style="danger",
                            )
                        ]
                    )
                    buttons.append(
                        [
                            Button.switch_inline(
                                text=t("btn_list_set"),
                                query=f"fcfg list set {key_id} ",
                                same_peer=True,
                                style="primary",
                            )
                        ]
                    )

                elif value_type == "dict":
                    buttons.append(
                        [
                            Button.switch_inline(
                                text=t("btn_dict_add"),
                                query=f"fcfg dict add {key_id} ",
                                same_peer=True,
                                style="success",
                            )
                        ]
                    )
                    buttons.append(
                        [
                            Button.switch_inline(
                                text=t("btn_dict_del"),
                                query=f"fcfg dict del {key_id}",
                                same_peer=True,
                                style="danger",
                            )
                        ]
                    )
                    buttons.append(
                        [
                            Button.switch_inline(
                                text=t("btn_dict_set"),
                                query=f"fcfg dict set {key_id} ",
                                same_peer=True,
                                style="primary",
                            )
                        ]
                    )

                if key not in SENSITIVE_KEYS:
                    buttons.append(
                        [
                            Button.inline(
                                t("btn_delete"),
                                data=f"cfg_delete_{key_id}".encode(),
                                style="danger",
                            )
                        ]
                    )

                if is_key_hidden(key) and key not in SENSITIVE_KEYS:
                    buttons.append(
                        [
                            Button.inline(
                                t("btn_reveal"),
                                data=f"cfg_reveal_{key_id}".encode(),
                                style="primary",
                            )
                        ]
                    )

                nav_buttons = [
                    Button.inline(
                        t("btn_back_simple"), data=f"config_kernel_page_{page}".encode()
                    ),
                    Button.inline("🔄", data=f"cfg_view_{key_id}".encode()),
                ]
                buttons.append(nav_buttons)

                buttons.append(
                    [Button.inline("❌ Close", data=b"cfg_close", style="danger")]
                )

                await event.edit(text, buttons=buttons, parse_mode="html")
            except Exception as e:
                await event.answer(str(e)[:50], alert=True)

        elif data.startswith("cfg_bool_toggle_"):
            try:
                key_id = data[16:]
                cached = kernel.cache.get(f"cfg_view_{key_id}")
                if not cached:
                    await event.answer(t("expired"), alert=True)
                    return

                key, page, config_type = cached
                if key not in kernel.config:
                    await event.answer(t("not_found"), alert=True)
                    return

                value = kernel.config[key]
                if not isinstance(value, bool):
                    await event.answer(t("not_boolean"), alert=True)
                    return

                kernel.config[key] = not value
                await save_config()

                result = await show_key_view(event, key_id, reveal=False)
                if result[0] is None:
                    return
                text, key, page, config_type, key_id = result

                new_value = kernel.config[key]
                toggle_text = t("toggle_false") if new_value else t("toggle_true")
                toggle_style = "danger" if new_value else "success"
                toggle_style = "danger" if new_value else "success"
                buttons = [
                    [
                        Button.inline(
                            toggle_text,
                            data=f"cfg_bool_toggle_{key_id}".encode(),
                            style=toggle_style,
                        )
                    ],
                    [
                        Button.inline(
                            t("btn_delete"),
                            data=f"cfg_delete_{key_id}".encode(),
                            style="danger",
                        )
                    ],
                    [
                        Button.inline(
                            t("btn_back_simple"),
                            data=f"config_kernel_page_{page}".encode(),
                        )
                    ],
                ]

                await event.edit(text, buttons=buttons, parse_mode="html")
                await event.answer(t("changed_to", value=new_value), alert=False)
            except Exception as e:
                await event.answer(str(e)[:50], alert=True)

        elif data.startswith("cfg_delete_"):
            try:
                key_id = data[11:]
                cached = kernel.cache.get(f"cfg_view_{key_id}")
                if not cached:
                    await event.answer(t("expired"), alert=True)
                    return

                key, page, config_type = cached

                if key in SENSITIVE_KEYS:
                    await event.answer(t("fcfg_inline_protected"), alert=True)
                    return

                if key in kernel.config:
                    kernel.config.pop(key)
                    await save_config()
                    await event.answer(t("key_deleted"), alert=True)

                    await config_kernel_page(event, page)
                else:
                    await event.answer(t("not_found"), alert=True)

            except Exception as e:
                await event.answer(str(e)[:50], alert=True)

        elif data.startswith("cfg_reveal_"):
            try:
                key_id = data[11:]
                # Show value without masking
                result = await show_key_view(event, key_id, reveal=True)
                if result[0] is None:
                    return
                text, key, page, config_type, key_id = result

                # Update cache
                kernel.cache.set(
                    f"cfg_view_{key_id}", (key, page, config_type), ttl=86400
                )

                value = kernel.config.get(key)
                value_type = type(value).__name__ if value is not None else "NoneType"

                buttons = []
                if value_type == "bool":
                    toggle_text = t("toggle_false") if value else t("toggle_true")
                    toggle_style = "danger" if value else "success"
                    toggle_style = "danger" if value else "success"
                    buttons.append(
                        [
                            Button.inline(
                                toggle_text, data=f"cfg_bool_toggle_{key_id}".encode()
                            )
                        ]
                    )
                elif not is_key_hidden(key) or key not in SENSITIVE_KEYS:
                    buttons.append(
                        [
                            Button.switch_inline(
                                t("btn_edit"),
                                query=f"fcfg set {key_id} ",
                                style="primary",
                            )
                        ]
                    )

                if value_type == "list":
                    buttons.append(
                        [
                            Button.switch_inline(
                                text=t("btn_list_add"),
                                query=f"fcfg list add {key_id} ",
                                same_peer=True,
                                style="success",
                            )
                        ]
                    )
                    buttons.append(
                        [
                            Button.switch_inline(
                                text=t("btn_list_del"),
                                query=f"fcfg list del {key_id}",
                                same_peer=True,
                                style="danger",
                            )
                        ]
                    )
                    buttons.append(
                        [
                            Button.switch_inline(
                                text=t("btn_list_set"),
                                query=f"fcfg list set {key_id} ",
                                same_peer=True,
                                style="primary",
                            )
                        ]
                    )

                elif value_type == "dict":
                    buttons.append(
                        [
                            Button.switch_inline(
                                text=t("btn_dict_add"),
                                query=f"fcfg dict add {key_id} ",
                                same_peer=True,
                                style="success",
                            )
                        ]
                    )
                    buttons.append(
                        [
                            Button.switch_inline(
                                text=t("btn_dict_del"),
                                query=f"fcfg dict del {key_id}",
                                same_peer=True,
                                style="danger",
                            )
                        ]
                    )
                    buttons.append(
                        [
                            Button.switch_inline(
                                text=t("btn_dict_set"),
                                query=f"fcfg dict set {key_id} ",
                                same_peer=True,
                                style="primary",
                            )
                        ]
                    )

                buttons.append(
                    [
                        Button.inline(
                            t("btn_delete"),
                            data=f"cfg_delete_{key_id}".encode(),
                            style="danger",
                        )
                    ]
                )

                nav_buttons = [
                    Button.inline(
                        t("btn_back_simple"), data=f"config_kernel_page_{page}".encode()
                    ),
                    Button.inline("🔄", data=f"cfg_reveal_{key_id}".encode()),
                ]
                buttons.append(nav_buttons)

                buttons.append(
                    [Button.inline("❌ Close", data=b"cfg_close", style="danger")]
                )

                await event.edit(text, buttons=buttons, parse_mode="html")
                await event.answer("👁️ Значение раскрыто", alert=False)

            except Exception as e:
                await event.answer(str(e)[:50], alert=True)

        elif data.startswith("cfg_module_reveal_"):
            try:
                key_id = data[18:]
                cached = kernel.cache.get(f"module_cfg_view_{key_id}")
                if not cached:
                    await event.answer(t("expired"), alert=True)
                    return

                module_name, key, page = cached
                module_config = await kernel.get_module_config(module_name, {})

                is_new_format = is_module_config_like(module_config) or (
                    isinstance(module_config, dict)
                    and module_config.get("__mcub_config__")
                )

                if is_new_format:
                    if key not in module_config.keys():
                        await event.answer(t("not_found"), alert=True)
                        return
                    value = module_config[key]
                else:
                    if key not in module_config:
                        await event.answer(t("not_found"), alert=True)
                        return
                    value = module_config[key]

                value_type = type(value).__name__
                type_emoji = get_type_emoji(value_type)

                # Show revealed value
                if isinstance(value, (dict, list)):
                    formatted_value = json.dumps(value, ensure_ascii=False, indent=2)
                    display_value = f"<pre>{html.escape(formatted_value)}</pre>"
                elif value is None:
                    display_value = "<code>null</code>"
                elif isinstance(value, bool):
                    display_value = (
                        "✔️ <code>true</code>" if value else "✖️ <code>false</code>"
                    )
                elif isinstance(value, str):
                    escaped_value = html.escape(value)
                    display_value = f"<code>{escaped_value}</code>"
                else:
                    display_value = f"<code>{html.escape(str(value))}</code>"

                text = t(
                    "key_view",
                    note=emoji_provider["📝"],
                    key=key,
                    type_emoji=type_emoji,
                    value_type=value_type,
                    display_value=display_value,
                )

                buttons = []

                # Bool toggle button
                if value_type == "bool":
                    toggle_text = t("toggle_false") if value else t("toggle_true")
                    toggle_style = "danger" if value else "success"
                    toggle_style = "danger" if value else "success"
                    buttons.append(
                        [
                            Button.inline(
                                toggle_text,
                                data=f"cfg_modules_bool_{module_name}__{key}__{page}".encode(),
                                style=toggle_style,
                            )
                        ]
                    )
                else:
                    # Edit button
                    buttons.append(
                        [
                            Button.switch_inline(
                                text=t("btn_edit"),
                                query=f"fcfg module {module_name} set {key_id} ",
                                same_peer=True,
                                style="primary",
                            )
                        ]
                    )

                # List/Dict operation buttons
                if value_type == "list":
                    buttons.append(
                        [
                            Button.switch_inline(
                                text=t("btn_list_add"),
                                query=f"fcfg module {module_name} list add {key_id} ",
                                same_peer=True,
                                style="success",
                            )
                        ]
                    )
                    buttons.append(
                        [
                            Button.switch_inline(
                                text=t("btn_list_del"),
                                query=f"fcfg module {module_name} list del {key_id}",
                                same_peer=True,
                                style="danger",
                            )
                        ]
                    )
                    buttons.append(
                        [
                            Button.switch_inline(
                                text=t("btn_list_set"),
                                query=f"fcfg module {module_name} list set {key_id} ",
                                same_peer=True,
                                style="primary",
                            )
                        ]
                    )
                elif value_type == "dict":
                    buttons.append(
                        [
                            Button.switch_inline(
                                text=t("btn_dict_add"),
                                query=f"fcfg module {module_name} dict add {key_id} ",
                                same_peer=True,
                                style="success",
                            )
                        ]
                    )
                    buttons.append(
                        [
                            Button.switch_inline(
                                text=t("btn_dict_del"),
                                query=f"fcfg module {module_name} dict del {key_id}",
                                same_peer=True,
                                style="danger",
                            )
                        ]
                    )
                    buttons.append(
                        [
                            Button.switch_inline(
                                text=t("btn_dict_set"),
                                query=f"fcfg module {module_name} dict set {key_id} ",
                                same_peer=True,
                                style="primary",
                            )
                        ]
                    )

                # Navigation buttons
                nav_buttons = [
                    Button.inline(
                        t("btn_back_simple"),
                        data=f"module_cfg_page_{module_name}__{page}".encode(),
                    ),
                    Button.inline(
                        "🔄",
                        data=f"cfg_module_reveal_{key_id}".encode(),
                    ),
                ]
                buttons.append(nav_buttons)

                buttons.append(
                    [Button.inline("❌ Close", data=b"cfg_close", style="danger")]
                )

                await event.edit(text, buttons=buttons, parse_mode="html")
                await event.answer("👁️ Значение раскрыто", alert=False)

            except Exception as e:
                await event.answer(str(e)[:50], alert=True)

    @kernel.register.command("cfg")
    # <subcommand/None> <key>
    async def cfg_handler(event):
        await ensure_config_initialized()
        try:
            args = event.text.split()
            if len(args) == 1:
                if hasattr(kernel, "bot_client"):
                    try:
                        success, _msg = await kernel.inline_query_and_click(
                            event.chat_id, "cfg"
                        )

                        if success:
                            await event.delete()
                    except:
                        await event.edit(
                            t("cfg_usage", gear=emoji_provider["⚙️"]),
                            parse_mode="html",
                        )

            elif len(args) == 2:
                key = args[1].strip()

                if is_key_hidden(key):
                    await event.edit(
                        t("hidden_key", briefcase=emoji_provider["💼"], key=key),
                        parse_mode="html",
                    )
                    return
                if key not in kernel.config:
                    await event.edit(
                        t("key_not_found", ballot=emoji_provider["🗳"], key=key),
                        parse_mode="html",
                    )
                    return

                value = kernel.config[key]
                value_type = type(value).__name__
                if isinstance(value, (dict, list)):
                    display_value = f"<pre>{html.escape(json.dumps(value, ensure_ascii=False, indent=2))}</pre>"
                elif isinstance(value, str):
                    escaped_value = html.escape(value)
                    display_value = f"<code>{escaped_value}</code>"
                else:
                    display_value = f"<code>{html.escape(str(value))}</code>"

                await event.edit(
                    t(
                        "key_view",
                        note=emoji_provider["📝"],
                        key=key,
                        type_emoji=get_type_emoji(value_type),
                        value_type=value_type,
                        display_value=display_value,
                    ),
                    parse_mode="html",
                )

            elif len(args) >= 3:
                subcommand = args[1].lower()
                key = args[2].strip()

                if subcommand == "now":
                    if is_key_hidden(key):
                        await event.edit(
                            t("hidden_key", briefcase=emoji_provider["💼"], key=key),
                            parse_mode="html",
                        )
                        return
                    if key not in kernel.config:
                        await event.edit(
                            t("key_not_found", ballot=emoji_provider["🗳"], key=key),
                            parse_mode="html",
                        )
                        return

                    value = kernel.config[key]
                    value_type = type(value).__name__
                    if isinstance(value, (dict, list)):
                        display_value = f"<pre>{html.escape(json.dumps(value, ensure_ascii=False, indent=2))}</pre>"
                    elif isinstance(value, str):
                        escaped_value = html.escape(value)
                        display_value = f"<code>{escaped_value}</code>"
                    else:
                        display_value = f"<code>{html.escape(str(value))}</code>"

                    await event.edit(
                        t(
                            "key_view",
                            note=emoji_provider["📝"],
                            key=key,
                            type_emoji=get_type_emoji(value_type),
                            value_type=value_type,
                            display_value=display_value,
                        ),
                        parse_mode="html",
                    )

                elif subcommand == "hide":
                    if key in SENSITIVE_KEYS:
                        await event.edit(
                            t("system_key", paperclip=emoji_provider["📎"]),
                            parse_mode="html",
                        )
                        return
                    hidden = kernel.config.get("hidden_keys", [])
                    if key not in hidden:
                        hidden.append(key)
                        kernel.config["hidden_keys"] = hidden
                        await save_config()
                    await event.edit(
                        t("hidden_key", briefcase=emoji_provider["💼"], key=key),
                        parse_mode="html",
                    )

                elif subcommand == "unhide":
                    hidden = kernel.config.get("hidden_keys", [])
                    if key in hidden:
                        hidden.remove(key)
                        kernel.config["hidden_keys"] = hidden
                        await save_config()
                    await event.edit(
                        t("visible_key", book=emoji_provider["📖"], key=key),
                        parse_mode="html",
                    )
                else:
                    # Unknown subcommand
                    await event.edit(
                        t("cfg_usage", gear=emoji_provider["⚙️"]),
                        parse_mode="html",
                    )
        except Exception as e:
            await kernel.handle_error(e, source="cfg", event=event)

    @kernel.register.command("fcfg")
    # <list/dict/set/add> <key/subkey> <key/None>
    async def fcfg_handler(event):
        await ensure_config_initialized()
        try:
            args = event.text.split()
            if len(args) < 2:
                await event.edit(
                    t("fcfg_usage", gear=emoji_provider["⚙️"]),
                    parse_mode="html",
                )
                return

            action = args[1].lower()

            module_mode = False
            module_name = None

            # Support for "fcfg module <module_name> <action>" format
            if action == "module":
                if len(args) < 4:
                    await event.edit(
                        t("fcfg_module_usage", cross=emoji_provider["❌"]),
                        parse_mode="html",
                    )
                    return
                module_mode = True
                module_name = args[2]
                # Shift args: module <module_name> set key val -> set key val
                args = [args[0]] + args[3:]
                action = args[1].lower() if len(args) > 1 else ""

            # Support for "-m module_name" flag (old format)
            if "-m" in args:
                module_mode = True
                m_index = args.index("-m")
                if len(args) <= m_index + 1:
                    await event.edit(
                        t("specify_module", cross=emoji_provider["❌"]),
                        parse_mode="html",
                    )
                    return
                module_name = args[m_index + 1]
                args = args[:m_index] + args[m_index + 2 :]

            def get_value_str_from_raw(key, n_prefix_args):
                """Получить value_str из исходного текста сообщения сохраняя переносы строк"""
                raw = event.text
                parts = raw.split(None, n_prefix_args)
                if len(parts) > n_prefix_args:
                    return strip_formatting(parts[n_prefix_args].strip())
                return ""

            if action == "set":
                if len(args) < 4:
                    await event.edit(
                        t("not_enough_args", cross=emoji_provider["❌"]),
                        parse_mode="html",
                    )
                    return

                key = args[2].strip()
                _raw = event.text
                _key_pos = _raw.find(key, _raw.find(args[1]))
                if _key_pos != -1:
                    _after_key = _raw[_key_pos + len(key) :].lstrip(" \t")
                    value_str = strip_formatting(_after_key.strip())
                else:
                    value_str = strip_formatting(" ".join(args[3:]).strip())

                if module_mode:
                    try:
                        module_config = await kernel.get_module_config(module_name, {})
                        is_new_format = is_module_config_like(module_config) or (
                            isinstance(module_config, dict)
                            and module_config.get("__mcub_config__")
                        )

                        if is_new_format:
                            # New format - use ModuleConfig with validation
                            if key not in module_config.keys():
                                current_type = None
                            else:
                                current_type = type(module_config[key]).__name__

                            value = parse_value(value_str, current_type)

                            try:
                                module_config[key] = value  # This will validate
                                await kernel.save_module_config(
                                    module_name,
                                    (
                                        module_config.to_dict()
                                        if hasattr(module_config, "to_dict")
                                        else module_config
                                    ),
                                )
                            except ValidationError as ve:
                                await event.edit(
                                    f"{emoji_provider['❌']} Validation error: {html.escape(str(ve))}",
                                    parse_mode="html",
                                )
                                return
                        else:
                            # Old format - plain dict
                            current_type = (
                                type(module_config.get(key)).__name__
                                if key in module_config
                                else None
                            )
                            value = parse_value(value_str, current_type)
                            module_config[key] = value
                            await kernel.save_module_config(module_name, module_config)
                            add_module_to_config_cache(module_name)

                        display_value = value
                        if isinstance(value, str):
                            display_value = value.replace("\n", "\\n")
                        await event.edit(
                            t(
                                "set_module_success",
                                check=emoji_provider["✅"],
                                module=module_name,
                                key=key,
                                value=html.escape(str(display_value)),
                            ),
                            parse_mode="html",
                        )
                    except Exception as e:
                        await event.edit(
                            f"{emoji_provider['❌']} {html.escape(str(e))}",
                            parse_mode="html",
                        )
                else:
                    if key in SENSITIVE_KEYS:
                        await event.edit(
                            t("protected_key", cross=emoji_provider["❌"]),
                            parse_mode="html",
                        )
                        return
                    try:
                        current_type = (
                            type(kernel.config.get(key)).__name__
                            if key in kernel.config
                            else None
                        )
                        value = parse_value(value_str, current_type)
                        kernel.config[key] = value
                        await save_config()
                        display_value = value
                        if isinstance(value, str):
                            display_value = value.replace("\n", "\\n")
                        await event.edit(
                            t(
                                "set_success",
                                check=emoji_provider["✅"],
                                key=key,
                                value=html.escape(str(display_value)),
                            ),
                            parse_mode="html",
                        )
                    except Exception as e:
                        await event.edit(
                            f"{emoji_provider['❌']} {html.escape(str(e))}",
                            parse_mode="html",
                        )

            elif action == "del":
                if len(args) < 3:
                    await event.edit(
                        t("not_enough_args", cross=emoji_provider["❌"]),
                        parse_mode="html",
                    )
                    return

                key = args[2].strip()

                if module_mode:
                    module_config = await kernel.get_module_config(module_name, {})
                    if key in module_config:
                        module_config.pop(key)
                        await kernel.save_module_config(module_name, module_config)
                        add_module_to_config_cache(module_name)
                        await event.edit(
                            t(
                                "delete_module_success",
                                ballot=emoji_provider["🗳"],
                                module=module_name,
                                key=key,
                            ),
                            parse_mode="html",
                        )
                    else:
                        await event.edit(
                            t("not_found_in_module", cross=emoji_provider["❌"]),
                            parse_mode="html",
                        )
                else:
                    if key in SENSITIVE_KEYS:
                        await event.edit(
                            t("protected_key", cross=emoji_provider["❌"]),
                            parse_mode="html",
                        )
                        return
                    if key in kernel.config:
                        kernel.config.pop(key)
                        if key in kernel.config.get("hidden_keys", []):
                            kernel.config["hidden_keys"].remove(key)
                        await save_config()
                        await event.edit(
                            t("delete_success", ballot=emoji_provider["🗳"], key=key),
                            parse_mode="html",
                        )
                    else:
                        await event.edit(
                            t("not_found", cross=emoji_provider["❌"]),
                            parse_mode="html",
                        )

            elif action == "add":
                if len(args) < 4:
                    await event.edit(
                        t("not_enough_args", cross=emoji_provider["❌"]),
                        parse_mode="html",
                    )
                    return

                key = args[2].strip()
                _raw = event.text
                _key_pos = _raw.find(key, _raw.find(args[1]))
                if _key_pos != -1:
                    _after_key = _raw[_key_pos + len(key) :].lstrip(" \t")
                    value_str = strip_formatting(_after_key.strip())
                else:
                    value_str = strip_formatting(" ".join(args[3:]).strip())

                if module_mode:
                    module_config = await kernel.get_module_config(module_name, {})
                    if key in module_config:
                        await event.edit(
                            t("key_exists", cross=emoji_provider["❌"]),
                            parse_mode="html",
                        )
                        return
                    try:
                        value = parse_value(value_str)
                        module_config[key] = value
                        await kernel.save_module_config(module_name, module_config)
                        add_module_to_config_cache(module_name)
                        await event.edit(
                            t(
                                "add_module_success",
                                check=emoji_provider["✅"],
                                module=module_name,
                                key=key,
                            ),
                            parse_mode="html",
                        )
                    except Exception as e:
                        await event.edit(
                            f"{emoji_provider['❌']} {html.escape(str(e))}",
                            parse_mode="html",
                        )
                else:
                    if key in kernel.config:
                        await event.edit(
                            t("key_exists", cross=emoji_provider["❌"]),
                            parse_mode="html",
                        )
                        return
                    try:
                        value = parse_value(value_str)
                        kernel.config[key] = value
                        await save_config()
                        await event.edit(
                            t("add_success", check=emoji_provider["✅"], key=key),
                            parse_mode="html",
                        )
                    except Exception as e:
                        await event.edit(
                            f"{emoji_provider['❌']} {html.escape(str(e))}",
                            parse_mode="html",
                        )

            elif action == "dict":
                if len(args) < 5:
                    await event.edit(
                        t("not_enough_args", cross=emoji_provider["❌"]),
                        parse_mode="html",
                    )
                    return

                key, subkey = args[2].strip(), args[3].strip()
                _raw = event.text
                _subkey_pos = _raw.find(subkey, _raw.find(key))
                if _subkey_pos != -1:
                    _after_subkey = _raw[_subkey_pos + len(subkey) :].lstrip(" \t")
                    value_str = strip_formatting(_after_subkey.strip())
                else:
                    value_str = strip_formatting(" ".join(args[4:]).strip())

                if module_mode:
                    try:
                        module_config = await kernel.get_module_config(module_name, {})

                        is_new_format = is_module_config_like(module_config) or (
                            isinstance(module_config, dict)
                            and module_config.get("__mcub_config__")
                        )

                        if is_new_format:
                            if key not in module_config.keys():
                                module_config._values[key] = ModuleConfig.ConfigValue(
                                    key, {}
                                )
                            current_value = module_config[key]
                            if not isinstance(current_value, dict):
                                await event.edit(
                                    t("not_dict", cross=emoji_provider["❌"]),
                                    parse_mode="html",
                                )
                                return
                            current_value[subkey] = parse_value(value_str)
                            module_config[key] = current_value
                            await kernel.save_module_config(
                                module_name,
                                (
                                    module_config.to_dict()
                                    if hasattr(module_config, "to_dict")
                                    else module_config
                                ),
                            )
                        else:
                            if key not in module_config:
                                module_config[key] = {}
                            if not isinstance(module_config[key], dict):
                                await event.edit(
                                    t("not_dict", cross=emoji_provider["❌"]),
                                    parse_mode="html",
                                )
                                return
                            module_config[key][subkey] = parse_value(value_str)
                            await kernel.save_module_config(module_name, module_config)
                            add_module_to_config_cache(module_name)

                        await event.edit(
                            t(
                                "dict_module_success",
                                check=emoji_provider["✅"],
                                module=module_name,
                                key=key,
                                subkey=subkey,
                            ),
                            parse_mode="html",
                        )
                    except Exception as e:
                        await event.edit(
                            f"{emoji_provider['❌']} {html.escape(str(e))}",
                            parse_mode="html",
                        )
                else:
                    try:
                        if key not in kernel.config:
                            kernel.config[key] = {}
                        if not isinstance(kernel.config[key], dict):
                            await event.edit(
                                t("not_dict", cross=emoji_provider["❌"]),
                                parse_mode="html",
                            )
                            return
                        kernel.config[key][subkey] = parse_value(value_str)
                        await save_config()
                        await event.edit(
                            t(
                                "dict_success",
                                check=emoji_provider["✅"],
                                key=key,
                                subkey=subkey,
                            ),
                            parse_mode="html",
                        )
                    except Exception as e:
                        await event.edit(
                            f"{emoji_provider['❌']} {html.escape(str(e))}",
                            parse_mode="html",
                        )

            elif action == "list":
                if len(args) < 4:
                    await event.edit(
                        t("not_enough_args", cross=emoji_provider["❌"]),
                        parse_mode="html",
                    )
                    return

                key = args[2].strip()
                _raw = event.text
                _key_pos2 = _raw.find(key, _raw.find(args[1]))
                if _key_pos2 != -1:
                    _after_key2 = _raw[_key_pos2 + len(key) :].lstrip(" \t")
                    value_str = strip_formatting(_after_key2.strip())
                else:
                    value_str = strip_formatting(" ".join(args[3:]).strip())

                if module_mode:
                    try:
                        module_config = await kernel.get_module_config(module_name, {})

                        is_new_format = is_module_config_like(module_config) or (
                            isinstance(module_config, dict)
                            and module_config.get("__mcub_config__")
                        )

                        if is_new_format:
                            if key not in module_config.keys():
                                from core.lib.module_config import ConfigValue

                                module_config._values[key] = ConfigValue(key, [])
                            current_value = module_config[key]
                            if not isinstance(current_value, list):
                                await event.edit(
                                    t("not_list", cross=emoji_provider["❌"]),
                                    parse_mode="html",
                                )
                                return
                            current_value.append(parse_value(value_str))
                            module_config[key] = current_value
                            await kernel.save_module_config(
                                module_name,
                                (
                                    module_config.to_dict()
                                    if hasattr(module_config, "to_dict")
                                    else module_config
                                ),
                            )
                        else:
                            if key not in module_config:
                                module_config[key] = []
                            if not isinstance(module_config[key], list):
                                await event.edit(
                                    t("not_list", cross=emoji_provider["❌"]),
                                    parse_mode="html",
                                )
                                return
                            module_config[key].append(parse_value(value_str))
                            await kernel.save_module_config(module_name, module_config)
                            add_module_to_config_cache(module_name)

                        await event.edit(
                            t(
                                "list_module_success",
                                check=emoji_provider["✅"],
                                module=module_name,
                                key=key,
                            ),
                            parse_mode="html",
                        )
                    except Exception as e:
                        await event.edit(
                            f"{emoji_provider['❌']} {html.escape(str(e))}",
                            parse_mode="html",
                        )
                else:
                    try:
                        if key not in kernel.config:
                            kernel.config[key] = []
                        if not isinstance(kernel.config[key], list):
                            await event.edit(
                                t("not_list", cross=emoji_provider["❌"]),
                                parse_mode="html",
                            )
                            return
                        kernel.config[key].append(parse_value(value_str))
                        await save_config()
                        await event.edit(
                            t("list_success", check=emoji_provider["✅"], key=key),
                            parse_mode="html",
                        )
                    except Exception as e:
                        await event.edit(
                            f"{emoji_provider['❌']} {html.escape(str(e))}",
                            parse_mode="html",
                        )

        except Exception as e:
            await kernel.handle_error(e, source="fcfg", event=event)

    kernel.register_inline_handler("cfg", config_menu_handler)
    kernel.register_inline_handler("config_kernel", config_kernel_handler)
    kernel.register_inline_handler("config_modules", config_modules_handler)
    kernel.register_inline_handler("fcfg", fcfg_inline_handler)

    kernel.register_callback_handler("config_menu", config_callback_handler)
    kernel.register_callback_handler("config_kernel_page_", config_callback_handler)
    kernel.register_callback_handler("config_modules_page_", config_callback_handler)
    kernel.register_callback_handler("module_select_", config_callback_handler)
    kernel.register_callback_handler("module_cfg_page_", config_callback_handler)
    kernel.register_callback_handler("module_cfg_view_", config_callback_handler)
    kernel.register_callback_handler("cfg_modules_bool_", config_callback_handler)
    kernel.register_callback_handler("cfg_view_", config_callback_handler)
    kernel.register_callback_handler("cfg_bool_toggle_", config_callback_handler)
    kernel.register_callback_handler("cfg_delete_", config_callback_handler)
    kernel.register_callback_handler("cfg_reveal_", config_callback_handler)
    kernel.register_callback_handler("cfg_module_reveal_", config_callback_handler)
    kernel.register_callback_handler("cfg_module_choice_", config_callback_handler)
    kernel.register_callback_handler("cfg_module_reset_", config_callback_handler)
    kernel.register_callback_handler("cfg_close", config_callback_handler)

    if hasattr(kernel, "bot_client") and kernel.bot_client:

        @kernel.bot_client.on(events.Raw(types.UpdateBotInlineSend))
        async def handle_chosen_result(event):
            await chosen_result_handler(event)
