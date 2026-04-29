# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

# author: @Hairpin00
# version: 1.1.5
# description: Module loader
import asyncio
import html
import inspect
import logging
import os
import random
import re
import shutil
import sys
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any

import aiohttp
from telethon import Button, events
from telethon.types import InputMediaWebPage

if TYPE_CHECKING:
    pass

from core.lib.loader.module_base import ModuleBase, command
from core.lib.loader.module_config import (
    Boolean,
    ConfigValue,
    ModuleConfig,
)
from core.lib.utils.exceptions import CommandConflictError

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


class Loader(ModuleBase):
    name = "loader"
    version = "1.1.5"
    author = "@Hairpin00"
    description: dict[str, str] = {
        "ru": "Загрузчик модулей",
        "en": "Module loader",
    }

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

    strings = {"name": "loader"}

    # OLD STRINGS (removed after migration to langpacks) - kept for reference
    # TODO: Remove after verifying langpacks work
    """
    _OLD_STRINGS = {
        "en": {
            "wait": "{wait} <b>Please wait...</b>",
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
            "module_loaded": (
                "{success} <b>Module</b> <code>{module_name}</code> <b>loaded!</b> (<code>{version}</code>) {emoji}\n"
                "<blockquote expandable>{idea} <b>Description:</b> {description}</blockquote>\n"
                "<blockquote expandable>{commands_list}</blockquote>\n"
                "<blockquote>{emoji_author} Author: {author}</blockquote>\n"
                "{source_link}"
            ),
            "module_loaded_no_cmds": (
                "{success} <b>Module</b> <code>{module_name}</code> <b>loaded!</b> (<code>{version}</code>) {emoji}\n"
                "<blockquote expandable>{idea} <b>Description:</b> {description}</blockquote>\n"
                "<blockquote>{emoji_author} Author: {author}</blockquote>\n"
                "<blockquote>{source_link}</blockquote>"
            ),
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
            "module_loaded": "{success} <b>Модуль</b> <code>{module_name}</code> <b>загружен!</b> (<code>{version}</code>) {emoji}\n<blockquote expandable>{idea} <b>Описание:</b> {description}</blockquote>\n<blockquote expandable>{commands_list}</blockquote>\n<blockquote>{emoji_author} Автор: {author}</blockquote>\n{source_link}",
            "module_loaded_no_cmds": "{success} <b>Модуль</b> <code>{module_name}</code> <b>загружен!</b> (<code>{version}</code>) {emoji}\n<blockquote expandable>{idea} <b>Описание:</b> {description}</blockquote>\n<blockquote>{emoji_author} Автор: {author}</blockquote>\n{source_link}",
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
    """

    async def on_load(self) -> None:
        await super().on_load()

        defaults = {
            "loader_protect_system": True,
            "loader_show_banners": True,
            "loader_allow_hikka_modules": True,
        }
        config_dict = await self.kernel.get_module_config(self.name, defaults)
        self.config.from_dict(config_dict)
        self.kernel.store_module_config_schema(self.name, self.config)
        clean = {k: v for k, v in self.config.to_dict().items() if v is not None}
        if clean:
            await self.kernel.save_module_config(self.name, clean)

        self.kernel.register_inline_handler("catalog", self._catalog_inline_handler)
        self.kernel.register_callback_handler(
            "catalog_", self._catalog_callback_handler
        )

    async def on_unload(self) -> None:
        pass

    def get_config(self):
        live = getattr(self.kernel, "_live_module_configs", {}).get(self.name)
        return live if live else self.config

    def _allow_hikka_modules(self) -> bool:
        cfg = self.get_config()
        if cfg is None:
            return True
        return cfg.get("loader_allow_hikka_modules", True)

    def _module_description(self, metadata: dict | None) -> str:
        if not metadata:
            return ""
        current_lang = self.kernel.config.get("language", "en")
        fallback = metadata.get("description") or ""
        return self.kernel._loader.pick_localized_text(
            metadata.get("description_i18n"),
            current_lang,
            fallback,
        )

    async def _mcub_handler(self) -> str:
        me = await self.kernel.client.get_me()
        mcub_emoji = (
            '<tg-emoji emoji-id="5470015630302287916">🔮</tg-emoji>'
            '<tg-emoji emoji-id="5469945764069280010">🔮</tg-emoji>'
            '<tg-emoji emoji-id="5469943045354984820">🔮</tg-emoji>'
            '<tg-emoji emoji-id="5469879466954098867">🔮</tg-emoji>'
            if me.premium
            else "MCUB"
        )
        return mcub_emoji

    async def _log_to_bot(self, text: str) -> None:
        if hasattr(self.kernel, "_log") and self.kernel._log:
            await self.kernel._log.log_module(text)
        elif hasattr(self.kernel, "send_log_message"):
            await self.kernel.send_log_message(f"{CUSTOM_EMOJI['crystal']} {text}")

    @staticmethod
    def _restore_backup_and_cleanup(
        backup_content: str | None,
        backup_path: str | None,
        new_file_path: str,
        add_log_fn: Callable,
    ) -> None:
        if os.path.exists(new_file_path):
            os.remove(new_file_path)
        if backup_content and backup_path:
            try:
                with open(backup_path, "w", encoding="utf-8") as f:
                    f.write(backup_content)
                add_log_fn(f"=> Backup restored: {backup_path}")
                logger.info(f"[loader] Backup restored to {backup_path}")
            except Exception as e:
                logger.error(f"[loader] Failed to restore backup: {e}")
                add_log_fn(f"=X Failed to restore backup: {e}")

    async def _restore_module_after_failed_update(
        self,
        module_name: str,
        is_system_target: bool,
        backup_path: str | None,
        add_log_fn: Callable,
    ) -> None:
        """Reload module from restored backup so commands are not lost."""
        if not backup_path or not os.path.exists(backup_path):
            return
        try:
            res = await self.kernel.load_module_from_file(
                backup_path,
                module_name,
                is_system_target,
                is_reload=True,
            )
            if res and res[0]:
                add_log_fn(f"=> Backup module reloaded: {module_name}")
            else:
                reason = (
                    res[1] if isinstance(res, tuple) and len(res) > 1 else "unknown"
                )
                add_log_fn(f"=X Backup reload failed: {reason}")
        except Exception as e:
            add_log_fn(f"=X Backup reload exception: {e}")

    @staticmethod
    async def _edit_with_emoji(
        message,
        text: str,
        parse_mode: str = "html",
        **kwargs,
    ) -> bool:
        try:
            await message.edit(text, parse_mode=parse_mode, **kwargs)
            return True
        except Exception:
            return False

    async def _send_with_emoji(self, chat_id: int | str, text: str, **kwargs) -> Any:
        try:
            if "<emoji" in text:
                text = text.replace("<emoji document_id=", "<tg-emoji emoji-id=")
                text = text.replace("</emoji>", "</tg-emoji>")
            if "<tg-emoji" in text or re.search(r"<[^>]+>", text):
                parse_mode = kwargs.pop("parse_mode", "html")
                return await self.client.send_message(
                    chat_id, text, parse_mode=parse_mode, **kwargs
                )
            else:
                return await self.client.send_message(chat_id, text, **kwargs)
        except Exception as e:
            await self.kernel.handle_error(e, source="send_with_emoji")
            fallback = re.sub(r"<tg-emoji[^>]*>.*?</tg-emoji>", "", text)
            fallback = re.sub(r"<emoji[^>]*>.*?</emoji>", "", fallback)
            fallback = re.sub(r"<[^>]+>", "", fallback)
            return await self.client.send_message(chat_id, fallback, **kwargs)

    @staticmethod
    def _detect_module_type(module: object) -> str:
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

    def _get_source_link(self, module_name: str) -> str:
        source = self.kernel._module_sources.get(module_name)
        if source:
            url = source.get("url")
            repo = source.get("repo")
            if url:
                return f'<blockquote><tg-emoji emoji-id="5411527152212411235">🔗</tg-emoji> Source link {url}</blockquote>'
            elif repo:
                repo = repo.rstrip("/")
                return f'<blockquote><tg-emoji emoji-id="5411527152212411235">🔗</tg-emoji> Source link {repo}/{module_name}.py</blockquote>'
        return ""

    async def _get_inline_bot_username(self) -> str | None:
        username = self.kernel.config.get("inline_bot_username")
        if username:
            return username.lstrip("@")
        if self.kernel.is_bot_available():
            try:
                bot_info = await self.kernel.bot_client.get_me()
                return bot_info.username
            except Exception as e:
                self.log.error(f"Error getting inline bot username: {e}")
        return None

    async def _open_inline_result(self, event, query: str) -> bool:
        bot_username = await self._get_inline_bot_username()
        if not bot_username:
            return False
        results = await self.client.inline_query(bot_username, query)
        if not results:
            return False
        await results[0].click(event.chat_id, reply_to=event.reply_to_msg_id)
        await event.delete()
        return True

    async def _handle_catalog(self, event, query_or_data: str) -> tuple[str, list]:
        try:
            parts = query_or_data.split("_")

            repo_index = 0
            page = 1

            if len(parts) >= 2 and parts[1].isdigit():
                repo_index = int(parts[1])
            if len(parts) >= 3 and parts[2].isdigit():
                page = int(parts[2])

            repos = [self.kernel.default_repo, *self.kernel.repositories]

            if repo_index < 0 or repo_index >= len(repos):
                repo_index = 0

            repo_url = repos[repo_index]
            cache_key = f"catalog:{repo_url}"
            cached = self.kernel.cache.get(cache_key)

            if cached is not None:
                modules, repo_name = cached
            else:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(f"{repo_url}/modules.ini") as resp:
                            modules = (
                                [
                                    l.strip()
                                    for l in (await resp.text()).split("\n")
                                    if l.strip()
                                ]
                                if resp.status == 200
                                else []
                            )
                        async with session.get(f"{repo_url}/name.ini") as resp:
                            repo_name = (
                                (await resp.text()).strip()
                                if resp.status == 200
                                else (
                                    repo_url.split("/")[-2]
                                    if "/" in repo_url
                                    else repo_url
                                )
                            )
                        self.kernel.cache.set(cache_key, (modules, repo_name), ttl=300)
                except Exception:
                    modules = []
                    repo_name = repo_url.split("/")[-2] if "/" in repo_url else repo_url

            per_page = 8
            total_pages = (len(modules) + per_page - 1) // per_page if modules else 1
            page = max(1, min(page, total_pages))
            start_idx = (page - 1) * per_page
            page_modules = modules[start_idx : start_idx + per_page] if modules else []

            msg = (
                self.strings("catalog_title", repo_url=repo_url)
                if repo_index == 0
                else self.strings(
                    "catalog_custom", repo_name=repo_name, repo_url=repo_url
                )
            )
            msg += (
                " | ".join([f"<code>{m}</code>" for m in page_modules])
                if page_modules
                else self.strings["no_modules_catalog"]
            )
            msg += f"\n\n{self.strings('catalog_page', page=page, total_pages=total_pages)}"

            buttons = []
            nav_buttons = []

            if page > 1:
                nav_buttons.append(
                    Button.inline(
                        self.strings["btn_back"],
                        f"catalog_{repo_index}_{page - 1}".encode(),
                        style="primary",
                    )
                )
            if page < total_pages:
                nav_buttons.append(
                    Button.inline(
                        self.strings["btn_next"],
                        f"catalog_{repo_index}_{page + 1}".encode(),
                        style="primary",
                    )
                )
            if nav_buttons:
                buttons.append(nav_buttons)

            if len(repos) > 1:
                buttons.append(
                    [
                        Button.inline(
                            f"{i + 1}", f"catalog_{i}_1".encode(), style="primary"
                        )
                        for i in range(len(repos))
                    ]
                )

            return msg, buttons

        except Exception as e:
            logger.error(f"Ошибка в handle_catalog: {e}")
            import traceback

            traceback.print_exc()
            return self.strings("catalog_error", error=str(e)[:100]), []

    async def _catalog_inline_handler(self, event) -> None:
        try:
            query = event.text or ""
            if not query or query == "catalog":
                query = "catalog_0_1"

            msg, buttons = await self._handle_catalog(event, query)

            builder = (
                event.builder.article(
                    "Catalog", text=msg, buttons=buttons, parse_mode="html"
                )
                if buttons
                else event.builder.article("Catalog", text=msg, parse_mode="html")
            )
            await event.answer([builder])
        except Exception as e:
            logger.error(f"Ошибка в catalog_inline_handler: {e}")

    async def _catalog_callback_handler(self, event) -> None:
        try:
            data_str = (
                event.data.decode("utf-8")
                if isinstance(event.data, bytes)
                else str(event.data)
            )
            msg, buttons = await self._handle_catalog(event, data_str)
            await event.edit(
                msg, buttons=buttons if buttons else None, parse_mode="html"
            )
        except Exception as e:
            logger.error(f"Ошибка в catalog_callback_handler: {e}")
            await event.answer(f"Ошибка: {str(e)[:50]}", alert=True)

    async def _find_repo_matches(
        self,
        module_name: str,
        repos: list[str],
        add_log: Callable | None = None,
    ) -> list[dict]:
        matches = []
        normalized = module_name.lower()

        for i, repo in enumerate(repos):
            try:
                if add_log:
                    add_log(self.strings("log_checking_repo", index=i + 1, repo=repo))
                modules = await self.kernel.get_repo_modules_list(repo)
                if modules and any(name.lower() == normalized for name in modules):
                    repo_name = await self.kernel.get_repo_name(repo)
                    matches.append({"repo_index": i, "repo_name": repo_name})
                    if add_log:
                        add_log(self.strings["log_found_in_repo"])
                elif add_log:
                    add_log(self.strings["log_not_found_in_repo"])
            except Exception as e:
                if add_log:
                    add_log(
                        self.strings("log_repo_error", repo=repo, error=str(e)[:100])
                    )
                await self.kernel.log_error(
                    f"Ошибка поиска модуля {module_name} в репозитории {repo}: {e}"
                )

        return matches

    async def _open_repo_choice_form(
        self,
        event,
        module_name: str,
        send_mode: bool,
        matches: list[dict],
    ) -> bool:
        from core_inline.api.inline import make_cb_button

        session_uuid = str(uuid.uuid4())[:8]
        session_key = f"dlm:{session_uuid}"
        self.kernel._inline._session_put(
            session_key,
            {
                "module_name": module_name,
                "send_mode": send_mode,
                "user_id": event.sender_id,
                "matches": [
                    {"repo_index": item["repo_index"], "repo_name": item["repo_name"]}
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
                        self.kernel,
                        f"{item['repo_index'] + 1}. {clean_name}",
                        self._dlm_repo_session_callback,
                        args=[session_uuid, str(item["repo_index"])],
                        ttl=300,
                    )
                ]
            )
        buttons.append(
            [
                make_cb_button(
                    self.kernel,
                    re.sub(r"<[^>]+>", "", self.strings["dlm_repo_choice_cancel"]),
                    self._dlm_repo_session_callback,
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
        title = self.strings(
            "dlm_repo_choice_title",
            cloud="🧩",
            module_name=module_name,
            action=self.strings[action_key],
        )

        success, _ = await self.kernel.inline_form(
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

    async def _dlm_repo_session_callback(
        self, event: events.CallbackQuery.Event, *args
    ) -> None:
        if not args:
            return

        session_uuid = args[0]
        action = args[1] if len(args) > 1 else ""
        session_key = f"dlm:{session_uuid}"
        select_data = self.kernel._inline._session_get(session_key, pop=True)

        if not select_data:
            await event.answer(self.strings["dlm_repo_choice_expired"], alert=True)
            return

        if action == "cancel":
            await event.edit(
                self.strings["dlm_repo_choice_cancelled"], parse_mode="html"
            )
            return

        if select_data.get("user_id") != event.sender_id:
            await event.answer(self.strings["dlm_repo_choice_expired"], alert=True)
            return

        repo_index = int(action)
        await self._run_dlm_install(
            event,
            select_data["module_name"],
            send_mode=select_data.get("send_mode", False),
            repo_index=repo_index,
        )

    async def _run_dlm_install(
        self,
        event,
        module_or_url: str,
        send_mode: bool = False,
        repo_index: int | None = None,
        preloaded_code: str | None = None,
        preloaded_repo_url: str | None = None,
    ) -> str | None:
        is_url = module_or_url.startswith(
            ("http://", "https://", "raw.githubusercontent.com")
        )
        if is_url:
            if module_or_url.endswith(".py"):
                module_name = os.path.basename(module_or_url)[:-3]
            else:
                module_name = os.path.basename(module_or_url).split("?")[0]
                if "." in module_name:
                    module_name = module_name.split(".")[0]
        else:
            module_name = module_or_url

        cfg = self.get_config()
        force_unload = not (cfg and cfg.get("loader_protect_system", True))
        if cfg and cfg.get("loader_protect_system", True):
            if module_name in self.kernel.system_modules:
                await self._edit_with_emoji(
                    event,
                    self.strings(
                        "system_module_install_attempt",
                        confused=CUSTOM_EMOJI["confused"],
                        module_name=module_name,
                        blocked=CUSTOM_EMOJI["blocked"],
                    ),
                )
                return None

        is_update = (
            module_name in self.kernel.loaded_modules
            or module_name in self.kernel.system_modules
        )
        is_system_target = module_name in self.kernel.system_modules
        old_version = None
        if is_update:
            old_file_path = os.path.join(
                (
                    self.kernel.MODULES_DIR
                    if module_name in self.kernel.system_modules
                    else self.kernel.MODULES_LOADED_DIR
                ),
                f"{module_name}.py",
            )
            old_version = await self.kernel._loader.get_module_version_from_file(
                old_file_path
            )

        install_log: list[str] = []

        def add_log(message: str) -> None:
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] {message}"
            install_log.append(log_entry)
            self.kernel.logger.debug(log_entry)

        try:
            code = preloaded_code
            repo_url = preloaded_repo_url
            msg = None

            def target_message():
                return event

            add_log(
                self.strings(
                    "log_start",
                    action="скачивание" if send_mode else "установку",
                    module_name=module_name,
                )
            )
            add_log(
                self.strings("log_mode", mode="отправка" if send_mode else "установка")
            )
            add_log(
                self.strings("log_type", type="URL" if is_url else "из репозитория")
            )

            if is_url:
                is_archive = self.kernel._loader.is_archive_url(module_or_url)

                if is_archive:
                    add_log(self.strings("log_download_url", url=module_or_url))
                    add_log("Detected archive file, using archive installer")

                    success, msg_txt, extra = (
                        await self.kernel._loader.install_from_archive(
                            module_or_url, module_name
                        )
                    )

                    if success:
                        add_log(f"Archive install success: {msg_txt}")
                        loaded_list = (
                            extra.get("loaded", []) if isinstance(extra, dict) else []
                        )
                        if len(loaded_list) > 1:
                            display_name = f"{len(loaded_list)} модулей"
                            desc = "archive pack"
                        else:
                            display_name = module_name
                            desc = self._module_description(None)

                        await self._edit_with_emoji(
                            event,
                            self.strings(
                                "module_loaded",
                                success=CUSTOM_EMOJI["success"],
                                module_name=display_name,
                                emoji=CUSTOM_EMOJI["idea"],
                                idea=CUSTOM_EMOJI["idea"],
                                description=desc,
                                version="1.0.0",
                                emoji_author=CUSTOM_EMOJI["author"],
                                author="unknown",
                                commands_list="",
                                source_link="",
                            ),
                        )
                        return
                    else:
                        add_log(f"Archive install failed: {msg_txt}")
                        await self._edit_with_emoji(
                            event,
                            self.strings(
                                "module_not_found_repos",
                                warning=CUSTOM_EMOJI["warning"],
                                module_name=msg_txt,
                            ),
                        )
                        return

                try:
                    add_log(self.strings("log_download_url", url=module_or_url))
                    async with aiohttp.ClientSession() as session:
                        async with session.get(module_or_url) as resp:
                            if resp.status == 200:
                                code = await resp.text()
                                add_log(
                                    self.strings(
                                        "log_download_success", status=resp.status
                                    )
                                )
                            else:
                                add_log(
                                    self.strings(
                                        "log_download_failed", status=resp.status
                                    )
                                )
                                await self._edit_with_emoji(
                                    msg or event,
                                    self.strings(
                                        "url_download_error",
                                        warning=CUSTOM_EMOJI["warning"],
                                        status=resp.status,
                                    ),
                                )
                                return
                except Exception as e:
                    add_log(self.strings("log_download_exception", error=str(e)))
                    await self.kernel.handle_error(
                        e, source="install_for_url", event=event
                    )
                    await self._edit_with_emoji(
                        event,
                        self.strings(
                            "url_exception",
                            warning=CUSTOM_EMOJI["warning"],
                            error=str(e)[:100],
                        ),
                    )
                    return

            elif code is None:
                repos = [self.kernel.default_repo, *self.kernel.repositories]
                add_log(self.strings("log_checking_repos", count=len(repos)))

                if repo_index is not None and 0 <= repo_index < len(repos):
                    repo_url = repos[repo_index]
                    add_log(self.strings("log_using_repo", repo=repo_url))
                    code = await self.kernel.download_module_from_repo(
                        repo_url, module_name
                    )
                    add_log(
                        self.strings["log_found_in_repo"]
                        if code
                        else self.strings["log_not_found_in_repo"]
                    )
                else:
                    for i, repo in enumerate(repos):
                        try:
                            add_log(
                                self.strings(
                                    "log_checking_repo", index=i + 1, repo=repo
                                )
                            )
                            code = await self.kernel.download_module_from_repo(
                                repo, module_name
                            )
                            if code:
                                repo_url = repo
                                add_log(self.strings["log_found_in_repo"])
                                break
                            else:
                                add_log(self.strings["log_not_found_in_repo"])
                        except Exception as e:
                            add_log(
                                self.strings(
                                    "log_repo_error", repo=repo, error=str(e)[:100]
                                )
                            )
                            await self.kernel.log_error(
                                f"Ошибка скачивания модуля {module_name} из {repo}: {e}"
                            )

            if not code:
                await self._edit_with_emoji(
                    event,
                    self.strings(
                        "module_not_found_repos",
                        warning=CUSTOM_EMOJI["warning"],
                        module_name=module_name,
                    ),
                )
                return

            metadata = await self.kernel.get_module_metadata(code)
            add_log(self.strings["log_getting_metadata"])
            add_log(self.strings("log_author", author=metadata["author"]))
            add_log(self.strings("log_version", version=metadata["version"]))
            add_log(
                self.strings(
                    "log_description", description=self._module_description(metadata)
                )
            )

            if metadata.get("is_class_style") and metadata.get("class_name"):
                class_name = metadata["class_name"]
                if (
                    class_name in self.kernel.system_modules
                    and cfg
                    and cfg.get("loader_protect_system", True)
                ):
                    await self._edit_with_emoji(
                        event,
                        self.strings(
                            "system_module_install_attempt",
                            confused=CUSTOM_EMOJI["confused"],
                            module_name=class_name,
                            blocked=CUSTOM_EMOJI["blocked"],
                        ),
                    )
                    return

            if send_mode:
                action = self.strings(
                    "downloading_module", download=CUSTOM_EMOJI["download"]
                )
            else:
                if is_update:
                    new_version = metadata["version"]
                    self.kernel.logger.info(
                        f"[loader] update check: {module_name} old={old_version} new={new_version}"
                    )
                    action = (
                        self.strings(
                            "updating_version",
                            reload=CUSTOM_EMOJI["loading"],
                            old_version=old_version,
                            new_version=new_version,
                        )
                        if old_version != new_version
                        else self.strings("updating", reload=CUSTOM_EMOJI["loading"])
                    )
                else:
                    action = self.strings("installing", test=CUSTOM_EMOJI["loading"])

            msg = await event.edit(
                self.strings(
                    "starting_install", action=action, module_name=module_name
                ),
                parse_mode="html",
            )

            file_path = os.path.join(
                (
                    self.kernel.MODULES_DIR
                    if module_name in self.kernel.system_modules
                    else self.kernel.MODULES_LOADED_DIR
                ),
                f"{module_name}.py",
            )

            old_file_backup = None
            old_file_backup_path = None

            new_class_name = metadata.get("class_name")
            for loaded_name, loaded_mod in list(self.kernel.loaded_modules.items()):
                class_instance = getattr(loaded_mod, "_class_instance", None)
                if class_instance is not None:
                    class_display_name = getattr(type(class_instance), "name", None)
                    if (
                        class_display_name == module_name
                        or class_display_name == new_class_name
                    ) and loaded_name != module_name:
                        old_file_path_cls = os.path.join(
                            self.kernel.MODULES_LOADED_DIR, f"{loaded_name}.py"
                        )
                        new_file_path_cls = os.path.join(
                            self.kernel.MODULES_LOADED_DIR, f"{module_name}.py"
                        )
                        if os.path.exists(old_file_path_cls):
                            with open(old_file_path_cls, encoding="utf-8") as f:
                                old_file_backup = f.read()
                            old_file_backup_path = old_file_path_cls
                            os.remove(old_file_path_cls)
                            self.kernel.logger.info(
                                f"[loader] Removed old file {old_file_path_cls} for class module {module_name}"
                            )
                        file_path = new_file_path_cls
                        is_update = True
                        await self.kernel.unregister_module_commands(
                            loaded_name, force=force_unload
                        )
                        break

            if send_mode:
                add_log(self.strings["log_saving_for_send"])
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(code)

                await self._edit_with_emoji(
                    target_message(),
                    self.strings(
                        "sending_module",
                        upload=CUSTOM_EMOJI["upload"],
                        module_name=module_name,
                    ),
                )
                await event.edit(
                    self.strings(
                        "file_sent_caption",
                        file=CUSTOM_EMOJI["file"],
                        module_name=module_name,
                        idea=CUSTOM_EMOJI["idea"],
                        description=self._module_description(metadata),
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
                add_log(self.strings["log_file_sent"])
                os.remove(file_path)
                return

            add_log(self.strings["log_install_mode"])

            dependencies = self.kernel._loader.parse_requires(code)
            if dependencies:
                add_log(self.strings("log_deps_found", deps=", ".join(dependencies)))
                deps_with_emoji = "\n".join(
                    f"{CUSTOM_EMOJI['lib']} {dep}" for dep in dependencies
                )
                await self._edit_with_emoji(
                    target_message(),
                    self.strings(
                        "installing_deps",
                        dependencies=CUSTOM_EMOJI["dependencies"],
                        deps_list=deps_with_emoji,
                    ),
                )
                await self.kernel._loader.install_dependencies_batch(
                    dependencies, log_fn=add_log
                )

            if is_update:
                add_log(self.strings("log_removing_old", module_name=module_name))
                if old_file_backup is None and os.path.exists(file_path):
                    with open(file_path, encoding="utf-8") as f:
                        old_file_backup = f.read()
                    old_file_backup_path = file_path
                await self.kernel.unregister_module_commands(
                    module_name, force=force_unload
                )

            add_log(self.strings("log_saving_file", file_path=file_path))
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(code)

            add_log(self.strings["log_loading_to_kernel"])

            if is_hikka_module(code):
                add_log(self.strings["log_hikka_detected"])
                if not self._allow_hikka_modules():
                    await self._edit_with_emoji(
                        target_message(),
                        self.strings("hikka_disabled", warning=CUSTOM_EMOJI["warning"]),
                    )
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    return
                if not HIKKA_COMPAT:
                    await self._edit_with_emoji(
                        target_message(),
                        self.strings(
                            "hikka_no_compat", warning=CUSTOM_EMOJI["warning"]
                        ),
                    )
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    return

                ok, err, extra = await load_hikka_module(
                    self.kernel, file_path, module_name
                )
                extra = extra or {}
                conflicts = extra.get("conflicts", [])

                if ok:
                    add_log(self.strings["log_module_loaded_kernel"])
                    lang = self.kernel.config.get("language", "ru")
                    commands, aliases_info, descriptions = (
                        self.kernel._loader.get_module_commands(module_name, lang)
                    )
                    emoji = random.choice(RANDOM_EMOJIS)
                    commands_list = self._build_commands_list(
                        module_name,
                        commands,
                        aliases_info,
                        descriptions,
                        metadata,
                        add_log,
                    )

                    conflict_text = ""
                    if conflicts:
                        conflict_text = (
                            f"\n\n⚠️ <b>Command conflicts ({len(conflicts)}):</b>\n"
                        )
                        for cf in conflicts:
                            owner = cf.get("owner") or "unknown"
                            conflict_text += f"<code>{cf['command']}</code> — registered by <code>{owner}</code>\n"

                    self.kernel.logger.info(f"Hikka модуль {module_name} установлен")
                    await self._send_module_loaded(
                        msg or event,
                        metadata,
                        module_name,
                        commands_list + conflict_text,
                        emoji,
                    )
                else:
                    add_log(self.strings("log_install_error", error=err))
                    log_text = "\n".join(install_log)
                    await self._edit_with_emoji(
                        msg,
                        self.strings(
                            "install_failed",
                            blocked=CUSTOM_EMOJI["blocked"],
                            idea=CUSTOM_EMOJI["idea"],
                            log=html.escape(log_text),
                        ),
                    )
                    self._restore_backup_and_cleanup(
                        old_file_backup, old_file_backup_path, file_path, add_log
                    )
                return

            lang = self.kernel.config.get("language", "ru")
            result = await self.kernel.load_module_from_file(
                file_path,
                module_name,
                False,
                source_url=module_or_url if is_url else None,
                source_repo=repo_url if not is_url and repo_url else None,
            )

            result_tuple = result
            if len(result_tuple) >= 3:
                success, message_text, loaded_module_name = result_tuple[:3]
            elif len(result_tuple) == 2:
                success, message_text = result_tuple
                loaded_module_name = module_name
            else:
                success, _message_text, loaded_module_name = (
                    False,
                    "Unknown error",
                    module_name,
                )

            if success:
                add_log(self.strings["log_module_loaded_kernel"])
                self.kernel._module_sources[loaded_module_name] = {
                    "type": "url" if is_url else "repo",
                    "url": module_or_url if is_url else None,
                    "repo": repo_url if not is_url and repo_url else None,
                }

                class_instance = getattr(
                    self.kernel.loaded_modules.get(loaded_module_name),
                    "_class_instance",
                    None,
                )
                display_name = (
                    getattr(type(class_instance), "name", loaded_module_name)
                    if class_instance is not None
                    else loaded_module_name
                )

                commands, aliases_info, descriptions = (
                    self.kernel._loader.get_module_commands(loaded_module_name, lang)
                )
                emoji = random.choice(RANDOM_EMOJIS)
                commands_list = self._build_commands_list(
                    loaded_module_name,
                    commands,
                    aliases_info,
                    descriptions,
                    metadata,
                    add_log,
                )

                self.kernel.logger.info(f"Модуль {loaded_module_name} скачан")
                await self._send_module_loaded(
                    event,
                    metadata,
                    display_name,
                    commands_list,
                    emoji,
                    source_link=self._get_source_link(loaded_module_name),
                )
            else:
                self._restore_backup_and_cleanup(
                    old_file_backup, old_file_backup_path, file_path, add_log
                )
                if is_update:
                    await self._restore_module_after_failed_update(
                        module_name, is_system_target, old_file_backup_path, add_log
                    )
                log_text = "\n".join(install_log)
                await self._edit_with_emoji(
                    target_message(),
                    self.strings(
                        "install_failed",
                        blocked=CUSTOM_EMOJI["blocked"],
                        idea=CUSTOM_EMOJI["idea"],
                        log=html.escape(log_text),
                    ),
                )

        except CommandConflictError as e:
            add_log(self.strings("log_conflict", error=e))
            log_text = "\n".join(install_log)

            if e.conflict_type == "system":
                await self._edit_with_emoji(
                    target_message(),
                    self.strings(
                        "conflict_system_alt",
                        shield=CUSTOM_EMOJI["shield"],
                        command=e.command,
                        log=html.escape(log_text),
                    ),
                )
            elif e.conflict_type == "user":
                await self._edit_with_emoji(
                    target_message(),
                    self.strings(
                        "conflict_user_alt",
                        error=CUSTOM_EMOJI["error"],
                        log=html.escape(log_text),
                    ),
                )

            self._restore_backup_and_cleanup(
                old_file_backup, old_file_backup_path, file_path, add_log
            )
            if is_update:
                await self._restore_module_after_failed_update(
                    module_name, is_system_target, old_file_backup_path, add_log
                )

        except Exception as e:
            add_log(self.strings("log_critical", error=str(e)))
            import traceback

            add_log(self.strings("log_traceback", traceback=traceback.format_exc()))

            log_text = "\n".join(install_log)
            await self._edit_with_emoji(
                msg or event,
                self.strings(
                    "install_failed",
                    blocked=CUSTOM_EMOJI["blocked"],
                    idea=CUSTOM_EMOJI["idea"],
                    log=html.escape(log_text),
                ),
            )
            self._restore_backup_and_cleanup(
                old_file_backup, old_file_backup_path, file_path, add_log
            )
            if is_update:
                await self._restore_module_after_failed_update(
                    module_name, is_system_target, old_file_backup_path, add_log
                )
            self.kernel._module_sources.pop(module_name, None)

    def _build_commands_list(
        self,
        module_name: str,
        commands: list[str],
        aliases_info: dict,
        descriptions: dict,
        metadata: dict,
        add_log: Callable,
    ) -> str:
        commands_list = ""
        if not commands:
            return commands_list

        add_log(self.strings("log_commands_found", count=len(commands)))

        for cmd in commands:
            cmd_desc = (
                descriptions.get(cmd)
                or (metadata or {}).get("commands", {}).get(cmd)
                or self.strings("no_cmd_desc", no_cmd=CUSTOM_EMOJI["no_cmd"])
            )
            command_line = self.strings(
                "command_line",
                crystal=CUSTOM_EMOJI["crystal"],
                prefix=self.get_prefix(),
                cmd=cmd,
                desc=cmd_desc,
            )

            if cmd in aliases_info:
                aliases = aliases_info[cmd]
                if isinstance(aliases, str):
                    aliases = [aliases]
                if aliases:
                    alias_text = ", ".join(
                        [f"<code>{self.get_prefix()}{a}</code>" for a in aliases]
                    )
                    command_line += self.strings("aliases_text", alias_text=alias_text)
                    add_log(
                        self.strings(
                            "log_aliases_found", cmd=cmd, aliases=", ".join(aliases)
                        )
                    )

            commands_list += command_line + "\n"

        # Inline commands
        inline_commands = self.kernel.get_module_inline_commands(module_name)
        if inline_commands:
            inline_emoji = '<tg-emoji emoji-id="5372981976804366741">🤖</tg-emoji>'
            bot_username = self.kernel.config.get("inline_bot_username", "bot")
            for cmd, desc in inline_commands:
                if desc:
                    commands_list += f"{inline_emoji} <code>@{bot_username} {cmd}</code> – <b>{desc}</b>\n"
                else:
                    commands_list += (
                        f"{inline_emoji} <code>@{bot_username} {cmd}</code>\n"
                    )

        return commands_list

    async def _send_module_loaded(
        self,
        message,
        metadata: dict,
        display_name: str,
        commands_list: str,
        emoji: str,
        source_link: str = "",
    ) -> None:
        cfg = self.get_config()
        show_banners = cfg.get("loader_show_banners", False) if cfg else False
        banner_url = metadata.get("banner_url") if metadata else None

        final_msg = self.strings(
            "module_loaded",
            success=CUSTOM_EMOJI["success"],
            module_name=display_name,
            emoji=emoji,
            idea=CUSTOM_EMOJI["idea"],
            description=self._module_description(metadata),
            version=(metadata or {}).get("version", "?"),
            author=(metadata or {}).get("author", "unknown"),
            emoji_author=CUSTOM_EMOJI["author"],
            commands_list=commands_list,
            source_link=source_link,
        )

        if (
            show_banners
            and banner_url
            and banner_url.startswith(("http://", "https://"))
        ):
            try:
                media = InputMediaWebPage(banner_url, optional=True)
                await message.edit(
                    final_msg, file=media, parse_mode="html", invert_media=True
                )
                return

            except Exception as e:
                self.log.error(f"Banner edit error: {e}")

        await self.edit(message, final_msg, as_html=True)

    @command(
        "iload",
        alias="im",
        doc_en="<reply> load module from reply",
        doc_ru="<ответ> загрузить модуль из ответа",
    )
    async def cmd_iload(self, event) -> None:
        if not event.is_reply:
            await self._edit_with_emoji(
                event, self.strings("reply_to_py", warning=CUSTOM_EMOJI["warning"])
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

        if not reply.document or not file_name:
            await self._edit_with_emoji(
                event, self.strings("not_py_file", warning=CUSTOM_EMOJI["warning"])
            )
            return

        install_log: list[str] = []

        def add_log(message: str) -> None:
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] {message}"
            install_log.append(log_entry)
            self.kernel.logger.debug(log_entry)

        is_archive = file_name.lower().endswith((".zip", ".tar.gz", ".tgz", ".tar"))

        if is_archive:
            add_log(f"Detected archive file: {file_name}")

            temp_dir = os.path.join(
                self.kernel.MODULES_LOADED_DIR, "_temp_iload_archive"
            )
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            os.makedirs(temp_dir, exist_ok=True)

            try:
                archive_path = os.path.join(temp_dir, file_name)
                await reply.download_media(archive_path)
                add_log(f"Archive downloaded to {archive_path}")

                with open(archive_path, "rb") as f:
                    archive_bytes = f.read()

                result = await self.kernel._loader._archive_mgr.extract(
                    archive_bytes, temp_dir
                )
                if not result.success:
                    await self._edit_with_emoji(
                        event,
                        f"{CUSTOM_EMOJI['error']} <b>Archive extraction failed:</b> {result.error}",
                    )
                    return

                add_log(
                    f"Archive extracted, type={result.pack_type}, modules={[m.name for m in result.modules]}"
                )

                module_name = os.path.splitext(file_name)[0]
                if result.metadata and result.metadata.name:
                    module_name = result.metadata.name

                cfg = self.get_config()
                protect_system = cfg and cfg.get("loader_protect_system", True)

                if protect_system and module_name in self.kernel.system_modules:
                    await self._edit_with_emoji(
                        event,
                        self.strings(
                            "system_module_install_attempt",
                            confused=CUSTOM_EMOJI["confused"],
                            blocked=CUSTOM_EMOJI["blocked"],
                            module_name=module_name,
                        ),
                    )
                    return

                deps = []
                if result.metadata and result.metadata.dependencies:
                    deps = result.metadata.dependencies
                    add_log(f"Archive dependencies: {deps}")
                    for dep in deps:
                        bare = re.split(r"[>=<!]", dep)[0].strip()
                        try:
                            __import__(bare.replace("-", "_"))
                        except ImportError:
                            ok, msg_txt = await self.kernel._loader.install_dependency(
                                bare
                            )
                            add_log(
                                f"Installed dependency: {dep}"
                                if ok
                                else f"Failed to install {dep}: {msg_txt}"
                            )

                target_dir = self.kernel.MODULES_LOADED_DIR
                loaded_modules: list[str] = []

                if result.pack_type == "single":
                    main_mod = next(
                        (m for m in result.modules if m.is_main), result.modules[0]
                    )
                    source_file = os.path.join(temp_dir, main_mod.file_path)

                    with open(source_file, encoding="utf-8") as f:
                        main_code = f.read()

                    has_local_import = (
                        "from . import" in main_code or "from .lib import" in main_code
                    )

                    if has_local_import:
                        module_dir = os.path.join(target_dir, module_name)
                        if os.path.exists(module_dir):
                            shutil.rmtree(module_dir)
                        os.makedirs(module_dir, exist_ok=True)

                        for root, _dirs, files in os.walk(temp_dir):
                            rel_dir = os.path.relpath(root, temp_dir)
                            if rel_dir == ".":
                                continue
                            target_subdir = os.path.join(module_dir, rel_dir)
                            os.makedirs(target_subdir, exist_ok=True)
                            for fname_item in files:
                                if fname_item.endswith(".py"):
                                    shutil.copy2(
                                        os.path.join(root, fname_item),
                                        os.path.join(target_subdir, fname_item),
                                    )

                        main_in_package = os.path.join(module_dir, "__init__.py")
                        with open(main_in_package, "w") as f:
                            content = main_code
                            content = re.sub(
                                r"from \.([^\s]+) import",
                                f"from {module_name}.\\1 import",
                                content,
                            )
                            content = re.sub(
                                r"from \. import", f"from {module_name} import", content
                            )
                            f.write(content)

                        if target_dir not in sys.path:
                            sys.path.insert(0, target_dir)

                        res = await self.kernel._loader.load_module_from_file(
                            main_in_package, module_name, False
                        )
                        success = res[0]
                        msg_txt = res[1] if len(res) >= 2 else ""
                    else:
                        target_file = os.path.join(target_dir, f"{module_name}.py")
                        shutil.copy2(source_file, target_file)
                        res = await self.kernel._loader.load_module_from_file(
                            target_file, module_name, False
                        )
                        success = res[0]
                        msg_txt = res[1] if len(res) >= 2 else ""

                    if success:
                        loaded_modules.append(module_name)
                        self.kernel._module_sources[module_name] = {
                            "type": "archive",
                            "pack_type": "single",
                        }
                    else:
                        await self._edit_with_emoji(
                            event,
                            f"{CUSTOM_EMOJI['error']} <b>Failed to load module:</b> {msg_txt}",
                        )
                        return
                else:
                    if protect_system:
                        system_conflicts = [
                            mod.name
                            for mod in result.modules
                            if mod.name in self.kernel.system_modules
                        ]
                        if system_conflicts:
                            await self._edit_with_emoji(
                                event,
                                f"{CUSTOM_EMOJI['confused']} <b>System module conflict:</b> {', '.join(system_conflicts)}",
                            )
                            return

                    failed_modules: list[str] = []
                    for mod in result.modules:
                        target_file = os.path.join(target_dir, f"{mod.name}.py")
                        source_file = os.path.join(temp_dir, mod.file_path)
                        if os.path.exists(source_file):
                            shutil.copy2(source_file, target_file)
                            res = await self.kernel._loader.load_module_from_file(
                                target_file, mod.name, False
                            )
                            success = res[0]
                            msg_txt = res[1] if len(res) >= 2 else ""
                            if success:
                                loaded_modules.append(mod.name)
                                self.kernel._module_sources[mod.name] = {
                                    "type": "archive",
                                    "pack_type": "pack",
                                }
                            else:
                                failed_modules.append(f"{mod.name}: {msg_txt}")
                                add_log(f"Failed to load {mod.name}: {msg_txt}")

                await self.kernel.save_module_sources()

                lang = self.kernel.config.get("language", "ru")
                commands, aliases_info, descriptions = (
                    self.kernel._loader.get_module_commands(module_name, lang)
                )

                if result.pack_type == "single":
                    code_for_meta = (
                        main_code if has_local_import else open(source_file).read()
                    )
                    metadata = await self.kernel.get_module_metadata(code_for_meta)
                else:
                    metadata = await self.kernel.get_module_metadata("")

                commands_list = ""
                for cmd in commands:
                    cmd_desc = (
                        descriptions.get(cmd)
                        or metadata["commands"].get(cmd)
                        or self.strings("no_cmd_desc", no_cmd=CUSTOM_EMOJI["no_cmd"])
                    )
                    commands_list += (
                        self.strings(
                            "command_line",
                            crystal=CUSTOM_EMOJI["crystal"],
                            prefix=self.get_prefix(),
                            cmd=cmd,
                            desc=cmd_desc,
                        )
                        + "\n"
                    )

                await self._edit_with_emoji(
                    event,
                    self.strings(
                        "module_loaded",
                        success=CUSTOM_EMOJI["success"],
                        module_name=", ".join(loaded_modules),
                        emoji=CUSTOM_EMOJI["idea"],
                        idea=CUSTOM_EMOJI["idea"],
                        description=self._module_description(metadata),
                        version=metadata["version"],
                        emoji_author=CUSTOM_EMOJI["author"],
                        author=metadata.get("author", "unknown"),
                        commands_list=commands_list,
                        source_link=self._get_source_link(module_name),
                    ),
                )
                return

            except Exception as e:
                await self.kernel.handle_error(e, source="iload_archive", event=event)
                await self._edit_with_emoji(
                    event,
                    f"{CUSTOM_EMOJI['error']} <b>Archive install error:</b> {str(e)[:200]}",
                )
                return
            finally:
                if os.path.exists(temp_dir):
                    try:
                        shutil.rmtree(temp_dir)
                    except Exception:
                        pass

        if not file_name.endswith(".py"):
            await self._edit_with_emoji(
                event, self.strings("not_py_file", warning=CUSTOM_EMOJI["warning"])
            )
            return

        module_name = file_name[:-3]

        install_log = []

        def add_log(message: str) -> None:
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] {message}"
            install_log.append(log_entry)
            self.kernel.logger.debug(log_entry)

        cfg = self.get_config()
        force_unload = not (cfg and cfg.get("loader_protect_system", True))

        if cfg and cfg.get("loader_protect_system", True):
            if module_name in self.kernel.system_modules:
                await self._edit_with_emoji(
                    event,
                    self.strings(
                        "system_module_update_attempt",
                        confused=CUSTOM_EMOJI["confused"],
                        module_name=module_name,
                        blocked=CUSTOM_EMOJI["blocked"],
                    ),
                )
                return

        is_update = (
            module_name in self.kernel.loaded_modules
            or module_name in self.kernel.system_modules
        )
        is_system_target = module_name in self.kernel.system_modules

        class_instance = getattr(
            self.kernel.loaded_modules.get(module_name), "_class_instance", None
        )
        if class_instance is not None:
            existing_class_name = getattr(type(class_instance), "name", None)
            if existing_class_name:
                is_update = True
                module_name = existing_class_name

        old_version = None
        old_file_backup = None
        old_file_backup_path = None
        msg = event

        if is_update:
            old_file_path = self.kernel._loader.get_module_path(module_name)
            old_version = await self.kernel._loader.get_module_version_from_file(
                old_file_path
            )
            self.kernel.logger.info(
                f"[loader] BEFORE download - old_file={old_file_path} old_version={old_version}"
            )

        file_path = self.kernel._loader.get_module_path(module_name)

        try:
            add_log(self.strings("log_downloading", file_path=file_path))
            await reply.download_media(file_path)
            add_log(self.strings["log_downloaded"])

            with open(file_path, encoding="utf-8") as f:
                code = f.read()
            add_log(self.strings["log_file_read"])

            add_log(self.strings["log_getting_metadata"])
            metadata = await self.kernel.get_module_metadata(code)

            new_class_name = metadata.get("class_name")
            for loaded_name, loaded_mod in list(self.kernel.loaded_modules.items()):
                class_instance = getattr(loaded_mod, "_class_instance", None)
                if class_instance is not None:
                    class_display_name = getattr(type(class_instance), "name", None)
                    if (
                        class_display_name == module_name
                        or (
                            new_class_name is not None
                            and class_display_name == new_class_name
                        )
                    ) and loaded_name != module_name:
                        old_file_path_cls = self.kernel._loader.get_module_path(
                            loaded_name
                        )
                        if os.path.exists(old_file_path_cls):
                            with open(old_file_path_cls, encoding="utf-8") as f:
                                old_file_backup = f.read()
                            old_file_backup_path = old_file_path_cls
                            os.remove(old_file_path_cls)
                            self.kernel.logger.info(
                                f"[loader] Removed old file {old_file_path_cls} for class module {class_display_name}"
                            )
                        target_name = (
                            new_class_name or class_display_name or module_name
                        )
                        file_path = self.kernel._loader.get_module_path(target_name)
                        self.kernel.logger.info(
                            f"[loader] Using path {file_path} for class module {target_name}"
                        )
                        is_update = True
                        break

            add_log(self.strings("log_author", author=metadata["author"]))
            add_log(self.strings("log_version", version=metadata["version"]))
            add_log(
                self.strings(
                    "log_description", description=self._module_description(metadata)
                )
            )

            if metadata.get("is_class_style") and metadata.get("class_name"):
                class_name = metadata["class_name"]
                if (
                    class_name in self.kernel.system_modules
                    and cfg
                    and cfg.get("loader_protect_system", True)
                ):
                    await self._edit_with_emoji(
                        event,
                        self.strings(
                            "system_module_install_attempt",
                            confused=CUSTOM_EMOJI["confused"],
                            module_name=class_name,
                            blocked=CUSTOM_EMOJI["blocked"],
                        ),
                    )
                    self._restore_backup_and_cleanup(
                        old_file_backup, old_file_backup_path, file_path, add_log
                    )
                    return
                if not is_update:
                    for loaded_name, loaded_mod in list(
                        self.kernel.loaded_modules.items()
                    ):
                        class_instance = getattr(loaded_mod, "_class_instance", None)
                        if class_instance is not None:
                            existing_class = getattr(type(class_instance), "name", None)
                            if existing_class == class_name:
                                old_file_path_cls = self.kernel._loader.get_module_path(
                                    loaded_name
                                )
                                if os.path.exists(old_file_path_cls):
                                    if old_file_backup is None:
                                        with open(
                                            old_file_path_cls, encoding="utf-8"
                                        ) as f:
                                            old_file_backup = f.read()
                                        old_file_backup_path = old_file_path_cls
                                    os.remove(old_file_path_cls)
                                    self.kernel.logger.info(
                                        f"[loader] Removed old file {old_file_path_cls} for class module {class_name}"
                                    )
                                is_update = True
                                await self.kernel.unregister_module_commands(
                                    loaded_name, force=force_unload
                                )
                                self.kernel.logger.info(
                                    f"[loader] Detected update via class name match: {class_name}"
                                )
                                break

            if is_update:
                new_version = metadata["version"]
                self.kernel.logger.info(
                    f"[loader] update check: {module_name} old={old_version} new={new_version}"
                )
                action = (
                    self.strings(
                        "updating_version",
                        reload=CUSTOM_EMOJI["loading"],
                        old_version=old_version,
                        new_version=new_version,
                    )
                    if old_version != new_version
                    else self.strings("updating", reload=CUSTOM_EMOJI["loading"])
                )
            else:
                action = self.strings("installing", test=CUSTOM_EMOJI["loading"])

            msg = await event.edit(
                self.strings("starting_install", action=action), parse_mode="html"
            )
            add_log(
                self.strings(
                    "log_start",
                    action="обновление" if is_update else "установку",
                    module_name=module_name,
                )
            )
            add_log(self.strings("log_filename", filename=file_name))

            await self._mcub_handler()
            add_log(self.strings["log_checking_compatibility"])

            dependencies = self.kernel._loader.parse_requires(code)
            if dependencies:
                add_log(self.strings("log_deps_found", deps=", ".join(dependencies)))

            if is_hikka_module(code):
                add_log(self.strings["log_hikka_detected"])
                if not self._allow_hikka_modules():
                    await self._edit_with_emoji(
                        msg,
                        self.strings("hikka_disabled", warning=CUSTOM_EMOJI["warning"]),
                    )
                    self._restore_backup_and_cleanup(
                        old_file_backup, old_file_backup_path, file_path, add_log
                    )
                    return
                if not HIKKA_COMPAT:
                    await self._edit_with_emoji(
                        msg,
                        self.strings(
                            "hikka_no_compat", warning=CUSTOM_EMOJI["warning"]
                        ),
                    )
                    self._restore_backup_and_cleanup(
                        old_file_backup, old_file_backup_path, file_path, add_log
                    )
                    return

                await self._edit_with_emoji(
                    msg,
                    self.strings(
                        "starting_install",
                        action=self.strings("installing", test=CUSTOM_EMOJI["loading"]),
                    ),
                )

            if dependencies:
                deps_with_emoji = "\n".join(
                    f"{CUSTOM_EMOJI['lib']} {dep}" for dep in dependencies
                )
                await self._edit_with_emoji(
                    msg,
                    self.strings(
                        "installing_deps",
                        dependencies=CUSTOM_EMOJI["dependencies"],
                        deps_list=deps_with_emoji,
                    ),
                )
                await self.kernel._loader.install_dependencies_batch(
                    dependencies, log_fn=add_log
                )

            if is_update:
                add_log(self.strings("log_removing_old", module_name=module_name))
                if old_file_backup is None and os.path.exists(file_path):
                    with open(file_path, encoding="utf-8") as f:
                        old_file_backup = f.read()
                    old_file_backup_path = file_path
                await self.kernel.unregister_module_commands(
                    module_name, force=force_unload
                )

            add_log(self.strings("log_loading_module", module_name=module_name))
            result = await self.kernel.load_module_from_file(
                file_path,
                module_name,
                is_system_target,
                source_url=None,
                source_repo=None,
            )
            success = result[0]
            message_text = result[1] if len(result) >= 2 else ""
            loaded_module_name = result[2] if len(result) >= 3 else module_name

            if success:
                add_log(self.strings["log_module_loaded"])
                self.kernel._module_sources[loaded_module_name] = {"type": "local"}

                loaded_obj = self.kernel.loaded_modules.get(
                    loaded_module_name
                ) or self.kernel.system_modules.get(loaded_module_name)
                class_instance = getattr(loaded_obj, "_class_instance", None)
                display_name = (
                    getattr(type(class_instance), "name", loaded_module_name)
                    if class_instance is not None
                    else loaded_module_name
                )

                lang = self.kernel.config.get("language", "ru")
                commands, aliases_info, descriptions = (
                    self.kernel._loader.get_module_commands(loaded_module_name, lang)
                )
                emoji = random.choice(RANDOM_EMOJIS)
                commands_list = self._build_commands_list(
                    loaded_module_name,
                    commands,
                    aliases_info,
                    descriptions,
                    metadata,
                    add_log,
                )

                self.kernel.logger.info(f"Модуль {display_name} установлен")
                self.strings(
                    "module_loaded",
                    success=CUSTOM_EMOJI["success"],
                    module_name=display_name,
                    emoji=emoji,
                    idea=CUSTOM_EMOJI["idea"],
                    description=self._module_description(metadata),
                    version=(metadata or {}).get("version", "?"),
                    author=(metadata or {}).get("author", "unknown"),
                    emoji_author=CUSTOM_EMOJI["author"],
                    commands_list=commands_list,
                    source_link=self._get_source_link(loaded_module_name),
                )
                await self._send_module_loaded(
                    msg,
                    metadata,
                    display_name,
                    commands_list,
                    emoji,
                    source_link=self._get_source_link(loaded_module_name),
                )
            else:
                add_log(self.strings("log_install_error", error=message_text))
                log_text = "\n".join(install_log)
                await self._edit_with_emoji(
                    msg,
                    self.strings(
                        "install_failed",
                        blocked=CUSTOM_EMOJI["blocked"],
                        idea=CUSTOM_EMOJI["idea"],
                        log=html.escape(log_text),
                    ),
                )
                self._restore_backup_and_cleanup(
                    old_file_backup, old_file_backup_path, file_path, add_log
                )

        except CommandConflictError as e:
            add_log(self.strings("log_conflict", error=e))
            log_text = "\n".join(install_log)

            if e.conflict_type == "system":
                await self._edit_with_emoji(
                    msg,
                    self.strings(
                        "conflict_system",
                        shield=CUSTOM_EMOJI["shield"],
                        prefix=self.get_prefix(),
                        command=e.command,
                        log=html.escape(log_text),
                    ),
                )
            elif e.conflict_type == "user":
                owner_module = self.kernel.command_owners.get(e.command, "unknown")
                await self._edit_with_emoji(
                    msg,
                    self.strings(
                        "conflict_user",
                        error=CUSTOM_EMOJI["error"],
                        prefix=self.get_prefix(),
                        command=e.command,
                        owner_module=owner_module,
                        log=html.escape(log_text),
                    ),
                )
            self._restore_backup_and_cleanup(
                old_file_backup, old_file_backup_path, file_path, add_log
            )

        except Exception as e:
            add_log(self.strings("log_critical", error=str(e)))
            import traceback

            add_log(self.strings("log_traceback", traceback=traceback.format_exc()))
            log_text = "\n".join(install_log)
            await self._edit_with_emoji(
                msg,
                self.strings(
                    "install_failed",
                    blocked=CUSTOM_EMOJI["blocked"],
                    idea=CUSTOM_EMOJI["idea"],
                    log=html.escape(log_text),
                ),
            )
            await self.kernel.handle_error(
                e, source="install_module_handler", event=event
            )
            self._restore_backup_and_cleanup(
                old_file_backup, old_file_backup_path, file_path, add_log
            )

        return None

    @command(
        "dlm",
        doc_en="<URL/[-send] [name]/[-list] [name/None]> download and install module from URL or repo",
        doc_ru="<URL/[-send] [name]/[-list] [name/None]> скачать и установить модуль из URL или репозитория",
    )
    async def cmd_dlm(self, event) -> None:
        args = event.text.split()

        if len(args) < 2:
            try:
                if await self._open_inline_result(event, "catalog"):
                    return
            except Exception as e:
                self.kernel.logger.error(f"Error calling inline catalog: {e}")

            await self._edit_with_emoji(
                event,
                self.strings(
                    "dlm_usage",
                    warning=CUSTOM_EMOJI["warning"],
                    prefix=self.get_prefix(),
                ),
            )
            return

        await self._edit_with_emoji(
            event, self.strings("wait", wait=CUSTOM_EMOJI["wait"])
        )

        if args[1] == "-list":
            if len(args) == 2:
                await self._edit_with_emoji(
                    event,
                    self.strings("dlm_list_loading", loading=CUSTOM_EMOJI["loading"]),
                )
                repos = [self.kernel.default_repo, *self.kernel.repositories]
                message_lines = []
                errors = []

                for i, repo in enumerate(repos):
                    try:
                        modules = await self.kernel.get_repo_modules_list(repo)
                        repo_name = await self.kernel.get_repo_name(repo)
                        if modules:
                            message_lines.append(
                                f"<b>{repo_name}</b>: {' | '.join(modules)}"
                            )
                        else:
                            errors.append(f"{i + 1}. {repo_name}: пустой список")
                    except Exception as e:
                        errors.append(f"{i + 1}. {repo}: ошибка - {str(e)[:50]}")

                if message_lines:
                    final_msg = self.strings(
                        "dlm_list_title",
                        folder=CUSTOM_EMOJI["folder"],
                        list="\n".join(message_lines),
                    )
                    if errors:
                        final_msg += self.strings(
                            "dlm_list_errors",
                            warning=CUSTOM_EMOJI["warning"],
                            errors="<br>".join(errors),
                        )
                else:
                    final_msg = self.strings(
                        "dlm_list_failed", warning=CUSTOM_EMOJI["warning"]
                    )
                    if errors:
                        final_msg += f"\n<blockquote expandable>{'<br>'.join(errors)}</blockquote>"

                await self._edit_with_emoji(event, final_msg)
                return
            else:
                module_name = args[2]
                msg = await event.edit(
                    self.strings(
                        "dlm_searching",
                        loading=CUSTOM_EMOJI["loading"],
                        module_name=module_name,
                    ),
                    parse_mode="html",
                )
                repos = [self.kernel.default_repo, *self.kernel.repositories]
                found = False

                for repo in repos:
                    try:
                        code = await self.kernel.download_module_from_repo(
                            repo, module_name
                        )
                        if code:
                            found = True
                            metadata = await self.kernel.get_module_metadata(code)
                            await self._edit_with_emoji(
                                msg,
                                self.strings(
                                    "module_info",
                                    file=CUSTOM_EMOJI["file"],
                                    module_name=module_name,
                                    idea=CUSTOM_EMOJI["idea"],
                                    description=self._module_description(metadata),
                                    crystal=CUSTOM_EMOJI["crystal"],
                                    version=metadata["version"],
                                    angel=CUSTOM_EMOJI["angel"],
                                    author=metadata["author"],
                                    folder=CUSTOM_EMOJI["folder"],
                                    size=len(code.encode("utf-8")),
                                    cloud=CUSTOM_EMOJI["cloud"],
                                    repo=repo,
                                ),
                            )
                            break
                    except Exception as e:
                        await self.kernel.log_error(
                            f"Ошибка поиска модуля {module_name} в {repo}: {e}"
                        )

                if not found:
                    await self._edit_with_emoji(
                        msg,
                        self.strings(
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
                await self._edit_with_emoji(
                    event,
                    self.strings(
                        "dlm_send_usage",
                        warning=CUSTOM_EMOJI["warning"],
                        prefix=self.get_prefix(),
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

        is_url = module_or_url.startswith(
            ("http://", "https://", "raw.githubusercontent.com")
        )

        if not is_url and repo_index is None:
            repos = [self.kernel.default_repo, *self.kernel.repositories]
            matches = await self._find_repo_matches(module_or_url, repos)

            if len(matches) > 1:
                opened = await self._open_repo_choice_form(
                    event, module_or_url, send_mode, matches
                )
                if opened:
                    return

            if len(matches) == 1:
                repo_index = matches[0]["repo_index"]

        await self._run_dlm_install(
            event, module_or_url, send_mode=send_mode, repo_index=repo_index
        )

    @command(
        "um",
        doc_en="<n> unload module by name",
        doc_ru="<имя> выгрузить модуль по имени",
    )
    async def cmd_um(self, event) -> None:
        args = event.text.split()
        if len(args) < 2:
            await self._edit_with_emoji(
                event,
                self.strings(
                    "um_usage",
                    warning=CUSTOM_EMOJI["warning"],
                    prefix=self.get_prefix(),
                ),
            )
            return

        module_name = args[1]
        actual_name, _ = self.kernel._loader.find_module_case_insensitive(module_name)
        if actual_name is None:
            await self._edit_with_emoji(
                event,
                self.strings(
                    "module_not_found_um",
                    warning=CUSTOM_EMOJI["warning"],
                    module_name=module_name,
                ),
            )
            return

        module_name = actual_name
        cfg = self.get_config()
        force_unload = not (cfg and cfg.get("loader_protect_system", True))

        try:
            await self.kernel.unregister_module_commands(
                module_name, force=force_unload
            )
        except PermissionError:
            await self._edit_with_emoji(
                event,
                self.strings(
                    "system_module_unload_attempt",
                    confused=CUSTOM_EMOJI["confused"],
                    blocked=CUSTOM_EMOJI["blocked"],
                    module_name=module_name,
                ),
            )
            return

        instance = self.kernel.loaded_modules.get(module_name)
        if instance and getattr(instance, "_hikka_compat", False):
            await unload_hikka_module(self.kernel, module_name)
        else:
            commands_to_remove = [
                cmd
                for cmd, owner in self.kernel.command_owners.items()
                if owner == module_name
            ]
            try:
                await self.kernel.unregister_module_commands(
                    module_name, force=force_unload
                )
            except PermissionError:
                await self._edit_with_emoji(
                    event,
                    self.strings(
                        "system_module_unload_attempt",
                        confused=CUSTOM_EMOJI["confused"],
                        blocked=CUSTOM_EMOJI["blocked"],
                        module_name=module_name,
                    ),
                )
                return
            self.kernel._loader.remove_module_aliases(module_name, commands_to_remove)

        file_path = self.kernel._loader.get_module_path(module_name)
        if os.path.exists(file_path):
            os.remove(file_path)

        package_dir = os.path.join(self.kernel.MODULES_LOADED_DIR, module_name)
        if os.path.isdir(package_dir):
            shutil.rmtree(package_dir)

        for mod in list(sys.modules.keys()):
            if mod == module_name or mod.startswith(f"{module_name}."):
                del sys.modules[mod]

        if module_name in self.kernel.loaded_modules:
            del self.kernel.loaded_modules[module_name]
        if module_name in self.kernel.system_modules:
            del self.kernel.system_modules[module_name]

        await self._log_to_bot(f"Модуль {module_name} удалён")
        await self._edit_with_emoji(
            event,
            self.strings(
                "module_unloaded",
                success=CUSTOM_EMOJI["success"],
                module_name=module_name,
            ),
        )
        self.kernel._module_sources.pop(module_name, None)
        await self.kernel.save_module_sources()

    @command(
        "unlm",
        doc_en="<n> unload module as file",
        doc_ru="<имя> выгрузить модуль виде файл",
    )
    async def cmd_unlm(self, event) -> None:
        args = event.text.split()
        if len(args) < 2:
            await self._edit_with_emoji(
                event,
                self.strings(
                    "unlm_usage",
                    warning=CUSTOM_EMOJI["warning"],
                    prefix=self.get_prefix(),
                ),
            )
            return

        module_name = args[1]
        actual_name, _ = self.kernel._loader.find_module_case_insensitive(module_name)
        if actual_name is None:
            await self._edit_with_emoji(
                event,
                self.strings(
                    "module_not_found_um",
                    warning=CUSTOM_EMOJI["warning"],
                    module_name=module_name,
                ),
            )
            return

        module_name = actual_name
        file_path = self.kernel._loader.get_module_path(module_name)

        if not os.path.exists(file_path):
            await self._edit_with_emoji(
                event,
                self.strings("module_file_not_found", warning=CUSTOM_EMOJI["warning"]),
            )
            return

        await self._edit_with_emoji(
            event,
            self.strings(
                "uploading_module",
                upload=CUSTOM_EMOJI["upload"],
                module_name=module_name,
            ),
        )
        await event.edit(
            self.strings(
                "file_upload_caption",
                file=CUSTOM_EMOJI["file"],
                module_name=module_name,
                prefix=self.get_prefix(),
                source_link=self._get_source_link(module_name),
            ),
            parse_mode="html",
            file=file_path,
        )

    @command(
        "reload",
        doc_en="<name/None> reload module(s)",
        doc_ru="<имя/нечего> перезагрузить модуль или модули",
    )
    async def cmd_reload(self, event) -> None:
        args = event.text.split()
        self.kernel.dedupe_event_builders(reason="reload_command_start_precheck")
        self.kernel.ensure_core_message_handlers(reason="reload_command_start")
        self.kernel.ensure_registered_module_handlers(reason="reload_command_start")
        self.kernel.logger.debug(
            "[reload] request text=%r loaded=%r system=%r",
            event.text,
            list(self.kernel.loaded_modules.keys()),
            list(self.kernel.system_modules.keys()),
        )

        if len(args) < 2:
            # Reload all
            modules_to_reload = list(self.kernel.loaded_modules.keys())
            if not modules_to_reload:
                self.kernel.logger.debug("[reload] no-loaded-modules")
                await self._edit_with_emoji(
                    event, self.strings("no_modules", folder=CUSTOM_EMOJI["folder"])
                )
                return

            msg = await event.edit(
                self.strings("reload_all", reload=CUSTOM_EMOJI["reload"]),
                parse_mode="html",
            )

            results: list[str] = []
            failed: list[str] = []

            cfg = self.get_config()
            force_unload = not (cfg and cfg.get("loader_protect_system", True))

            for module_name in modules_to_reload:
                self.kernel.logger.debug(
                    "[reload] reloading-from-bulk module=%r", module_name
                )

                file_path = os.path.join(
                    (
                        self.kernel.MODULES_DIR
                        if module_name in self.kernel.system_modules
                        else self.kernel.MODULES_LOADED_DIR
                    ),
                    f"{module_name}.py",
                )

                if not os.path.exists(file_path):
                    self.kernel.logger.debug(
                        "[reload] missing-file bulk module=%r file=%r",
                        module_name,
                        file_path,
                    )
                    failed.append(module_name)
                    continue

                if module_name in sys.modules:
                    del sys.modules[module_name]

                try:
                    await self.kernel.unregister_module_commands(
                        module_name, force=force_unload
                    )
                except PermissionError:
                    self.kernel.logger.debug(
                        "[reload] skipped-system-module module=%r", module_name
                    )
                    continue

                if module_name in self.kernel.loaded_modules:
                    del self.kernel.loaded_modules[module_name]

                old_source = self.kernel._module_sources.get(module_name)
                result = await self.kernel.load_module_from_file(
                    file_path,
                    module_name,
                    False,
                    is_reload=True,
                    source_url=old_source.get("url") if old_source else None,
                    source_repo=old_source.get("repo") if old_source else None,
                )
                success = result[0]
                self.kernel.dedupe_event_builders(
                    reason=f"reload_bulk_after_{module_name}"
                )
                self.kernel.ensure_core_message_handlers(
                    reason=f"reload_bulk_after_{module_name}"
                )
                self.kernel.ensure_registered_module_handlers(
                    reason=f"reload_bulk_after_{module_name}"
                )

                if success:
                    results.append(module_name)
                else:
                    failed.append(module_name)

            success_count = len(results)
            failed_count = len(failed)

            if failed:
                failed_list = ""
                for name in failed[:10]:
                    failed_list += self.strings("failed_module", name=name)
                if failed_count > 10:
                    failed_list += self.strings("and_more", count=failed_count - 10)

                if success_count > 0:
                    await self._edit_with_emoji(
                        msg,
                        self.strings(
                            "reload_all_partial",
                            success=CUSTOM_EMOJI["success"],
                            success_count=f"✓ {success_count}",
                            warning=CUSTOM_EMOJI["warning"],
                            failed_count=failed_count,
                            failed_list=failed_list,
                        ),
                    )
                else:
                    await self._edit_with_emoji(
                        msg,
                        self.strings(
                            "reload_all_failed",
                            warning=CUSTOM_EMOJI["warning"],
                            count=failed_count,
                            failed_list=failed_list,
                        ),
                    )
            else:
                if success_count == 1:
                    await self._edit_with_emoji(
                        msg,
                        self.strings(
                            "reload_all_success_one",
                            success=CUSTOM_EMOJI["success"],
                            count="1",
                            name=results[0],
                        ),
                    )
                else:
                    await self._edit_with_emoji(
                        msg,
                        self.strings(
                            "reload_all_success",
                            success=CUSTOM_EMOJI["success"],
                            count=f"✓ {success_count}",
                        ),
                    )

            self.kernel.dedupe_event_builders(reason="reload_bulk_complete")
            self.kernel.ensure_core_message_handlers(reason="reload_bulk_complete")
            self.kernel.ensure_registered_module_handlers(reason="reload_bulk_complete")
            return

        # Single module reload
        module_name = args[1]
        actual_name, _ = self.kernel._loader.find_module_case_insensitive(module_name)
        if actual_name is None:
            self.kernel.logger.debug(
                "[reload] module-not-found requested=%r loaded=%r system=%r",
                module_name,
                list(self.kernel.loaded_modules.keys()),
                list(self.kernel.system_modules.keys()),
            )
            await self._edit_with_emoji(
                event,
                self.strings(
                    "module_not_found_um",
                    warning=CUSTOM_EMOJI["warning"],
                    module_name=module_name,
                ),
            )
            return

        module_name = actual_name
        file_path = self.kernel._loader.get_module_path(module_name)
        is_system = module_name in self.kernel.system_modules

        if not os.path.exists(file_path):
            self.kernel.logger.debug(
                "[reload] single-missing-file module=%r file=%r system=%s",
                module_name,
                file_path,
                is_system,
            )
            await self._edit_with_emoji(
                event,
                self.strings("module_file_not_found", warning=CUSTOM_EMOJI["warning"]),
            )
            return

        msg = await event.edit(
            self.strings(
                "reloading", reload=CUSTOM_EMOJI["reload"], module_name=module_name
            ),
            parse_mode="html",
        )
        self.kernel.logger.debug(
            "[reload] single-start module=%r system=%s file=%r",
            module_name,
            is_system,
            file_path,
        )

        try:
            with open(file_path, encoding="utf-8") as f:
                code = f.read()
            dependencies = self.kernel._loader.parse_requires(code)
        except Exception as e:
            dependencies = []
            self.kernel.logger.warning(
                "[reload] failed to parse dependencies for %s: %s", module_name, e
            )

        if dependencies:
            deps_with_emoji = "\n".join(
                f"{CUSTOM_EMOJI['lib']} {dep}" for dep in dependencies
            )
            await self._edit_with_emoji(
                msg,
                self.strings(
                    "installing_deps",
                    dependencies=CUSTOM_EMOJI["dependencies"],
                    deps_list=deps_with_emoji,
                ),
            )
            try:
                await self.kernel._loader.install_dependencies_batch(dependencies)
            except Exception as e:
                self.kernel.logger.error(
                    "[reload] deps install failed for %s: %s", module_name, e
                )
                await self._edit_with_emoji(
                    msg,
                    self.strings(
                        "install_failed",
                        blocked=CUSTOM_EMOJI["blocked"],
                        idea=CUSTOM_EMOJI["idea"],
                        log=html.escape(str(e)),
                    ),
                )
                return

        instance = self.kernel.loaded_modules.get(
            module_name
        ) or self.kernel.system_modules.get(module_name)
        if instance and getattr(instance, "_hikka_compat", False):
            self.kernel.logger.debug(
                "[reload] single-hikka-compat module=%r", module_name
            )
            if HIKKA_COMPAT:
                await unload_hikka_module(self.kernel, module_name)
                await asyncio.sleep(0)
        else:
            cfg = self.get_config()
            force_unload = not (cfg and cfg.get("loader_protect_system", True))
            try:
                await self.kernel.unregister_module_commands(
                    module_name, force=force_unload
                )
            except PermissionError:
                await self._edit_with_emoji(
                    msg,
                    self.strings(
                        "system_module_unload_attempt",
                        confused=CUSTOM_EMOJI["confused"],
                        blocked=CUSTOM_EMOJI["blocked"],
                        module_name=module_name,
                    ),
                )
                return

        if module_name in sys.modules:
            del sys.modules[module_name]
        if module_name in self.kernel.loaded_modules:
            del self.kernel.loaded_modules[module_name]

        if is_system:
            cfg = self.get_config()
            if cfg and cfg.get("loader_protect_system", True):
                if module_name in self.kernel.system_modules:
                    del self.kernel.system_modules[module_name]

        result = await self.kernel.load_module_from_file(
            file_path, module_name, is_system, is_reload=True
        )
        success = result[0]
        message_text = result[1] if len(result) >= 2 else ""

        self.kernel.dedupe_event_builders(reason=f"reload_single_after_{module_name}")
        self.kernel.ensure_core_message_handlers(
            reason=f"reload_single_after_{module_name}"
        )
        self.kernel.ensure_registered_module_handlers(
            reason=f"reload_single_after_{module_name}"
        )

        if success:
            lang = self.kernel.config.get("language", "ru")
            commands, _, _ = self.kernel._loader.get_module_commands(module_name, lang)
            cmd_text = (
                f"{CUSTOM_EMOJI['crystal']} {', '.join([f'<code>{self.get_prefix()}{cmd}</code>' for cmd in commands])}"
                if commands
                else self.strings["no_commands"]
            )
            emoji = random.choice(RANDOM_EMOJIS)
            self.kernel.logger.info(f"Модуль {module_name} перезагружен")
            await self._edit_with_emoji(
                msg,
                self.strings(
                    "reload_success",
                    success=CUSTOM_EMOJI["success"],
                    module_name=module_name,
                    emoji=emoji,
                    cmd_text=cmd_text,
                ),
            )
        else:
            await self.kernel.handle_error(
                Exception(message_text), source="reload_module_handler", event=event
            )
            await self._edit_with_emoji(
                msg, self.strings("reload_error", warning=CUSTOM_EMOJI["warning"])
            )

    @command(
        "addrepo",
        doc_en="<URL> add module repository URL",
        doc_ru="<URL> добавить URL репозитория модулей",
    )
    async def cmd_addrepo(self, event) -> None:
        args = event.text.split()
        if len(args) < 2:
            await self._edit_with_emoji(
                event,
                self.strings(
                    "addrepo_usage",
                    warning=CUSTOM_EMOJI["warning"],
                    prefix=self.get_prefix(),
                ),
            )
            return

        url = args[1].strip()
        success, message = await self.kernel.add_repository(url)

        await self._edit_with_emoji(
            event,
            f"{CUSTOM_EMOJI['success'] if success else CUSTOM_EMOJI['warning']} <b>{message}</b>",
        )

    @command(
        "delrepo",
        doc_en="<ID> remove module repository",
        doc_ru="<ID> удалить репозиторий модулей",
    )
    async def cmd_delrepo(self, event) -> None:
        args = event.text.split()
        if len(args) < 2:
            await self._edit_with_emoji(
                event,
                self.strings(
                    "delrepo_usage",
                    warning=CUSTOM_EMOJI["warning"],
                    prefix=self.get_prefix(),
                ),
            )
            return

        success, message = await self.kernel.remove_repository(args[1])
        await self._edit_with_emoji(
            event,
            f"{CUSTOM_EMOJI['success'] if success else CUSTOM_EMOJI['warning']} <b>{message}</b>",
        )
