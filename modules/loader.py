from __future__ import annotations

# author: @Hairpin00
# version: 1.1.5
# description: loader modules
import asyncio
import html
import inspect
import logging
import os
import random
import re
import subprocess
import sys
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Callable

import aiohttp
from telethon import Button
from telethon.types import InputMediaWebPage

if TYPE_CHECKING:
    from telethon import types

from core.lib.loader.module_config import (
    ModuleConfig,
    ConfigValue,
    Boolean,
)

try:
    from core.lib.loader.hikka_compat import (
        is_hikka_module,
        load_hikka_module,
        unload_hikka_module,
    )

    HIKKA_COMPAT = True
except ImportError:
    HIKKA_COMPAT = False
    _OLD_MCUB_COMPAT = False

    def is_hikka_module(code):
        from core.lib.loader.hikka_compat.fake_package import (
            is_hikka_module as _is_hikka,
        )

        return _is_hikka(code)

    async def load_hikka_module(kernel, path, name):
        return False, "hikka_compat not found"

    async def unload_hikka_module(kernel, name):
        return False


async def safe_edit(msg, *args, **kwargs):
    """Edit message, ignoring MessageNotModifiedError."""
    try:
        return await msg.edit(*args, **kwargs)
    except Exception as e:
        if "Content of the message was not modified" in str(e):
            return msg
        raise


logger = logging.getLogger("mcub.loader")

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Custom emoji
CUSTOM_EMOJI = {
    "loading": '<tg-emoji emoji-id="5893368370530621889">🔜</tg-emoji>',
    "dependencies": '<tg-emoji emoji-id="5328311576736833844">🟠</tg-emoji>',
    "confused": '<tg-emoji emoji-id="5249119354825487565">🫨</tg-emoji>',
    "error": '<tg-emoji emoji-id="5370843963559254781">😖</tg-emoji>',
    "file": '<tg-emoji emoji-id="5269353173390225894">💾</tg-emoji>',
    "process": '<tg-emoji emoji-id="5426958067763804056">⏳</tg-emoji>',
    "blocked": '<tg-emoji emoji-id="5431895003821513760">🚫</tg-emoji>',
    "warning": '<tg-emoji emoji-id="5409235172979672859">⚠️</tg-emoji>',
    "stone": '<tg-emoji emoji-id="4904687665158292410">🗿</tg-emoji>',
    "idea": '<tg-emoji emoji-id="5411134407517964108">💡</tg-emoji>',
    "success": '<tg-emoji emoji-id="5118861066981344121">✅</tg-emoji>',
    "test": '<tg-emoji emoji-id="5134183530313548836">🧪</tg-emoji>',
    "crystal": '<tg-emoji emoji-id="5368585403467048206">🪬</tg-emoji>',
    "sparkle": '<tg-emoji emoji-id="5426900601101374618">🪩</tg-emoji>',
    "folder": '<tg-emoji emoji-id="5217444336089714383">📂</tg-emoji>',
    "upload": '<tg-emoji emoji-id="5253526631221307799">📤</tg-emoji>',
    "shield": '<tg-emoji emoji-id="5253671358734281000">🛡</tg-emoji>',
    "angel": '<tg-emoji emoji-id="5404521025465518254">😇</tg-emoji>',
    "nerd": '<tg-emoji emoji-id="5465154440287757794">🤓</tg-emoji>',
    "cloud": '<tg-emoji emoji-id="5370947515220761242">🌩</tg-emoji>',
    "reload": '<tg-emoji emoji-id="5893368370530621889">🔜</tg-emoji>',
    "convert": '<tg-emoji emoji-id="5332600281970517875">🔄</tg-emoji>',
    "download": '<tg-emoji emoji-id="5469785308386041323">⬇️</tg-emoji>',
    "no_cmd": '<tg-emoji emoji-id="5429428837895141860">🫨</tg-emoji>',
    "author": '<tg-emoji emoji-id="5332630862137685609">💖</tg-emoji>',
    "lib": '<tg-emoji emoji-id="5359785904535774578">💼</tg-emoji>',
    "wait": '<tg-emoji emoji-id="5326015457155620929">🧳</tg-emoji>',
    "link": '<tg-emoji emoji-id="5411527152212411235">🔗</tg-emoji>',
}

# Random completion emojis
RANDOM_EMOJIS = [
    "ಠ_ಠ",
    "( ཀ ʖ̯ ཀ)",
    "(◕‿◕✿)",
    "(つ･･)つ",
    "༼つ◕_◕༽つ",
    "(•_•)",
    "☜(ﾟヮﾟ☜)",
    "(☞ﾟヮﾟ)☞",
    "ʕ•ᴥ•ʔ",
    "(づ￣ ³￣)づ",
]

try:
    from core.kernel import CommandConflictError
except ImportError:

    class CommandConflictError(Exception):
        def __init__(self, message, conflict_type=None, command=None):
            super().__init__(message)
            self.conflict_type = conflict_type
            self.command = command


def register(kernel):
    kernel.logger.debug("[LoaderModule] register start")
    client = kernel.client
    language = kernel.config.get("language", "en")
    kernel.logger.debug(f"[LoaderModule] register language={language}")

    config = ModuleConfig(
        ConfigValue(
            "loader_protect_system",
            True,
            description="Protect system modules from being overwritten",
            validator=Boolean(default=True),
        ),
        ConfigValue(
            "loader_show_banners",
            True,
            description="Show module banners in loaded modules list",
            validator=Boolean(default=True),
        ),
        ConfigValue(
            "loader_allow_hikka_modules",
            True,
            description="Allow loading Hikka/Heroku compatible modules",
            validator=Boolean(default=True),
        ),
    )

    def get_config():
        live_cfg = getattr(kernel, "_live_module_configs", {}).get(__name__)
        if live_cfg:
            return live_cfg
        return config

    async def startup():
        config_dict = await kernel.get_module_config(
            __name__,
            {
                "loader_protect_system": True,
                "loader_show_banners": True,
                "loader_allow_hikka_modules": True,
            },
        )
        config.from_dict(config_dict)
        kernel.store_module_config_schema(__name__, config)
        config_dict_clean = {k: v for k, v in config.to_dict().items() if v is not None}
        if config_dict_clean:
            await kernel.save_module_config(__name__, config_dict_clean)

    asyncio.create_task(startup())

    def allow_hikka_modules() -> bool:
        cfg = get_config()
        if cfg is None:
            return True
        return cfg.get("loader_allow_hikka_modules", True)

    # Localized strings
    strings = {
        "en": {
            "wait": "{wait} <b>Please wait...</b>",
            "reply_to_py": "{warning} <b>Reply to a .py file</b>",
            "not_py_file": "{warning} <b>This is not a .py file</b>",
            "system_module_update_attempt": "{confused} <b>Oops, looks like you tried to update a system module</b> <code>{module_name}</code>\n<blockquote><i>{blocked} Unfortunately, you cannot update system modules using <code>loadera</code></i></blockquote>",
            "system_module_unload_attempt": "{confused} <b>Oops, looks like you tried to unload a system module</b> <code>{module_name}</code>\n<blockquote><i>{blocked} Unfortunately, you cannot unload system modules</i></blockquote>",
            "starting_install": "{action} <b>modules</b>",
            "installing": "{test} <b>Installing</b>",
            "updating": "{reload} <b>Updating</b>",
            "updating_version": "{reload} <b>Updating to v</b><code>{old_version}</code> <b>→ v</b><code>{new_version}</code>",
            "log_start": "=- Starting {action} module {module_name}",
            "log_filename": "=> File name: {filename}",
            "log_downloading": "=- Downloading file to {file_path}",
            "log_downloaded": "=> File downloaded successfully",
            "log_file_read": "=> File read",
            "log_checking_compatibility": "=- Checking module compatibility...",
            "log_incompatible": "=X Module incompatible (Heroku/Hikka type)",
            "log_compatible": "=> Module compatible",
            "log_getting_metadata": "Getting module metadata...",
            "log_author": "Author: {author}",
            "log_version": "Version: {version}",
            "log_description": "Description: {description}",
            "log_checking_deps": "=- Checking dependencies...",
            "log_deps_found": "=> Found dependencies: {deps}",
            "installing_deps": "{dependencies} <b>installing dependencies:</b>\n<blockquote expandable><code>{deps_list}</code></blockquote>",
            "log_installing_dep": "=- Installing dependency: {dep}",
            "log_dep_installed": "=> Dependency {dep} installed successfully",
            "log_dep_error": "=X Error installing {dep}: {error}",
            "log_removing_old": "=- Removing old module commands {module_name}",
            "log_loading_module": "=- Loading module {module_name}...",
            "log_module_loaded": "=> Module loaded successfully",
            "log_commands_found": "=> Commands found: {count}",
            "module_loaded": "{success} <b>Module {module_name} loaded!</b> {emoji}\n<blockquote expandable>{idea} <i>D: {description}</i> | V: <code>{version}</code></blockquote>\n<blockquote expandable>{commands_list}</blockquote>\n<blockquote>{emoji_author} Author: {author}</blockquote>\n{source_link}",
            "module_loaded_no_cmds": "{success} <b>Module {module_name} loaded!</b> {emoji}\n<blockquote>{idea} <i>D: {description}</i> | V: <code>{version}</code></blockquote>\n<blockquote>{emoji_author} Author: {author}</blockquote>\n{source_link}",
            "no_cmd_desc": "{no_cmd} Command has no description",
            "command_line": "{crystal} <code>{prefix}{cmd}</code> – <b>{desc}</b>",
            "aliases_text": " (Aliases: {alias_text})",
            "log_aliases_found": "Command {cmd} has aliases: {aliases}",
            "log_install_error": "=X Module loading error: {error}",
            "install_failed": "<b>{blocked} Looks like the installation failed</b>\n<b>{idea} Install Log:</b>\n<pre>{log}</pre>",
            "log_conflict": "✗ Command conflict: {error}",
            "conflict_system": "{shield} <b>System command conflict!</b>\n<blockquote>Command <code>{prefix}{command}</code> already registered by system module.</blockquote>\n<b>Install Log:</b>\n<pre>{log}</pre>",
            "conflict_user": "{error} <b>Module command conflict!</b>\n<blockquote>Command <code>{prefix}{command}</code> already registered by module <code>{owner_module}</code>.</blockquote>\n<b>Install Log:</b>\n<pre>{log}</pre>",
            "log_critical": "=X Critical error: {error}",
            "log_traceback": "Traceback:\n{traceback}",
            "dlm_usage": "{warning} <b>Usage:</b> <code>{prefix}dlm [-send/-s/-list] module_name or URL</code>",
            "dlm_list_loading": "{loading} <b>Getting module list...</b>",
            "dlm_list_title": "{folder} <b>Module list from repositories:</b>\n<blockquote expandable>{list}</blockquote>",
            "dlm_list_errors": "\n\n{warning} <b>Errors:</b>\n<blockquote expandable>{errors}</blockquote>",
            "dlm_list_failed": "{warning} <b>Failed to get module list</b>",
            "dlm_searching": "{loading} <b>Searching for module {module_name}...</b>",
            "module_info": "{file} <b>Module:</b> <code>{module_name}</code>\n{idea} <b>Description:</b> <i>{description}</i>\n{crystal} <b>Version:</b> <code>{version}</code>\n{angel} <b>Author:</b> <i>{author}</i>\n{folder} <b>Size:</b> <code>{size} bytes</code>\n{cloud} <b>Repository:</b> <code>{repo}</code>",
            "module_not_found": "{warning} <b>Module {module_name} not found in any repository</b>",
            "dlm_send_usage": "{warning} <b>Usage:</b> <code>{prefix}dlm -send module_name or URL</code>",
            "system_module_install_attempt": "{confused} <b>Oops, looks like you tried to install a system module</b> <code>{module_name}</code>\n<blockquote><i>{blocked} System modules cannot be installed via <code>dlm</code></i></blockquote>",
            "downloading_module": "{download} downloading",
            "log_mode": "=+ Mode: {mode}",
            "log_type": "=+ Type: {type}",
            "log_download_url": "=- Downloading module from URL: {url}",
            "log_download_success": "=> ✓ Module downloaded successfully (status: {status})",
            "log_download_failed": "=X Download error (status: {status})",
            "url_download_error": "{warning} <b>Failed to download module from URL</b> (status: {status})",
            "log_download_exception": "=X Download error: {error}",
            "url_exception": "{warning} <b>Download error:</b> {error}",
            "log_checking_repos": "=- Checking repositories ({count} items)",
            "log_using_repo": "=- Using specified repository: {repo}",
            "log_found_in_repo": "=> Module found in specified repository",
            "log_not_found_in_repo": "=X Module not found in specified repository",
            "log_checking_repo": "=- Checking repository {index}: {repo}",
            "log_repo_error": "=X Error checking repository {repo}: {error}",
            "module_not_found_repos": "{warning} <b>Module<code> {module_name} </code>not found in repositories</b>",
            "log_saving_for_send": "Saving file for sending",
            "sending_module": "{upload} <b>Sending module {module_name}...</b>",
            "file_sent_caption": "<blockquote expandable>{file} <b>Module:</b> <code>{module_name}.py</code>\n{idea} <b>description:</b> <i>{description}</i>\n{crystal} <b>version:</b> <code>{version}</code>\n{angel} <b>author:</b> <i>{author}</i>\n{folder} <b>Size:</b> <code>{size} bytes</code></blockquote>",
            "log_file_sent": "=> File sent, deleting temp file",
            "log_install_mode": "=- Installation mode, continuing...",
            "log_saving_file": "=- Saving module file: {file_path}",
            "log_loading_to_kernel": "=- Loading module to kernel",
            "log_module_loaded_kernel": "=> Module loaded successfully to kernel",
            "conflict_system_alt": "{shield} <b>Oops, this module tried to overwrite a system command</b> (<code>{command}</code>)\n<blockquote><i>This is not an error but a <b>precaution</b></i></blockquote>\n<b>Install Log:</b>\n<pre>{log}</pre>",
            "conflict_user_alt": "{error} <b>Oops, looks like a module conflict occurred</b> <i>(their commands)</i>\n<blockquote><i>Conflict details in logs 🔭</i></blockquote>\n<b>Install Log:</b>\n<pre>{log}</pre>",
            "log_deleting_due_conflict": "=> Deleting module file due to conflict",
            "log_deleting_due_error": "=> Deleting module file due to error",
            "um_usage": "{warning} <b>Usage:</b> <code>{prefix}um module_name</code>",
            "module_not_found_um": "{warning} <b>Module {module_name} not found</b>",
            "module_unloaded": "{success} <b>Module {module_name} unloaded</b>",
            "unlm_usage": "{warning} <b>Usage:</b> <code>{prefix}unlm module_name</code>",
            "module_file_not_found": "{warning} <b>Module file not found</b>",
            "uploading_module": "{upload} <b>Uploading module {module_name}...</b>",
            "file_upload_caption": "{file} <b>Module:</b> {module_name}.py\n\n<blockquote><code>{prefix}im</code> to install</blockquote>\n{source_link}",
            "reload_usage": "{warning} <b>Usage:</b> <code>{prefix}reload module_name</code>",
            "reloading": "{reload} <b>Reloading <code>{module_name}</code>...</b>",
            "reload_success": "{success} <b>Module {module_name} reloaded!</b> {emoji}\n\n<blockquote expandable>{cmd_text}</blockquote>",
            "no_commands": "No commands",
            "reload_error": "{warning} <b>Error, check logs</b>",
            "no_modules": "{folder} <b>No modules loaded</b>",
            "loaded_modules": "{crystal} <b>Loaded modules:</b>\n\n",
            "system_modules": "{shield} <b>System modules:</b>\n",
            "user_modules": "{sparkle} <b>User modules:</b>\n",
            "module_line": "• <b>{name}</b> <i>({count} commands)</i>\n",
            "addrepo_usage": "{warning} <b>Usage:</b> <code>{prefix}addrepo URL</code>",
            "delrepo_usage": "{warning} <b>Usage:</b> <code>{prefix}delrepo index</code>",
            "catalog_title": "<b>🌩️ Official MCUB Repository</b> <code>{repo_url}</code>\n\n",
            "catalog_custom": "<i>{repo_name}</i> <code>{repo_url}</code>\n\n",
            "no_modules_catalog": "📭 No modules",
            "catalog_page": "📄 Page {page}/{total_pages}",
            "catalog_error": "❌ Catalog loading error: {error}",
            "dlm_repo_choice_title": "{cloud} <b>Module</b> <code>{module_name}</code> <b>found in multiple repositories</b>\n<blockquote>Choose where to {action}</blockquote>",
            "dlm_repo_choice_action_install": "install it",
            "dlm_repo_choice_action_send": "download it",
            "dlm_repo_choice_repo": "{index}. {repo_name}",
            "dlm_repo_choice_expired": "⚠️ Repository selection expired",
            "dlm_repo_choice_cancel": "Cancel",
            "dlm_repo_choice_cancelled": "Selection cancelled",
            "btn_back": "Back",
            "btn_next": "Next",
            "modules_not_mcub": "{warning} Module is not {mcub} type, [Heroku/Hikka]",
            "log_hikka_detected": "=+ Hikka/Heroku module detected — loading via compat layer",
            "hikka_no_compat": "{warning} <b>Hikka compat, not found.</b>",
            "hikka_disabled": "{warning} <b>Hikka/Heroku modules support is disabled via loader config (loader_allow_hikka_modules).</b>",
            "reload_all": "{reload} <b>Reloading all modules...</b>",
            "reload_all_success": "{success} <b>All modules reloaded!</b>\n<blockquote>{count}</blockquote>",
            "reload_all_success_one": "{success} <b>All modules reloaded!</b>\n{count} (<code>{name}</code>)",
            "reload_all_failed": "{warning} <b>Failed to reload {count} module(s):</b>\n<blockquote expandable>{failed_list}</blockquote>",
            "reload_all_partial": "{success} <b>Modules reloaded!</b>\n{success_count}\n{warning} <b>Failed: {failed_count}</b>\n<blockquote expandable>{failed_list}</blockquote>",
            "failed_module": "• <code>{name}</code>\n",
            "and_more": "• <code>+{count} more</code>",
        },
        "ru": {
            "wait": "{wait} <b>Пожалуйста подождите...</b>",
            "reply_to_py": "{warning} <b>Ответьте на .py файл</b>",
            "not_py_file": "{warning} <b>Это не .py файл</b>",
            "system_module_update_attempt": "{confused} <b>Ой, кажется ты попытался обновить системный модуль</b> <code>{module_name}</code>\n<blockquote><i>{blocked} К сожалению нельзя обновлять системные модули с помощью <code>loadera</code></i></blockquote>",
            "system_module_unload_attempt": "{confused} <b>Ой, кажется ты попытался выгрузить системный модуль</b> <code>{module_name}</code>\n<blockquote><i>{blocked} К сожалению нельзя выгружать системные модули</i></blockquote>",
            "starting_install": "{action} <b>модуль</b>",
            "installing": "{test} <b>Устанавливаю</b>",
            "updating": "{reload} <b>Oбновляю</b>",
            "updating_version": "{reload} <b>Oбновляю до v</b><code>{old_version}</code> <b>→ v</b><code>{new_version}</code>",
            "log_start": "=- Начинаю {action} модуля {module_name}",
            "log_filename": "=> Имя файла: {filename}",
            "log_downloading": "=- Скачиваю файл в {file_path}",
            "log_downloaded": "=> Файл успешно скачан",
            "log_file_read": "=> Файл прочитан",
            "log_checking_compatibility": "=- Проверяю совместимость модуля...",
            "log_incompatible": "=X Модуль не совместим (Heroku/Hikka тип)",
            "log_compatible": "=> Модуль совместим",
            "log_getting_metadata": "Получаю метаданные модуля...",
            "log_author": "Автор: {author}",
            "log_version": "Версия: {version}",
            "log_description": "Описание: {description}",
            "log_checking_deps": "=- Проверяю зависимости...",
            "log_deps_found": "=> Найдены зависимости: {deps}",
            "installing_deps": "{dependencies} <b>ставлю зависимости:</b>\n<blockquote expandable><code>{deps_list}</code></blockquote>",
            "log_installing_dep": "=- Устанавливаю зависимость: {dep}",
            "log_dep_installed": "=> Зависимость {dep} установлена успешно",
            "log_dep_error": "=X Ошибка установки {dep}: {error}",
            "log_removing_old": "=- Удаляю старые команды модуля {module_name}",
            "log_loading_module": "=- Загружаю модуль {module_name}...",
            "log_module_loaded": "=> Модуль успешно загружен",
            "log_commands_found": "=> Найдено команд: {count}",
            "module_loaded": "{success} <b>Модуль {module_name} загружен!</b> {emoji}\n<blockquote expandable>{idea} <i>D: {description}</i> | V: <code>{version}</code></blockquote>\n<blockquote expandable>{commands_list}</blockquote>\n<blockquote>{emoji_author} Author: {author}</blockquote>\n{source_link}",
            "module_loaded_no_cmds": "{success} <b>Модуль {module_name} загружен!</b> {emoji}\n<blockquote>{idea} <i>D: {description}</i> | V: <code>{version}</code></blockquote>\n<blockquote>{emoji_author} Author: {author}</blockquote>\n{source_link}",
            "no_cmd_desc": "{no_cmd} У команды нету описания",
            "command_line": "{crystal} <code>{prefix}{cmd}</code> – <b>{desc}</b>",
            "aliases_text": " (Aliases: {alias_text})",
            "log_aliases_found": "Команда {cmd} имеет алиасы: {aliases}",
            "log_install_error": "=X Ошибка загрузки модуля: {error}",
            "install_failed": "<b>{blocked} Кажется установка прошла неудачно</b>\n<b>{idea} Install Log:</b>\n<pre>{log}</pre>",
            "log_conflict": "✗ Конфликт команд: {error}",
            "conflict_system": "{shield} <b>Конфликт системной команды!</b>\n<blockquote>Команда <code>{prefix}{command}</code> уже зарегистрирована системным модулем.</blockquote>\n<b>Install Log:</b>\n<pre>{log}</pre>",
            "conflict_user": "{error} <b>Конфликт команд модулей!</b>\n<blockquote>Команда <code>{prefix}{command}</code> уже зарегистрирована модулем <code>{owner_module}</code>.</blockquote>\n<b>Install Log</b>\n<pre>{log}</pre>",
            "log_critical": "=X Критическая ошибка: {error}",
            "log_traceback": "Трейсбэк:\n{traceback}",
            "dlm_usage": "{warning} <b>Использование:</b> <code>{prefix}dlm [-send/-s/-list] название_модуля или ссылка</code>",
            "dlm_list_loading": "{loading} <b>Получаю список модулей...</b>",
            "dlm_list_title": "{folder} <b>Список модулей из репозиториев:</b>\n<blockquote expandable>{list}</blockquote>",
            "dlm_list_errors": "\n\n{warning} <b>Ошибки:</b>\n<blockquote expandable>{errors}</blockquote>",
            "dlm_list_failed": "{warning} <b>Не удалось получить список модулей</b>",
            "dlm_searching": "{loading} <b>Ищу модуль {module_name}...</b>",
            "module_info": "{file} <b>Модуль:</b> <code>{module_name}</code>\n{idea} <b>Описание:</b> <i>{description}</i>\n{crystal} <b>Версия:</b> <code>{version}</code>\n{angel} <b>Автор:</b> <i>{author}</i>\n{folder} <b>Размер:</b> <code>{size} байт</code>\n{cloud} <b>Репозиторий:</b> <code>{repo}</code>",
            "module_not_found": "{warning} <b>Модуль {module_name} не найден ни в одном репозитории</b>",
            "dlm_send_usage": "{warning} <b>Использование:</b> <code>{prefix}dlm -send название_модуля или ссылка</code>",
            "system_module_install_attempt": "{confused} <b>Ой, кажется ты попытался установить системный модуль</b> <code>{module_name}</code>\n<blockquote><i>{blocked} Системные модули нельзя устанавливать через <code>dlm</code></i></blockquote>",
            "downloading_module": "{download} скачиваю",
            "log_mode": "=+ Режим: {mode}",
            "log_type": "=+ Тип: {type}",
            "log_download_url": "=- Скачиваю модуль по URL: {url}",
            "log_download_success": "=> ✓ Модуль скачан успешно (статус: {status})",
            "log_download_failed": "=X Ошибка скачивания (статус: {status})",
            "url_download_error": "{warning} <b>Не удалось скачать модуль по ссылке</b> (статус: {status})",
            "log_download_exception": "=X Ошибка скачивания: {error}",
            "url_exception": "{warning} <b>Ошибка скачивания:</b> {error}",
            "log_checking_repos": "=- Проверяю репозитории ({count} шт.)",
            "log_using_repo": "=- Использую указанный репозиторий: {repo}",
            "log_found_in_repo": "=> Модуль найден в указанном репозитории",
            "log_not_found_in_repo": "=X Модуль не найден в указанном репозитории",
            "log_checking_repo": "=- Проверяю репозиторий {index}: {repo}",
            "log_repo_error": "=X Ошибка проверки репозитория {repo}: {error}",
            "module_not_found_repos": "{warning} <b>Модуль<code> {module_name} </code>не найден в репозиториях</b>",
            "log_saving_for_send": "Сохраняю файл для отправки",
            "sending_module": "{upload} <b>Отправляю модуль {module_name}...</b>",
            "file_sent_caption": "<blockquote expandable>{file} <b>Модуль:</b> <code>{module_name}.py</code>\n{idea} <b>описание:</b> <i>{description}</i>\n{crystal} <b>версия:</b> <code>{version}</code>\n{angel} <b>автор:</b> <i>{author}</i>\n{folder} <b>Размер:</b> <code>{size} байт</code></blockquote>",
            "log_file_sent": "=> Файл отправлен, удаляю временный файл",
            "log_install_mode": "=- Режим установки, продолжаю...",
            "log_saving_file": "=- Сохраняю файл модуля: {file_path}",
            "log_loading_to_kernel": "=- Загружаю модуль в ядро",
            "log_module_loaded_kernel": "=> Модуль успешно загружен в ядро",
            "conflict_system_alt": "{shield} <b>Ой, этот модуль хотел перезаписать системную команду</b> (<code>{command}</code>)\n<blockquote><i>Это не ошибка а мера <b>предосторожности</b></i></blockquote>\n<b>Лог установки:</b>\n<pre>{log}</pre>",
            "conflict_user_alt": "{error} <b>Ой, кажется случился конфликт модулей</b> <i>(их команд)</i>\n<blockquote><i>Детали конфликта в логах 🔭</i></blockquote>\n<b>Лог установки:</b>\n<pre>{log}</pre>",
            "log_deleting_due_conflict": "=> Удаляю файл модуля из-за конфликта",
            "log_deleting_due_error": "=> Удаляю файл модуля из-за ошибки",
            "um_usage": "{warning} <b>Использование:</b> <code>{prefix}um название_модуля</code>",
            "module_not_found_um": "{warning} <b>Модуль {module_name} не найден</b>",
            "module_unloaded": "{success} <b>Модуль {module_name} удален</b>",
            "unlm_usage": "{warning} <b>Использование:</b> <code>{prefix}unlm название_модуля</code>",
            "module_file_not_found": "{warning} <b>Файл модуля не найден</b>",
            "uploading_module": "{upload} <b>Отправка модуля {module_name}...</b>",
            "file_upload_caption": "{file} <b>Модуль:</b> {module_name}.py\n\n<blockquote><code>{prefix}im</code> для установки</blockquote>\n{source_link}",
            "reload_usage": "{warning} <b>Использование:</b> <code>{prefix}reload название_модуля</code>",
            "reloading": "{reload} <b>Перезагрузка <code>{module_name}</code>...</b>",
            "reload_success": "{success} <b>Модуль {module_name} перезагружен!</b> {emoji}\n\n<blockquote expandable>{cmd_text}</blockquote>",
            "no_commands": "Нет команд",
            "reload_error": "{warning} <b>Ошибка, смотри логи</b>",
            "no_modules": "{folder} <b>Модули не загружены</b>",
            "loaded_modules": "{crystal} <b>Загруженные модули:</b>\n\n",
            "system_modules": "{shield} <b>Системные модули:</b>\n",
            "user_modules": "{sparkle} <b>Пользовательские модули:</b>\n",
            "module_line": "• <b>{name}</b> <i>({count} команд)</i>\n",
            "addrepo_usage": "{warning} <b>Использование:</b> <code>{prefix}addrepo URL</code>",
            "delrepo_usage": "{warning} <b>Использование:</b> <code>{prefix}delrepo индекс</code>",
            "catalog_title": "<b>🌩️ Официальный репозиторий MCUB</b> <code>{repo_url}</code>\n\n",
            "catalog_custom": "<i>{repo_name}</i> <code>{repo_url}</code>\n\n",
            "no_modules_catalog": "📭 Нет модулей",
            "catalog_page": "📄 Страница {page}/{total_pages}",
            "catalog_error": "❌ Ошибка загрузки каталога: {error}",
            "dlm_repo_choice_title": "{cloud} <b>Модуль</b> <code>{module_name}</code> <b>найден в нескольких репозиториях</b>\n<blockquote>Выбери, откуда {action}</blockquote>",
            "dlm_repo_choice_action_install": "установить его",
            "dlm_repo_choice_action_send": "скачать его",
            "dlm_repo_choice_repo": "{index}. {repo_name}",
            "dlm_repo_choice_expired": "⚠️ Выбор репозитория устарел",
            "dlm_repo_choice_cancel": "Отмена",
            "dlm_repo_choice_cancelled": "Выбор отменён",
            "btn_back": "Назад",
            "btn_next": "Вперёд",
            "modules_not_mcub": "{warning} Модуль не {mcub} типа <i>[Heroku/Hikka]</i>",
            "log_hikka_detected": "=+ Обнаружен Hikka/Heroku модуль",
            "hikka_no_compat": "{warning} <b>Hikka compat не найден.</b>",
            "hikka_disabled": "{warning} <b>Поддержка Hikka/Heroku модулей отключена через конфиг loader (loader_allow_hikka_modules).</b>",
            "reload_all": "{reload} <b>Перезагружаю все модули...</b>",
            "reload_all_success": "{success} <b>Все модули перезагружены!</b>\n<blockquote>{count}</blockquote>",
            "reload_all_success_one": "{success} <b>Все модули перезагружены!</b>\n{count} (<code>{name}</code>)",
            "reload_all_failed": "{warning} <b>Не удалось перезагрузить {count} модуль(ей):</b>\n<blockquote expandable>{failed_list}</blockquote>",
            "reload_all_partial": "{success} <b>Модули перезагружены!</b>\n{success_count}\n{warning} <b>Не удалось: {failed_count}</b>\n<blockquote expandable>{failed_list}</blockquote>",
            "failed_module": "• <code>{name}</code>\n",
            "and_more": "• <code>+{count} ещё</code>",
        },
    }

    # Get strings for current language
    lang_strings = strings.get(language, strings["en"])

    def t(key: str, **kwargs: str) -> str:
        """Возвращает локализованную строку с подстановкой значений"""
        if key not in lang_strings:
            return key
        return lang_strings[key].format(**kwargs)

    async def mcub_handler() -> str:
        me = await kernel.client.get_me()
        mcub_emoji = (
            '<tg-emoji emoji-id="5470015630302287916">🔮</tg-emoji><tg-emoji emoji-id="5469945764069280010">🔮</tg-emoji><tg-emoji emoji-id="5469943045354984820">🔮</tg-emoji><tg-emoji emoji-id="5469879466954098867">🔮</tg-emoji>'
            if me.premium
            else "MCUB"
        )
        return mcub_emoji

    async def log_to_bot(text: str) -> None:
        if hasattr(kernel, "_log") and kernel._log:
            await kernel._log.log_module(text)
        elif hasattr(kernel, "send_log_message"):
            await kernel.send_log_message(f"{CUSTOM_EMOJI['crystal']} {text}")

    async def edit_with_emoji(
        message: types.Message,
        text: str,
        parse_mode: str = "html",
        **kwargs,
    ) -> bool:
        try:
            await message.edit(text, parse_mode=parse_mode, **kwargs)
            return True
        except Exception:
            return False

    async def send_with_emoji(
        chat_id: int | str,
        text: str,
        **kwargs,
    ) -> types.Message:
        try:
            if "<emoji" in text:
                text = text.replace("<emoji document_id=", "<tg-emoji emoji-id=")
                text = text.replace("</emoji>", "</tg-emoji>")
            if "<tg-emoji" in text or re.search(r"<[^>]+>", text):
                parse_mode = kwargs.pop("parse_mode", "html")
                return await client.send_message(
                    chat_id, text, parse_mode=parse_mode, **kwargs
                )
            else:
                return await client.send_message(chat_id, text, **kwargs)
        except Exception as e:
            await kernel.handle_error(e, source="send_with_emoji")
            fallback_text = re.sub(r"<tg-emoji[^>]*>.*?</tg-emoji>", "", text)
            fallback_text = re.sub(r"<emoji[^>]*>.*?</emoji>", "", fallback_text)
            fallback_text = re.sub(r"<[^>]+>", "", fallback_text)
            return await client.send_message(chat_id, fallback_text, **kwargs)

    async def load_module_from_file(
        file_path: str,
        module_name: str,
        is_system: bool = False,
    ) -> tuple[bool, str] | None:
        try:
            return await kernel.load_module_from_file(file_path, module_name, is_system)
        except CommandConflictError as e:
            raise e
        except Exception as e:
            kernel.logger.error(f"Ошибка загрузки модуля {module_name}: {e}")
            return False, f"Ошибка загрузки: {str(e)}"

    def detect_module_type(module: object) -> str:
        register = getattr(module, "register", None)
        if register is None:
            return "none"

        try:
            params = list(inspect.signature(register).parameters.keys())
        except (TypeError, ValueError):
            return "unknown"

        if len(params) == 0:
            return "unknown"
        if len(params) == 1:
            param_name = params[0]
            if param_name == "kernel":
                return "new"
            if param_name == "client":
                return "old"
        return "unknown"

    async def handle_catalog(
        event: types.Message,
        query_or_data: str,
    ) -> tuple[str, list[list[Button]]]:
        try:
            parts = query_or_data.split("_")

            repo_index = 0
            page = 1

            if len(parts) >= 2 and parts[1].isdigit():
                repo_index = int(parts[1])

            if len(parts) >= 3 and parts[2].isdigit():
                page = int(parts[2])

            repos = [kernel.default_repo] + kernel.repositories

            if repo_index < 0 or repo_index >= len(repos):
                repo_index = 0

            repo_url = repos[repo_index]
            cache_key = f"catalog:{repo_url}"
            cached = kernel.cache.get(cache_key)

            if cached is not None:
                modules, repo_name = cached
            else:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(f"{repo_url}/modules.ini") as resp:
                            if resp.status == 200:
                                modules_text = await resp.text()
                                modules = [
                                    line.strip()
                                    for line in modules_text.split("\n")
                                    if line.strip()
                                ]
                            else:
                                modules = []

                        async with session.get(f"{repo_url}/name.ini") as resp:
                            if resp.status == 200:
                                repo_name = await resp.text()
                                repo_name = repo_name.strip()
                            else:
                                repo_name = (
                                    repo_url.split("/")[-2]
                                    if "/" in repo_url
                                    else repo_url
                                )

                        kernel.cache.set(cache_key, (modules, repo_name), ttl=300)
                except Exception:
                    modules = []
                    repo_name = repo_url.split("/")[-2] if "/" in repo_url else repo_url

            per_page = 8
            total_pages = (len(modules) + per_page - 1) // per_page if modules else 1

            if page < 1:
                page = 1
            if page > total_pages:
                page = total_pages

            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            page_modules = modules[start_idx:end_idx] if modules else []

            if repo_index == 0:
                msg = t("catalog_title", repo_url=repo_url)
            else:
                msg = t("catalog_custom", repo_name=repo_name, repo_url=repo_url)

            if page_modules:
                modules_text = " | ".join([f"<code>{m}</code>" for m in page_modules])
                msg += modules_text
            else:
                msg += t("no_modules_catalog")

            msg += f"\n\n{t('catalog_page', page=page, total_pages=total_pages)}"

            buttons = []
            nav_buttons = []

            if page > 1:
                nav_buttons.append(
                    Button.inline(
                        t("btn_back"),
                        f"catalog_{repo_index}_{page - 1}".encode(),
                        style="primary",
                    )
                )

            if page < total_pages:
                nav_buttons.append(
                    Button.inline(
                        t("btn_next"),
                        f"catalog_{repo_index}_{page + 1}".encode(),
                        style="primary",
                    )
                )

            if nav_buttons:
                buttons.append(nav_buttons)

            if len(repos) > 1:
                repo_buttons = []
                for i in range(len(repos)):
                    repo_buttons.append(
                        Button.inline(
                            f"{i + 1}", f"catalog_{i}_1".encode(), style="primary"
                        )
                    )
                buttons.append(repo_buttons)

            return msg, buttons

        except Exception as e:
            logger.error(f"Ошибка в handle_catalog: {e}")
            import traceback

            traceback.print_exc()
            return t("catalog_error", error=str(e)[:100]), []

    async def get_inline_bot_username() -> str | None:
        username = kernel.config.get("inline_bot_username")
        if username:
            return username.lstrip("@")

        if kernel.is_bot_available():
            try:
                bot_info = await kernel.bot_client.get_me()
                return bot_info.username
            except Exception as e:
                kernel.logger.error(f"Error getting inline bot username: {e}")

        return None

    async def open_inline_result(
        event: types.Message,
        query: str,
    ) -> bool:
        bot_username = await get_inline_bot_username()
        if not bot_username:
            return False

        results = await client.inline_query(bot_username, query)
        if not results:
            return False

        await results[0].click(event.chat_id, reply_to=event.reply_to_msg_id)
        await event.delete()
        return True

    async def find_repo_matches(
        module_name: str,
        repos: list[str],
        add_log: Callable | None = None,
    ) -> list[dict[str, int | str]]:
        matches = []
        normalized = module_name.lower()

        for i, repo in enumerate(repos):
            try:
                if add_log:
                    add_log(t("log_checking_repo", index=i + 1, repo=repo))
                modules = await kernel.get_repo_modules_list(repo)
                if modules and any(name.lower() == normalized for name in modules):
                    repo_name = await kernel.get_repo_name(repo)
                    matches.append(
                        {
                            "repo_index": i,
                            "repo_name": repo_name,
                        }
                    )
                    if add_log:
                        add_log(t("log_found_in_repo"))
                elif add_log:
                    add_log(t("log_not_found_in_repo"))
            except Exception as e:
                if add_log:
                    add_log(t("log_repo_error", repo=repo, error=str(e)[:100]))
                await kernel.log_error(
                    f"Ошибка поиска модуля {module_name} в репозитории {repo}: {e}"
                )

        return matches

    async def open_repo_choice_form(
        event: types.Message,
        module_name: str,
        send_mode: bool,
        matches: list[dict[str, int | str]],
    ) -> bool:
        from core_inline.api.inline import make_cb_button

        session_uuid = str(uuid.uuid4())[:8]
        session_key = f"dlm:{session_uuid}"
        kernel._inline._session_put(
            session_key,
            {
                "module_name": module_name,
                "send_mode": send_mode,
                "user_id": event.sender_id,
                "matches": [
                    {
                        "repo_index": item["repo_index"],
                        "repo_name": item["repo_name"],
                    }
                    for item in matches
                ],
            },
            ttl=300,
        )

        buttons = []
        for item in matches:
            clean_name = re.sub(r"<[^>]+>", "", item["repo_name"])[:40]
            buttons.append(
                [
                    make_cb_button(
                        kernel,
                        f"{item['repo_index'] + 1}. {clean_name}",
                        dlm_repo_session_callback,
                        args=[session_uuid, str(item["repo_index"])],
                        ttl=300,
                    )
                ]
            )
        buttons.append(
            [
                make_cb_button(
                    kernel,
                    re.sub(r"<[^>]+>", "", t("dlm_repo_choice_cancel")),
                    dlm_repo_session_callback,
                    args=[session_uuid, "cancel"],
                    ttl=300,
                )
            ]
        )

        action_key = (
            "dlm_repo_choice_action_send"
            if send_mode
            else "dlm_repo_choice_action_install"
        )
        title = t(
            "dlm_repo_choice_title",
            cloud="🧩",
            module_name=module_name,
            action=t(action_key),
        )

        success, _ = await kernel.inline_form(
            event.chat_id,
            title=title,
            buttons=buttons,
            auto_send=True,
            ttl=300,
        )

        if success:
            await event.delete()
            return True
        return False

    async def dlm_repo_session_callback(event: types.CallbackQuery, *args) -> None:
        if not args:
            return

        session_uuid = args[0]
        action = args[1] if len(args) > 1 else ""

        session_key = f"dlm:{session_uuid}"
        select_data = kernel._inline._session_get(session_key, pop=True)

        if not select_data:
            await event.answer(t("dlm_repo_choice_expired"), alert=True)
            return

        if action == "cancel":
            await event.edit(t("dlm_repo_choice_cancelled"), parse_mode="html")
            return

        if select_data.get("user_id") != event.sender_id:
            await event.answer(t("dlm_repo_choice_expired"), alert=True)
            return

        repo_index = int(action)
        await run_dlm_install(
            event,
            select_data["module_name"],
            send_mode=select_data.get("send_mode", False),
            repo_index=repo_index,
        )

    async def catalog_inline_handler(event: types.InlineQuery) -> None:
        try:
            query = event.text or ""

            if not query or query == "catalog":
                query = "catalog_0_1"

            msg, buttons = await handle_catalog(event, query)

            if buttons:
                builder = event.builder.article(
                    "Catalog", text=msg, buttons=buttons, parse_mode="html"
                )
            else:
                builder = event.builder.article("Catalog", text=msg, parse_mode="html")

            await event.answer([builder])

        except Exception as e:
            logger.error(f"Ошибка в catalog_inline_handler: {e}")

    async def catalog_callback_handler(event: types.CallbackQuery) -> None:
        try:
            data_str = (
                event.data.decode("utf-8")
                if isinstance(event.data, bytes)
                else str(event.data)
            )

            msg, buttons = await handle_catalog(event, data_str)

            await event.edit(
                msg, buttons=buttons if buttons else None, parse_mode="html"
            )

        except Exception as e:
            logger.error(f"Ошибка в catalog_callback_handler: {e}")
            await event.answer(f"Ошибка: {str(e)[:50]}", alert=True)

    kernel.register_inline_handler("catalog", catalog_inline_handler)
    kernel.register_callback_handler("catalog_", catalog_callback_handler)

    def get_source_link(module_name: str) -> str:
        """Generate source link string for module."""
        source = kernel._module_sources.get(module_name)
        if source:
            url = source.get("url")
            repo = source.get("repo")
            if url:
                return f'<blockquote><tg-emoji emoji-id="5411527152212411235">🔗</tg-emoji> {url}</blockquote>'
            elif repo:
                # Normalize URL to avoid double slashes
                repo = repo.rstrip("/")
                return f'<blockquote><tg-emoji emoji-id="5411527152212411235">🔗</tg-emoji> {repo}/{module_name}.py</blockquote>'
        return ""

    async def run_dlm_install(
        event: types.Message,
        module_or_url: str,
        send_mode: bool = False,
        repo_index: int | None = None,
        preloaded_code: str | None = None,
        preloaded_repo_url: str | None = None,
    ) -> None:
        is_url = False
        if module_or_url.startswith(
            ("http://", "https://", "raw.githubusercontent.com")
        ):
            is_url = True
            if module_or_url.endswith(".py"):
                module_name = os.path.basename(module_or_url)[:-3]
            else:
                module_name = os.path.basename(module_or_url).split("?")[0]
                if "." in module_name:
                    module_name = module_name.split(".")[0]
        else:
            module_name = module_or_url

        cfg = get_config()
        if cfg and cfg.get("loader_protect_system", True):
            if module_name in kernel.system_modules:
                await edit_with_emoji(
                    event,
                    t(
                        "system_module_install_attempt",
                        confused=CUSTOM_EMOJI["confused"],
                        module_name=module_name,
                        blocked=CUSTOM_EMOJI["blocked"],
                    ),
                )
                return

        is_update = (
            module_name in kernel.loaded_modules or module_name in kernel.system_modules
        )

        old_version = None
        if is_update:
            old_file_path = os.path.join(
                (
                    kernel.MODULES_DIR
                    if module_name in kernel.system_modules
                    else kernel.MODULES_LOADED_DIR
                ),
                f"{module_name}.py",
            )
            old_version = await kernel._loader.get_module_version_from_file(
                old_file_path
            )

        install_log = []

        def add_log(message):
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] {message}"
            install_log.append(log_entry)
            kernel.logger.debug(log_entry)

        try:
            code = preloaded_code
            repo_url = preloaded_repo_url
            msg = None

            def target_message():
                return event

            add_log(
                t(
                    "log_start",
                    action="скачивание" if send_mode else "установку",
                    module_name=module_name,
                )
            )
            add_log(t("log_mode", mode="отправка" if send_mode else "установка"))
            add_log(t("log_type", type="URL" if is_url else "из репозитория"))

            if is_url:
                try:
                    add_log(t("log_download_url", url=module_or_url))
                    async with aiohttp.ClientSession() as session:
                        async with session.get(module_or_url) as resp:
                            if resp.status == 200:
                                code = await resp.text()
                                add_log(t("log_download_success", status=resp.status))
                            else:
                                add_log(t("log_download_failed", status=resp.status))
                                await edit_with_emoji(
                                    msg or event,
                                    t(
                                        "url_download_error",
                                        warning=CUSTOM_EMOJI["warning"],
                                        status=resp.status,
                                    ),
                                )
                                return
                except Exception as e:
                    add_log(t("log_download_exception", error=str(e)))
                    await kernel.handle_error(e, source="install_for_url", event=event)
                    await edit_with_emoji(
                        event,
                        t(
                            "url_exception",
                            warning=CUSTOM_EMOJI["warning"],
                            error=str(e)[:100],
                        ),
                    )
                    return
            elif code is None:
                repos = [kernel.default_repo] + kernel.repositories
                add_log(t("log_checking_repos", count=len(repos)))

                if repo_index is not None and 0 <= repo_index < len(repos):
                    repo_url = repos[repo_index]
                    add_log(t("log_using_repo", repo=repo_url))
                    code = await kernel.download_module_from_repo(repo_url, module_name)
                    if code:
                        add_log(t("log_found_in_repo"))
                    else:
                        add_log(t("log_not_found_in_repo"))
                else:
                    for i, repo in enumerate(repos):
                        try:
                            add_log(t("log_checking_repo", index=i + 1, repo=repo))
                            code = await kernel.download_module_from_repo(
                                repo, module_name
                            )
                            if code:
                                repo_url = repo
                                add_log(t("log_found_in_repo"))
                                break
                            else:
                                add_log(t("log_not_found_in_repo"))
                        except Exception as e:
                            add_log(
                                t(
                                    "log_repo_error",
                                    repo=repo,
                                    error=str(e)[:100],
                                )
                            )
                            await kernel.log_error(
                                f"Ошибка скачивания модуля {module_name} из {repo}: {e}"
                            )
                            continue

            if not code:
                await edit_with_emoji(
                    event,
                    t(
                        "module_not_found_repos",
                        warning=CUSTOM_EMOJI["warning"],
                        module_name=module_name,
                    ),
                )
                return

            metadata = await kernel.get_module_metadata(code)
            add_log(t("log_getting_metadata"))
            add_log(t("log_author", author=metadata["author"]))
            add_log(t("log_version", version=metadata["version"]))
            add_log(t("log_description", description=metadata["description"]))

            if send_mode:
                action = t("downloading_module", download=CUSTOM_EMOJI["download"])
            else:
                if is_update:
                    new_version = metadata["version"]
                    kernel.logger.info(
                        f"[loader] update check: {module_name} old={old_version} new={new_version}"
                    )
                    if old_version != new_version:
                        action = t(
                            "updating_version",
                            reload=CUSTOM_EMOJI["reload"],
                            old_version=old_version,
                            new_version=new_version,
                        )
                    else:
                        action = t("updating", reload=CUSTOM_EMOJI["reload"])
                else:
                    action = t("installing", test=CUSTOM_EMOJI["loading"])

            msg = await event.edit(
                t("starting_install", action=action, module_name=module_name),
                parse_mode="html",
            )

            file_path = os.path.join(
                (
                    kernel.MODULES_DIR
                    if module_name in kernel.system_modules
                    else kernel.MODULES_LOADED_DIR
                ),
                f"{module_name}.py",
            )

            if send_mode:
                add_log(t("log_saving_for_send"))
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(code)

                await edit_with_emoji(
                    target_message(),
                    t(
                        "sending_module",
                        upload=CUSTOM_EMOJI["upload"],
                        module_name=module_name,
                    ),
                )

                await event.edit(
                    t(
                        "file_sent_caption",
                        file=CUSTOM_EMOJI["file"],
                        module_name=module_name,
                        idea=CUSTOM_EMOJI["idea"],
                        description=metadata["description"],
                        crystal=CUSTOM_EMOJI["crystal"],
                        version=metadata["version"],
                        angel=CUSTOM_EMOJI["angel"],
                        author=metadata["author"],
                        folder=CUSTOM_EMOJI["folder"],
                        size=os.path.getsize(file_path),
                    ),
                    file=file_path,
                    parse_mode="html",
                )

                add_log(t("log_file_sent"))
                os.remove(file_path)
                return

            add_log(t("log_install_mode"))

            dependencies = kernel._loader.parse_requires(code)
            if dependencies:
                add_log(t("log_deps_found", deps=", ".join(dependencies)))

            if dependencies:
                deps_with_emoji = "\n".join(
                    f"{CUSTOM_EMOJI['lib']} {dep}" for dep in dependencies
                )
                await edit_with_emoji(
                    target_message(),
                    t(
                        "installing_deps",
                        dependencies=CUSTOM_EMOJI["dependencies"],
                        deps_list=deps_with_emoji,
                    ),
                )
                await kernel._loader.install_dependencies_batch(
                    dependencies, log_fn=add_log
                )

            if is_update:
                add_log(t("log_removing_old", module_name=module_name))
                await kernel.unregister_module_commands(module_name)

            add_log(t("log_saving_file", file_path=file_path))
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(code)

            add_log(t("log_loading_to_kernel"))

            if is_hikka_module(code):
                add_log(t("log_hikka_detected"))
                if not allow_hikka_modules():
                    await edit_with_emoji(
                        target_message(),
                        t("hikka_disabled", warning=CUSTOM_EMOJI["warning"]),
                    )
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    return
                if not HIKKA_COMPAT:
                    await edit_with_emoji(
                        target_message(),
                        t("hikka_no_compat", warning=CUSTOM_EMOJI["warning"]),
                    )
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    return

                await edit_with_emoji(
                    target_message(),
                    t(
                        "starting_install",
                        action=t("installing", test=CUSTOM_EMOJI["loading"]),
                    ),
                )
                ok, err, extra = await load_hikka_module(kernel, file_path, module_name)
                extra = extra or {}
                conflicts = extra.get("conflicts", [])
                if ok:
                    add_log(t("log_module_loaded_kernel"))
                    commands, aliases_info, descriptions = (
                        kernel._loader.get_module_commands(module_name)
                    )
                    emoji = random.choice(RANDOM_EMOJIS)
                    commands_list = ""
                    if commands:
                        add_log(t("log_commands_found", count=len(commands)))
                        for cmd in commands:
                            cmd_desc = (
                                descriptions.get(cmd)
                                or metadata["commands"].get(cmd)
                                or t("no_cmd_desc", no_cmd=CUSTOM_EMOJI["no_cmd"])
                            )
                            command_line = t(
                                "command_line",
                                crystal=CUSTOM_EMOJI["crystal"],
                                prefix=kernel.custom_prefix,
                                cmd=cmd,
                                desc=cmd_desc,
                            )
                            commands_list += command_line + "\n"

                    inline_commands = kernel.get_module_inline_commands(module_name)
                    if inline_commands:
                        inline_emoji = (
                            '<tg-emoji emoji-id="5372981976804366741">🤖</tg-emoji>'
                        )
                        for cmd, desc in inline_commands:
                            if desc:
                                commands_list += f"{inline_emoji} <code>@{kernel.config.get('inline_bot_username', 'bot')} {cmd}</code> – <b>{desc}</b>\n"
                            else:
                                commands_list += f"{inline_emoji} <code>@{kernel.config.get('inline_bot_username', 'bot')} {cmd}</code>\n"

                    conflict_text = ""
                    if conflicts:
                        conflict_text = (
                            f"\n\n⚠️ <b>Command conflicts ({len(conflicts)}):</b>\n"
                        )
                        for cf in conflicts:
                            owner = cf.get("owner") or "unknown"
                            conflict_text += f"<code>{cf['command']}</code> — registered by <code>{owner}</code>\n"

                    kernel.logger.info(f"Hikka модуль {module_name} установлен")

                    banner_url = metadata.get("banner_url")
                    cfg = get_config()
                    show_banners = (
                        cfg.get("loader_show_banners", False) if cfg else False
                    )
                    if (
                        show_banners
                        and banner_url
                        and banner_url.startswith(("http://", "https://"))
                    ):
                        try:
                            media = InputMediaWebPage(banner_url, optional=True)
                            await msg.edit(
                                t(
                                    "module_loaded",
                                    success=CUSTOM_EMOJI["success"],
                                    module_name=module_name,
                                    emoji=emoji,
                                    idea=CUSTOM_EMOJI["idea"],
                                    description=metadata["description"],
                                    version=metadata["version"],
                                    author=metadata.get("author", "unknown"),
                                    emoji_author=CUSTOM_EMOJI["author"],
                                    commands_list=commands_list + conflict_text,
                                    source_link=get_source_link(module_name),
                                ),
                                file=media,
                                parse_mode="html",
                                invert_media=True,
                            )
                        except Exception as e:
                            kernel.logger.error(f"Banner edit error: {e}")
                            await edit_with_emoji(
                                target_message(),
                                t(
                                    "module_loaded",
                                    success=CUSTOM_EMOJI["success"],
                                    module_name=module_name,
                                    emoji=emoji,
                                    idea=CUSTOM_EMOJI["idea"],
                                    description=metadata["description"],
                                    version=metadata["version"],
                                    author=metadata.get("author", "unknown"),
                                    emoji_author=CUSTOM_EMOJI["author"],
                                    commands_list=commands_list + conflict_text,
                                ),
                            )
                    else:
                        await edit_with_emoji(
                            target_message(),
                            t(
                                "module_loaded",
                                success=CUSTOM_EMOJI["success"],
                                module_name=module_name,
                                emoji=emoji,
                                idea=CUSTOM_EMOJI["idea"],
                                description=metadata["description"],
                                version=metadata["version"],
                                author=metadata.get("author", "unknown"),
                                emoji_author=CUSTOM_EMOJI["author"],
                                commands_list=commands_list + conflict_text,
                                source_link=get_source_link(module_name),
                            ),
                        )
                else:
                    add_log(t("log_install_error", error=err))
                    log_text = "\n".join(install_log)
                    await edit_with_emoji(
                        msg,
                        t(
                            "install_failed",
                            blocked=CUSTOM_EMOJI["blocked"],
                            idea=CUSTOM_EMOJI["idea"],
                            log=html.escape(log_text),
                        ),
                    )
                    if os.path.exists(file_path):
                        os.remove(file_path)
                return

            success, message_text = await kernel.load_module_from_file(
                file_path,
                module_name,
                False,
                source_url=module_or_url if is_url else None,
                source_repo=repo_url if not is_url and repo_url else None,
            )

            if success:
                add_log(t("log_module_loaded_kernel"))
                commands, aliases_info, descriptions = (
                    kernel._loader.get_module_commands(module_name)
                )
                emoji = random.choice(RANDOM_EMOJIS)

                commands_list = ""
                if commands:
                    add_log(t("log_commands_found", count=len(commands)))
                    for cmd in commands:
                        cmd_desc = (
                            descriptions.get(cmd)
                            or metadata["commands"].get(cmd)
                            or t("no_cmd_desc", no_cmd=CUSTOM_EMOJI["no_cmd"])
                        )

                        command_line = t(
                            "command_line",
                            crystal=CUSTOM_EMOJI["crystal"],
                            prefix=kernel.custom_prefix,
                            cmd=cmd,
                            desc=cmd_desc,
                        )

                        if cmd in aliases_info:
                            aliases = aliases_info[cmd]
                            if isinstance(aliases, str):
                                aliases = [aliases]
                            if aliases:
                                alias_text = ", ".join(
                                    [
                                        f"<code>{kernel.custom_prefix}{a}</code>"
                                        for a in aliases
                                    ]
                                )
                                command_line += t("aliases_text", alias_text=alias_text)
                                add_log(
                                    t(
                                        "log_aliases_found",
                                        cmd=cmd,
                                        aliases=", ".join(aliases),
                                    )
                                )
                        commands_list += command_line + "\n"

                inline_commands = kernel.get_module_inline_commands(module_name)
                if inline_commands:
                    inline_emoji = (
                        '<tg-emoji emoji-id="5372981976804366741">🤖</tg-emoji>'
                    )
                    for cmd, desc in inline_commands:
                        if desc:
                            commands_list += f"{inline_emoji} <code>@{kernel.config.get('inline_bot_username', 'bot')} {cmd}</code> – <b>{desc}</b>\n"
                        else:
                            commands_list += f"{inline_emoji} <code>@{kernel.config.get('inline_bot_username', 'bot')} {cmd}</code>\n"

                final_msg = t(
                    "module_loaded",
                    success=CUSTOM_EMOJI["success"],
                    module_name=module_name,
                    emoji=emoji,
                    idea=CUSTOM_EMOJI["idea"],
                    description=metadata["description"],
                    version=metadata["version"],
                    author=metadata.get("author", "unknown"),
                    emoji_author=CUSTOM_EMOJI["author"],
                    commands_list=commands_list,
                    source_link=get_source_link(module_name),
                )

                kernel.logger.info(f"Модуль {module_name} скачан")

                banner_url = metadata.get("banner_url")
                cfg = get_config()
                show_banners = cfg.get("loader_show_banners", False) if cfg else False
                if (
                    show_banners
                    and banner_url
                    and banner_url.startswith(("http://", "https://"))
                ):
                    try:
                        media = InputMediaWebPage(banner_url, optional=True)
                        await msg.edit(
                            final_msg, file=media, parse_mode="html", invert_media=True
                        )
                    except Exception as e:
                        kernel.logger.error(f"Banner edit error: {e}")
                        await edit_with_emoji(msg, final_msg)
                else:
                    await edit_with_emoji(target_message(), final_msg)
            else:
                add_log(t("log_install_error", error=message_text))
                log_text = "\n".join(install_log)
                await edit_with_emoji(
                    target_message(),
                    t(
                        "install_failed",
                        blocked=CUSTOM_EMOJI["blocked"],
                        idea=CUSTOM_EMOJI["idea"],
                        log=html.escape(log_text),
                    ),
                )
                if os.path.exists(file_path):
                    add_log(t("log_deleting_due_error"))
                    os.remove(file_path)

        except CommandConflictError as e:
            add_log(t("log_conflict", error=e))
            log_text = "\n".join(install_log)

            if e.conflict_type == "system":
                await edit_with_emoji(
                    target_message(),
                    t(
                        "conflict_system_alt",
                        shield=CUSTOM_EMOJI["shield"],
                        command=e.command,
                        log=html.escape(log_text),
                    ),
                )
            elif e.conflict_type == "user":
                await edit_with_emoji(
                    target_message(),
                    t(
                        "conflict_user_alt",
                        error=CUSTOM_EMOJI["error"],
                        log=html.escape(log_text),
                    ),
                )

            file_path = kernel._loader.get_module_path(module_name)
            if os.path.exists(file_path):
                add_log(t("log_deleting_due_conflict"))
                os.remove(file_path)

        except Exception as e:
            add_log(t("log_critical", error=str(e)))
            import traceback

            add_log(t("log_traceback", traceback=traceback.format_exc()))

            log_text = "\n".join(install_log)
            await edit_with_emoji(
                msg or event,
                t(
                    "install_failed",
                    blocked=CUSTOM_EMOJI["blocked"],
                    idea=CUSTOM_EMOJI["idea"],
                    log=html.escape(log_text),
                ),
            )

            file_path = kernel._loader.get_module_path(module_name)
            if os.path.exists(file_path):
                add_log(t("log_deleting_due_error"))
                os.remove(file_path)

            # Remove source info on error
            kernel._module_sources.pop(module_name, None)

    @kernel.register.command("iload", alias="im")
    # <reply> load module
    async def install_module_handler(event: types.CallbackQuery) -> None:
        if not event.is_reply:
            await edit_with_emoji(
                event, t("reply_to_py", warning=CUSTOM_EMOJI["warning"])
            )
            return

        reply = await event.get_reply_message()
        file_name = next(
            (
                getattr(attr, "file_name", None)
                for attr in (reply.document.attributes if reply.document else [])
                if hasattr(attr, "file_name")
            ),
            None,
        )
        if not reply.document or not file_name or not file_name.endswith(".py"):
            await edit_with_emoji(
                event, t("not_py_file", warning=CUSTOM_EMOJI["warning"])
            )
            return

        module_name = file_name[:-3]

        install_log = []

        def add_log(message):
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] {message}"
            install_log.append(log_entry)
            kernel.logger.debug(log_entry)

        cfg = get_config()
        if cfg and cfg.get("loader_protect_system", True):
            if module_name in kernel.system_modules:
                await edit_with_emoji(
                    event,
                    t(
                        "system_module_update_attempt",
                        confused=CUSTOM_EMOJI["confused"],
                        module_name=module_name,
                        blocked=CUSTOM_EMOJI["blocked"],
                    ),
                )
                return

        is_update = (
            module_name in kernel.loaded_modules or module_name in kernel.system_modules
        )

        old_version = None
        if is_update:
            old_file_path = kernel._loader.get_module_path(module_name)
            old_version = await kernel._loader.get_module_version_from_file(
                old_file_path
            )
            kernel.logger.info(
                f"[loader] BEFORE download - old_file={old_file_path} old_version={old_version}"
            )

        file_path = kernel._loader.get_module_path(module_name)

        try:
            add_log(t("log_downloading", file_path=file_path))
            await reply.download_media(file_path)
            add_log(t("log_downloaded"))

            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()
            add_log(t("log_file_read"))

            add_log(t("log_getting_metadata"))
            metadata = await kernel.get_module_metadata(code)
            dependencies = []
            add_log(t("log_author", author=metadata["author"]))
            add_log(t("log_version", version=metadata["version"]))
            add_log(t("log_description", description=metadata["description"]))

            if is_update:
                new_version = metadata["version"]
                kernel.logger.info(
                    f"[loader] update check: {module_name} old={old_version} new={new_version}"
                )
                if old_version != new_version:
                    action = t(
                        "updating_version",
                        reload=CUSTOM_EMOJI["loading"],
                        old_version=old_version,
                        new_version=new_version,
                    )
                else:
                    action = t("updating", reload=CUSTOM_EMOJI["loading"])
            else:
                action = t("installing", test=CUSTOM_EMOJI["loading"])

            msg = await event.edit(
                t("starting_install", action=action), parse_mode="html"
            )

            add_log(
                t(
                    "log_start",
                    action="обновление" if is_update else "установку",
                    module_name=module_name,
                )
            )
            add_log(t("log_filename", filename=file_name))

            mcub = await mcub_handler()
            add_log(t("log_checking_compatibility"))

            dependencies = kernel._loader.parse_requires(code)
            if dependencies:
                add_log(t("log_deps_found", deps=", ".join(dependencies)))

            if is_hikka_module(code):
                add_log(t("log_hikka_detected"))
                if not allow_hikka_modules():
                    await edit_with_emoji(
                        msg,
                        t("hikka_disabled", warning=CUSTOM_EMOJI["warning"]),
                    )
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    return
                if not HIKKA_COMPAT:
                    await edit_with_emoji(
                        msg,
                        t("hikka_no_compat", warning=CUSTOM_EMOJI["warning"]),
                    )
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    return

                await edit_with_emoji(
                    msg,
                    t(
                        "starting_install",
                        action=t("installing", test=CUSTOM_EMOJI["loading"]),
                    ),
                )
            if dependencies:
                deps_with_emoji = "\n".join(
                    f"{CUSTOM_EMOJI['lib']} {dep}" for dep in dependencies
                )
                await edit_with_emoji(
                    msg,
                    t(
                        "installing_deps",
                        dependencies=CUSTOM_EMOJI["dependencies"],
                        deps_list=deps_with_emoji,
                    ),
                )
                await kernel._loader.install_dependencies_batch(
                    dependencies, log_fn=add_log
                )

            if is_update:
                add_log(t("log_removing_old", module_name=module_name))
                await kernel.unregister_module_commands(module_name)

            add_log(t("log_loading_module", module_name=module_name))
            success, message_text = await kernel.load_module_from_file(
                file_path, module_name, False, source_url=None, source_repo=None
            )

            if success:
                add_log(t("log_module_loaded"))
                commands, aliases_info, descriptions = (
                    kernel._loader.get_module_commands(module_name)
                )

                emoji = random.choice(RANDOM_EMOJIS)

                commands_list = ""
                if commands:
                    add_log(t("log_commands_found", count=len(commands)))
                    for cmd in commands:
                        cmd_desc = (
                            descriptions.get(cmd)
                            or metadata["commands"].get(cmd)
                            or t("no_cmd_desc", no_cmd=CUSTOM_EMOJI["no_cmd"])
                        )

                        command_line = t(
                            "command_line",
                            crystal=CUSTOM_EMOJI["crystal"],
                            prefix=kernel.custom_prefix,
                            cmd=cmd,
                            desc=cmd_desc,
                        )

                        if cmd in aliases_info:
                            aliases = aliases_info[cmd]
                            if isinstance(aliases, str):
                                aliases = [aliases]
                            if aliases:
                                alias_text = ", ".join(
                                    [
                                        f"<code>{kernel.custom_prefix}{a}</code>"
                                        for a in aliases
                                    ]
                                )
                                command_line += t("aliases_text", alias_text=alias_text)
                                add_log(
                                    t(
                                        "log_aliases_found",
                                        cmd=cmd,
                                        aliases=", ".join(aliases),
                                    )
                                )
                        commands_list += command_line + "\n"

                inline_commands = kernel.get_module_inline_commands(module_name)
                if inline_commands:
                    inline_emoji = (
                        '<tg-emoji emoji-id="5372981976804366741">🤖</tg-emoji>'
                    )
                    for cmd, desc in inline_commands:
                        if desc:
                            commands_list += f"{inline_emoji} <code>@{kernel.config.get('inline_bot_username', 'bot')} {cmd}</code> – <b>{desc}</b>\n"
                        else:
                            commands_list += f"{inline_emoji} <code>@{kernel.config.get('inline_bot_username', 'bot')} {cmd}</code>\n"

                final_msg = t(
                    "module_loaded",
                    success=CUSTOM_EMOJI["success"],
                    module_name=module_name,
                    emoji=emoji,
                    idea=CUSTOM_EMOJI["idea"],
                    description=metadata["description"],
                    version=metadata["version"],
                    author=metadata.get("author", "unknown"),
                    emoji_author=CUSTOM_EMOJI["author"],
                    commands_list=commands_list,
                    source_link=get_source_link(module_name),
                )

                kernel.logger.info(f"Модуль {module_name} установлен")

                banner_url = metadata.get("banner_url")
                cfg = get_config()
                show_banners = cfg.get("loader_show_banners", False) if cfg else False
                if (
                    show_banners
                    and banner_url
                    and banner_url.startswith(("http://", "https://"))
                ):
                    try:
                        media = InputMediaWebPage(banner_url, optional=True)
                        await msg.edit(
                            final_msg, file=media, parse_mode="html", invert_media=True
                        )
                    except Exception as e:
                        kernel.logger.error(f"Banner edit error: {e}")
                        await edit_with_emoji(msg, final_msg)
                else:
                    await edit_with_emoji(msg, final_msg)

            else:
                add_log(t("log_install_error", error=message_text))
                log_text = "\n".join(install_log)
                await edit_with_emoji(
                    msg,
                    t(
                        "install_failed",
                        blocked=CUSTOM_EMOJI["blocked"],
                        idea=CUSTOM_EMOJI["idea"],
                        log=html.escape(log_text),
                    ),
                )

                if os.path.exists(file_path):
                    os.remove(file_path)

        except CommandConflictError as e:
            add_log(t("log_conflict", error=e))
            log_text = "\n".join(install_log)

            if e.conflict_type == "system":
                await edit_with_emoji(
                    msg,
                    t(
                        "conflict_system",
                        shield=CUSTOM_EMOJI["shield"],
                        prefix=kernel.custom_prefix,
                        command=e.command,
                        log=html.escape(log_text),
                    ),
                )
            elif e.conflict_type == "user":
                owner_module = kernel.command_owners.get(e.command, "unknown")
                await edit_with_emoji(
                    msg,
                    t(
                        "conflict_user",
                        error=CUSTOM_EMOJI["error"],
                        prefix=kernel.custom_prefix,
                        command=e.command,
                        owner_module=owner_module,
                        log=html.escape(log_text),
                    ),
                )
            if os.path.exists(file_path):
                os.remove(file_path)

        except Exception as e:
            add_log(t("log_critical", error=str(e)))
            import traceback

            add_log(t("log_traceback", traceback=traceback.format_exc()))

            log_text = "\n".join(install_log)
            await edit_with_emoji(
                msg,
                t(
                    "install_failed",
                    blocked=CUSTOM_EMOJI["blocked"],
                    idea=CUSTOM_EMOJI["idea"],
                    log=html.escape(log_text),
                ),
            )
            await kernel.handle_error(e, source="install_module_handler", event=event)
            if os.path.exists(file_path):
                os.remove(file_path)

    @kernel.register.command("dlm")
    # <args> <URL/module> -s send as file, -list list modules
    async def download_module_handler(event: types.Message) -> None:
        args = event.text.split()

        if len(args) < 2:
            try:
                if await open_inline_result(event, "catalog"):
                    return
            except Exception as e:
                kernel.logger.error(f"Error calling inline catalog: {e}")

            await edit_with_emoji(
                event,
                t(
                    "dlm_usage",
                    warning=CUSTOM_EMOJI["warning"],
                    prefix=kernel.custom_prefix,
                ),
            )
            return

        await edit_with_emoji(
            event,
            t(
                "wait",
                wait=CUSTOM_EMOJI["wait"],
            ),
        )

        if args[1] == "-list":
            if len(args) == 2:
                await edit_with_emoji(
                    event, t("dlm_list_loading", loading=CUSTOM_EMOJI["loading"])
                )

                repos = [kernel.default_repo] + kernel.repositories
                message_lines = []
                errors = []

                for i, repo in enumerate(repos):
                    try:
                        modules = await kernel.get_repo_modules_list(repo)
                        repo_name = await kernel.get_repo_name(repo)

                        if modules:
                            module_list = " | ".join(modules)
                            message_lines.append(f"<b>{repo_name}</b>: {module_list}")
                        else:
                            errors.append(f"{i + 1}. {repo_name}: пустой список")
                    except Exception as e:
                        errors.append(f"{i + 1}. {repo}: ошибка - {str(e)[:50]}")

                if message_lines:
                    msg_text = "\n".join(message_lines)
                    final_msg = t(
                        "dlm_list_title", folder=CUSTOM_EMOJI["folder"], list=msg_text
                    )

                    if errors:
                        final_msg += t(
                            "dlm_list_errors",
                            warning=CUSTOM_EMOJI["warning"],
                            errors="<br>".join(errors),
                        )
                else:
                    final_msg = t("dlm_list_failed", warning=CUSTOM_EMOJI["warning"])
                    if errors:
                        final_msg += f"\n<blockquote expandable>{'<br>'.join(errors)}</blockquote>"

                await edit_with_emoji(event, final_msg)
                return
            else:
                module_name = args[2]
                msg = await event.edit(
                    t(
                        "dlm_searching",
                        loading=CUSTOM_EMOJI["loading"],
                        module_name=module_name,
                    ),
                    parse_mode="html",
                )

                repos = [kernel.default_repo] + kernel.repositories
                found = False

                for repo in repos:
                    try:
                        code = await kernel.download_module_from_repo(repo, module_name)
                        if code:
                            found = True
                            metadata = await kernel.get_module_metadata(code)
                            size = len(code.encode("utf-8"))

                            info = t(
                                "module_info",
                                file=CUSTOM_EMOJI["file"],
                                module_name=module_name,
                                idea=CUSTOM_EMOJI["idea"],
                                description=metadata["description"],
                                crystal=CUSTOM_EMOJI["crystal"],
                                version=metadata["version"],
                                angel=CUSTOM_EMOJI["angel"],
                                author=metadata["author"],
                                folder=CUSTOM_EMOJI["folder"],
                                size=size,
                                cloud=CUSTOM_EMOJI["cloud"],
                                repo=repo,
                            )
                            await edit_with_emoji(msg, info)
                            break
                    except Exception as e:
                        await kernel.log_error(
                            f"Ошибка поиска модуля {module_name} в {repo}: {e}"
                        )
                        continue

                if not found:
                    await edit_with_emoji(
                        msg,
                        t(
                            "module_not_found",
                            warning=CUSTOM_EMOJI["warning"],
                            module_name=module_name,
                        ),
                    )
                return

        send_mode = False
        module_or_url = None
        repo_index = None

        if args[1] in ["-send", "-s", "--send"]:
            if len(args) < 3:
                await edit_with_emoji(
                    event,
                    t(
                        "dlm_send_usage",
                        warning=CUSTOM_EMOJI["warning"],
                        prefix=kernel.custom_prefix,
                    ),
                )
                return
            send_mode = True
            module_or_url = args[2]
            if len(args) > 3 and args[3].isdigit():
                repo_index = int(args[3]) - 1
        else:
            module_or_url = args[1]
            if len(args) > 2 and args[2].isdigit():
                repo_index = int(args[2]) - 1
            send_mode = False
        is_url = module_or_url.startswith(
            ("http://", "https://", "raw.githubusercontent.com")
        )

        if not is_url and repo_index is None:
            repos = [kernel.default_repo] + kernel.repositories
            matches = await find_repo_matches(module_or_url, repos)

            if len(matches) > 1:
                opened = await open_repo_choice_form(
                    event, module_or_url, send_mode, matches
                )
                if opened:
                    return

            if len(matches) == 1:
                repo_index = matches[0]["repo_index"]

        await run_dlm_install(
            event,
            module_or_url,
            send_mode=send_mode,
            repo_index=repo_index,
        )

    @kernel.register.command("um")
    # <module> remove module
    async def unload_module_handler(event: types.Message) -> None:
        args = event.text.split()
        if len(args) < 2:
            await edit_with_emoji(
                event,
                t(
                    "um_usage",
                    warning=CUSTOM_EMOJI["warning"],
                    prefix=kernel.custom_prefix,
                ),
            )
            return

        module_name = args[1]

        actual_name, _ = kernel._loader.find_module_case_insensitive(module_name)
        if actual_name is None:
            await edit_with_emoji(
                event,
                t(
                    "module_not_found_um",
                    warning=CUSTOM_EMOJI["warning"],
                    module_name=module_name,
                ),
            )
            return

        module_name = actual_name

        cfg = get_config()
        force_unload = not (cfg and cfg.get("loader_protect_system", True))

        try:
            await kernel.unregister_module_commands(module_name, force=force_unload)
        except PermissionError as e:
            await edit_with_emoji(
                event,
                t(
                    "system_module_unload_attempt",
                    confused=CUSTOM_EMOJI["confused"],
                    blocked=CUSTOM_EMOJI["blocked"],
                    module_name=module_name,
                ),
            )
            return

        instance = kernel.loaded_modules.get(module_name)
        if instance and getattr(instance, "_hikka_compat", False):
            await unload_hikka_module(kernel, module_name)
        else:
            commands_to_remove = [
                cmd
                for cmd, owner in kernel.command_owners.items()
                if owner == module_name
            ]
            try:
                await kernel.unregister_module_commands(module_name, force=force_unload)
            except PermissionError:
                await edit_with_emoji(
                    event,
                    t(
                        "system_module_unload_attempt",
                        confused=CUSTOM_EMOJI["confused"],
                        blocked=CUSTOM_EMOJI["blocked"],
                        module_name=module_name,
                    ),
                )
                return

            kernel._loader.remove_module_aliases(module_name, commands_to_remove)

        file_path = kernel._loader.get_module_path(module_name)
        if os.path.exists(file_path):
            os.remove(file_path)

        if module_name in sys.modules:
            del sys.modules[module_name]

        if module_name in kernel.loaded_modules:
            del kernel.loaded_modules[module_name]

        if module_name in kernel.system_modules:
            del kernel.system_modules[module_name]

        await log_to_bot(f"Модуль {module_name} удалён")
        await edit_with_emoji(
            event,
            t(
                "module_unloaded",
                success=CUSTOM_EMOJI["success"],
                module_name=module_name,
            ),
        )

        # Remove source info and save
        kernel._module_sources.pop(module_name, None)
        await kernel.save_module_sources()

    @kernel.register.command("unlm")
    # <module> - upload as file
    async def upload_module_handler(event: types.Message) -> None:
        args = event.text.split()
        if len(args) < 2:
            await edit_with_emoji(
                event,
                t(
                    "unlm_usage",
                    warning=CUSTOM_EMOJI["warning"],
                    prefix=kernel.custom_prefix,
                ),
            )
            return

        module_name = args[1]

        actual_name, _ = kernel._loader.find_module_case_insensitive(module_name)
        if actual_name is None:
            await edit_with_emoji(
                event,
                t(
                    "module_not_found_um",
                    warning=CUSTOM_EMOJI["warning"],
                    module_name=module_name,
                ),
            )
            return

        module_name = actual_name

        file_path = kernel._loader.get_module_path(module_name)

        if not os.path.exists(file_path):
            await edit_with_emoji(
                event, t("module_file_not_found", warning=CUSTOM_EMOJI["warning"])
            )
            return

        await edit_with_emoji(
            event,
            t(
                "uploading_module",
                upload=CUSTOM_EMOJI["upload"],
                module_name=module_name,
            ),
        )
        await event.edit(
            t(
                "file_upload_caption",
                file=CUSTOM_EMOJI["file"],
                module_name=module_name,
                prefix=kernel.custom_prefix,
                source_link=get_source_link(module_name),
            ),
            parse_mode="html",
            file=file_path,
        )

    @kernel.register.command("reload")
    # <modules> reload modules
    async def reload_module_handler(event: types.Message) -> None:
        args = event.text.split()
        kernel.dedupe_event_builders(reason="reload_command_start_precheck")
        kernel.ensure_core_message_handlers(reason="reload_command_start")
        kernel.ensure_registered_module_handlers(reason="reload_command_start")
        kernel.logger.debug(
            "[reload] request text=%r loaded=%r system=%r",
            event.text,
            list(kernel.loaded_modules.keys()),
            list(kernel.system_modules.keys()),
        )

        if len(args) < 2:
            modules_to_reload = list(kernel.loaded_modules.keys())
            if not modules_to_reload:
                kernel.logger.debug("[reload] no-loaded-modules")
                await edit_with_emoji(
                    event,
                    t("no_modules", folder=CUSTOM_EMOJI["folder"]),
                )
                return

            msg = await event.edit(
                t("reload_all", reload=CUSTOM_EMOJI["reload"]),
                parse_mode="html",
            )

            results = []
            failed = []

            cfg = get_config()
            force_unload = not (cfg and cfg.get("loader_protect_system", True))

            for module_name in modules_to_reload:
                kernel.logger.debug(
                    "[reload] reloading-from-bulk module=%r", module_name
                )

                file_path = os.path.join(
                    (
                        kernel.MODULES_DIR
                        if module_name in kernel.system_modules
                        else kernel.MODULES_LOADED_DIR
                    ),
                    f"{module_name}.py",
                )

                if not os.path.exists(file_path):
                    kernel.logger.debug(
                        "[reload] missing-file bulk module=%r file=%r",
                        module_name,
                        file_path,
                    )
                    failed.append(module_name)
                    continue

                if module_name in sys.modules:
                    kernel.logger.debug(
                        "[reload] removing-sys-module module=%r", module_name
                    )
                    del sys.modules[module_name]

                try:
                    await kernel.unregister_module_commands(
                        module_name, force=force_unload
                    )
                except PermissionError:
                    kernel.logger.debug(
                        "[reload] skipped-system-module module=%r", module_name
                    )
                    continue
                kernel.logger.debug(
                    "[reload] after-unregister module=%r commands=%r aliases=%r",
                    module_name,
                    list(kernel.command_handlers.keys()),
                    dict(kernel.aliases),
                )

                if module_name in kernel.loaded_modules:
                    kernel.logger.debug(
                        "[reload] dropping-loaded-module module=%r", module_name
                    )
                    del kernel.loaded_modules[module_name]

                # Preserve source info on reload
                old_source = kernel._module_sources.get(module_name)

                success, _ = await kernel.load_module_from_file(
                    file_path,
                    module_name,
                    False,
                    source_url=old_source.get("url") if old_source else None,
                    source_repo=old_source.get("repo") if old_source else None,
                )
                kernel.logger.debug(
                    "[reload] post-load bulk module=%r success=%s loaded=%s",
                    module_name,
                    success,
                    module_name in kernel.loaded_modules,
                )
                kernel.dedupe_event_builders(reason=f"reload_bulk_after_{module_name}")
                kernel.ensure_core_message_handlers(
                    reason=f"reload_bulk_after_{module_name}"
                )
                kernel.ensure_registered_module_handlers(
                    reason=f"reload_bulk_after_{module_name}"
                )
                kernel.logger.debug(
                    "[reload] bulk-result module=%r success=%s commands=%r aliases=%r",
                    module_name,
                    success,
                    list(kernel.command_handlers.keys()),
                    dict(kernel.aliases),
                )

                if success:
                    results.append(module_name)
                else:
                    failed.append(module_name)

            success_count = len(results)
            failed_count = len(failed)

            if failed:
                failed_list = ""
                for i, name in enumerate(failed[:10]):
                    failed_list += t("failed_module", name=name)
                if failed_count > 10:
                    failed_list += t("and_more", count=failed_count - 10)

                if success_count > 0:
                    await edit_with_emoji(
                        msg,
                        t(
                            "reload_all_partial",
                            success=CUSTOM_EMOJI["success"],
                            success_count=f"✓ {success_count}",
                            warning=CUSTOM_EMOJI["warning"],
                            failed_count=failed_count,
                            failed_list=failed_list,
                        ),
                    )
                else:
                    await edit_with_emoji(
                        msg,
                        t(
                            "reload_all_failed",
                            warning=CUSTOM_EMOJI["warning"],
                            count=failed_count,
                            failed_list=failed_list,
                        ),
                    )
            else:
                if success_count == 1:
                    await edit_with_emoji(
                        msg,
                        t(
                            "reload_all_success_one",
                            success=CUSTOM_EMOJI["success"],
                            count=f"1",
                            name=results[0],
                        ),
                    )
                else:
                    await edit_with_emoji(
                        msg,
                        t(
                            "reload_all_success",
                            success=CUSTOM_EMOJI["success"],
                            count=f"✓ {success_count}",
                        ),
                    )
            kernel.dedupe_event_builders(reason="reload_bulk_complete")
            kernel.ensure_core_message_handlers(reason="reload_bulk_complete")
            kernel.ensure_registered_module_handlers(reason="reload_bulk_complete")
            return

        module_name = args[1]

        actual_name, _ = kernel._loader.find_module_case_insensitive(module_name)
        if actual_name is None:
            kernel.logger.debug(
                "[reload] module-not-found requested=%r loaded=%r system=%r",
                module_name,
                list(kernel.loaded_modules.keys()),
                list(kernel.system_modules.keys()),
            )
            await edit_with_emoji(
                event,
                t(
                    "module_not_found_um",
                    warning=CUSTOM_EMOJI["warning"],
                    module_name=module_name,
                ),
            )
            return

        module_name = actual_name

        file_path = kernel._loader.get_module_path(module_name)
        is_system = module_name in kernel.system_modules

        if not os.path.exists(file_path):
            kernel.logger.debug(
                "[reload] single-missing-file module=%r file=%r system=%s",
                module_name,
                file_path,
                is_system,
            )
            await edit_with_emoji(
                event, t("module_file_not_found", warning=CUSTOM_EMOJI["warning"])
            )
            return

        msg = await event.edit(
            t("reloading", reload=CUSTOM_EMOJI["reload"], module_name=module_name),
            parse_mode="html",
        )
        kernel.logger.debug(
            "[reload] single-start module=%r system=%s file=%r",
            module_name,
            is_system,
            file_path,
        )

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()
            dependencies = kernel._loader.parse_requires(code)
        except Exception as e:
            dependencies = []
            kernel.logger.warning(
                "[reload] failed to parse dependencies for %s: %s", module_name, e
            )

        if dependencies:
            deps_with_emoji = "\n".join(
                f"{CUSTOM_EMOJI['lib']} {dep}" for dep in dependencies
            )
            await edit_with_emoji(
                msg,
                t(
                    "installing_deps",
                    dependencies=CUSTOM_EMOJI["dependencies"],
                    deps_list=deps_with_emoji,
                ),
            )
            try:
                await kernel._loader.install_dependencies_batch(dependencies)
            except Exception as e:
                kernel.logger.error(
                    "[reload] deps install failed for %s: %s", module_name, e
                )
                await edit_with_emoji(
                    msg,
                    t(
                        "install_failed",
                        blocked=CUSTOM_EMOJI["blocked"],
                        idea=CUSTOM_EMOJI["idea"],
                        log=html.escape(str(e)),
                    ),
                )
                return

        instance = kernel.loaded_modules.get(module_name) or kernel.system_modules.get(
            module_name
        )
        if instance and getattr(instance, "_hikka_compat", False):
            kernel.logger.debug("[reload] single-hikka-compat module=%r", module_name)
            if HIKKA_COMPAT:
                await unload_hikka_module(kernel, module_name)
                await asyncio.sleep(0)
        else:
            cfg = get_config()
            force_unload = not (cfg and cfg.get("loader_protect_system", True))
            try:
                await kernel.unregister_module_commands(module_name, force=force_unload)
            except PermissionError:
                await edit_with_emoji(
                    msg,
                    t(
                        "system_module_unload_attempt",
                        confused=CUSTOM_EMOJI["confused"],
                        blocked=CUSTOM_EMOJI["blocked"],
                        module_name=module_name,
                    ),
                )
                return

            kernel.logger.debug(
                "[reload] single-after-unregister module=%r commands=%r aliases=%r",
                module_name,
                list(kernel.command_handlers.keys()),
                dict(kernel.aliases),
            )

        if module_name in sys.modules:
            kernel.logger.debug(
                "[reload] single-remove-sys-module module=%r", module_name
            )
            del sys.modules[module_name]

        if module_name in kernel.loaded_modules:
            kernel.logger.debug(
                "[reload] single-drop-loaded-module module=%r", module_name
            )
            del kernel.loaded_modules[module_name]
        else:
            kernel.logger.debug(
                "[reload] single-loaded-module-absent module=%r", module_name
            )

        if is_system:
            cfg = get_config()
            if cfg and cfg.get("loader_protect_system", True):
                if module_name in kernel.system_modules:
                    kernel.logger.debug(
                        "[reload] single-drop-system-module module=%r", module_name
                    )
                    del kernel.system_modules[module_name]
                else:
                    kernel.logger.debug(
                        "[reload] single-system-module-already-absent module=%r",
                        module_name,
                    )
            else:
                kernel.logger.debug(
                    "[reload] single-keep-system-module module=%r (protect disabled)",
                    module_name,
                )

        success, message_text = await kernel.load_module_from_file(
            file_path, module_name, is_system
        )
        kernel.logger.debug(
            "[reload] single-post-load module=%r success=%s loaded=%s system=%s",
            module_name,
            success,
            module_name in kernel.loaded_modules,
            module_name in kernel.system_modules,
        )
        kernel.dedupe_event_builders(reason=f"reload_single_after_{module_name}")
        kernel.ensure_core_message_handlers(reason=f"reload_single_after_{module_name}")
        kernel.ensure_registered_module_handlers(
            reason=f"reload_single_after_{module_name}"
        )
        kernel.logger.debug(
            "[reload] single-result module=%r success=%s message=%r commands=%r aliases=%r",
            module_name,
            success,
            message_text,
            list(kernel.command_handlers.keys()),
            dict(kernel.aliases),
        )

        if success:
            commands, _, _ = kernel._loader.get_module_commands(module_name)
            cmd_text = (
                f"{CUSTOM_EMOJI['crystal']} {', '.join([f'<code>{kernel.custom_prefix}{cmd}</code>' for cmd in commands])}"
                if commands
                else t("no_commands")
            )

            emoji = random.choice(RANDOM_EMOJIS)
            kernel.logger.info(f"Модуль {module_name} перезагружен")
            await edit_with_emoji(
                msg,
                t(
                    "reload_success",
                    success=CUSTOM_EMOJI["success"],
                    module_name=module_name,
                    emoji=emoji,
                    cmd_text=cmd_text,
                ),
            )
        else:
            await kernel.handle_error(
                Exception(message_text), source="reload_module_handler", event=event
            )
            await edit_with_emoji(
                msg, t("reload_error", warning=CUSTOM_EMOJI["warning"])
            )

    @kernel.register.command("addrepo")
    # <URL> add repo
    async def add_repo_handler(event: types.Message) -> None:
        args = event.text.split()
        if len(args) < 2:
            await edit_with_emoji(
                event,
                t(
                    "addrepo_usage",
                    warning=CUSTOM_EMOJI["warning"],
                    prefix=kernel.custom_prefix,
                ),
            )
            return

        url = args[1].strip()
        success, message = await kernel.add_repository(url)

        if success:
            await edit_with_emoji(event, f"{CUSTOM_EMOJI['success']} <b>{message}</b>")
        else:
            await edit_with_emoji(event, f"{CUSTOM_EMOJI['warning']} <b>{message}</b>")

    @kernel.register.command("delrepo")
    # <id> remove repo
    async def del_repo_handler(event: types.Message) -> None:
        args = event.text.split()
        if len(args) < 2:
            await edit_with_emoji(
                event,
                t(
                    "delrepo_usage",
                    warning=CUSTOM_EMOJI["warning"],
                    prefix=kernel.custom_prefix,
                ),
            )
            return

        success, message = await kernel.remove_repository(args[1])

        if success:
            await edit_with_emoji(event, f"{CUSTOM_EMOJI['success']} <b>{message}</b>")
        else:
            await edit_with_emoji(event, f"{CUSTOM_EMOJI['warning']} <b>{message}</b>")
