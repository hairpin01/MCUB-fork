# author: @Hairpin00
# version: 1.0.9
# description: loader modules
import logging
import os
import re
import sys
import subprocess
import inspect
import aiohttp
from datetime import datetime
import html
import random
from telethon import Button

logger = logging.getLogger("mcub.loader")

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Кастомные эмодзи
CUSTOM_EMOJI = {
    "loading": '<tg-emoji emoji-id="5893368370530621889">🔜</tg-emoji>',
    "dependencies": '<tg-emoji emoji-id="5328311576736833844">🟠</tg-emoji>',
    "confused": '<tg-emoji emoji-id="5249119354825487565">🫨</tg-emoji>',
    "error": '<tg-emoji emoji-id="5370843963559254781">😖</tg-emoji>',
    "file": '<tg-emoji emoji-id="5269353173390225894">💾</tg-emoji>',
    "process": '<tg-emoji emoji-id="5426958067763804056">⏳</tg-emoji>',
    "blocked": '<tg-emoji emoji-id="5431895003821513760">🚫</tg-emoji>',
    "warning": '<tg-emoji emoji-id="5409235172979672859">⚠️</tg-emoji>',
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
}

# Случайные эмодзи для завершения
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
    client = kernel.client
    language = kernel.config.get('language', 'en')

    # Локализованные строки
    strings = {
        'en': {
            'reply_to_py': '{warning} <b>Reply to a .py file</b>',
            'not_py_file': '{warning} <b>This is not a .py file</b>',
            'system_module_update_attempt': '{confused} <b>Oops, looks like you tried to update a system module</b> <code>{module_name}</code>\n<blockquote><i>{blocked} Unfortunately, you cannot update system modules using <code>loadera</code></i></blockquote>',
            'starting_install': '{action} modules',
            'installing': '{test} Installing',
            'updating': '{reload} Updating',
            'log_start': '=- Starting {action} module {module_name}',
            'log_filename': '=> File name: {filename}',
            'log_downloading': '=- Downloading file to {file_path}',
            'log_downloaded': '=> File downloaded successfully',
            'log_file_read': '=> File read',
            'log_checking_compatibility': '=- Checking module compatibility...',
            'log_incompatible': '=X Module incompatible (Heroku/Hikka type)',
            'log_compatible': '=> Module compatible',
            'log_getting_metadata': 'Getting module metadata...',
            'log_author': 'Author: {author}',
            'log_version': 'Version: {version}',
            'log_description': 'Description: {description}',
            'log_checking_deps': '=- Checking dependencies...',
            'log_deps_found': '=> Found dependencies: {deps}',
            'installing_deps': '{dependencies} <b>installing dependencies:</b>\n<code>{deps_list}</code>',
            'log_installing_dep': '=- Installing dependency: {dep}',
            'log_dep_installed': '=> Dependency {dep} installed successfully',
            'log_dep_error': '=X Error installing {dep}: {error}',
            'log_removing_old': '=- Removing old module commands {module_name}',
            'log_loading_module': '=- Loading module {module_name}...',
            'log_module_loaded': '=> Module loaded successfully',
            'log_commands_found': '=> Commands found: {count}',
            'module_loaded': '{success} <b>Module {module_name} loaded!</b> {emoji}\n<blockquote expandable>{idea} <i>D: {description}</i> | V: <code>{version}</code></blockquote>\n<blockquote expandable>{commands_list}</blockquote>',
            'no_cmd_desc': '{no_cmd} Command has no description',
            'command_line': '{crystal} <code>{prefix}{cmd}</code> – <b>{desc}</b>',
            'aliases_text': ' (Aliases: {alias_text})',
            'log_aliases_found': 'Command {cmd} has aliases: {aliases}',
            'log_install_error': '=X Module loading error: {error}',
            'install_failed': '<b>{blocked} Looks like the installation failed</b>\n<b>{idea} Install Log:</b>\n<pre>{log}</pre>',
            'log_conflict': '✗ Command conflict: {error}',
            'conflict_system': '{shield} <b>System command conflict!</b>\n<blockquote>Command <code>{prefix}{command}</code> already registered by system module.</blockquote>\n<b>Install Log:</b>\n<pre>{log}</pre>',
            'conflict_user': '{error} <b>Module command conflict!</b>\n<blockquote>Command <code>{prefix}{command}</code> already registered by module <code>{owner_module}</code>.</blockquote>\n<b>Install Log:</b>\n<pre>{log}</pre>',
            'log_critical': '=X Critical error: {error}',
            'log_traceback': 'Traceback:\n{traceback}',
            'dlm_usage': '{warning} <b>Usage:</b> <code>{prefix}dlm [-send/-s/-list] module_name or URL</code>',
            'dlm_list_loading': '{loading} <b>Getting module list...</b>',
            'dlm_list_title': '{folder} <b>Module list from repositories:</b>\n<blockquote expandable>{list}</blockquote>',
            'dlm_list_errors': '\n\n{warning} <b>Errors:</b>\n<blockquote expandable>{errors}</blockquote>',
            'dlm_list_failed': '{warning} <b>Failed to get module list</b>',
            'dlm_searching': '{loading} <b>Searching for module {module_name}...</b>',
            'module_info': '{file} <b>Module:</b> <code>{module_name}</code>\n{idea} <b>Description:</b> <i>{description}</i>\n{crystal} <b>Version:</b> <code>{version}</code>\n{angel} <b>Author:</b> <i>{author}</i>\n{folder} <b>Size:</b> <code>{size} bytes</code>\n{cloud} <b>Repository:</b> <code>{repo}</code>',
            'module_not_found': '{warning} <b>Module {module_name} not found in any repository</b>',
            'dlm_send_usage': '{warning} <b>Usage:</b> <code>{prefix}dlm -send module_name or URL</code>',
            'system_module_install_attempt': '{confused} <b>Oops, looks like you tried to install a system module</b> <code>{module_name}</code>\n<blockquote><i>{blocked} System modules cannot be installed via <code>dlm</code></i></blockquote>',
            'downloading_module': '{download} downloading',
            'log_mode': '=+ Mode: {mode}',
            'log_type': '=+ Type: {type}',
            'log_download_url': '=- Downloading module from URL: {url}',
            'log_download_success': '=> ✓ Module downloaded successfully (status: {status})',
            'log_download_failed': '=X Download error (status: {status})',
            'url_download_error': '{warning} <b>Failed to download module from URL</b> (status: {status})',
            'log_download_exception': '=X Download error: {error}',
            'url_exception': '{warning} <b>Download error:</b> {error}',
            'log_checking_repos': '=- Checking repositories ({count} items)',
            'log_using_repo': '=- Using specified repository: {repo}',
            'log_found_in_repo': '=> Module found in specified repository',
            'log_not_found_in_repo': '=X Module not found in specified repository',
            'log_checking_repo': '=- Checking repository {index}: {repo}',
            'log_repo_error': '=X Error checking repository {repo}: {error}',
            'module_not_found_repos': '{warning} <b>Module {module_name} not found in repositories</b>',
            'log_saving_for_send': 'Saving file for sending',
            'sending_module': '{upload} <b>Sending module {module_name}...</b>',
            'file_sent_caption': '<blockquote expandable>{file} <b>Module:</b> <code>{module_name}.py</code>\n{idea} <b>description:</b> <i>{description}</i>\n{crystal} <b>version:</b> <code>{version}</code>\n{angel} <b>author:</b> <i>{author}</i>\n{folder} <b>Size:</b> <code>{size} bytes</code></blockquote>',
            'log_file_sent': '=> File sent, deleting temp file',
            'log_install_mode': '=- Installation mode, continuing...',
            'log_saving_file': '=- Saving module file: {file_path}',
            'log_loading_to_kernel': '=- Loading module to kernel',
            'log_module_loaded_kernel': '=> Module loaded successfully to kernel',
            'conflict_system_alt': '{shield} <b>Oops, this module tried to overwrite a system command</b> (<code>{command}</code>)\n<blockquote><i>This is not an error but a <b>precaution</b></i></blockquote>\n<b>Install Log:</b>\n<pre>{log}</pre>',
            'conflict_user_alt': '{error} <b>Oops, looks like a module conflict occurred</b> <i>(their commands)</i>\n<blockquote><i>Conflict details in logs 🔭</i></blockquote>\n<b>Install Log:</b>\n<pre>{log}</pre>',
            'log_deleting_due_conflict': '=> Deleting module file due to conflict',
            'log_deleting_due_error': '=> Deleting module file due to error',
            'um_usage': '{warning} <b>Usage:</b> <code>{prefix}um module_name</code>',
            'module_not_found_um': '{warning} <b>Module {module_name} not found</b>',
            'module_unloaded': '{success} <b>Module {module_name} unloaded</b>',
            'unlm_usage': '{warning} <b>Usage:</b> <code>{prefix}unlm module_name</code>',
            'module_file_not_found': '{warning} <b>Module file not found</b>',
            'uploading_module': '{upload} <b>Uploading module {module_name}...</b>',
            'file_upload_caption': '{file} <b>Module:</b> {module_name}.py\n\n<blockquote><code>{prefix}im</code> to install</blockquote>',
            'reload_usage': '{warning} <b>Usage:</b> <code>{prefix}reload module_name</code>',
            'reloading': '{reload} <b>Reloading <code>{module_name}</code>...</b>',
            'reload_success': '{success} <b>Module {module_name} reloaded!</b> {emoji}\n\n<blockquote expandable>{cmd_text}</blockquote>',
            'no_commands': 'No commands',
            'reload_error': '{warning} <b>Error, check logs</b>',
            'no_modules': '{folder} <b>No modules loaded</b>',
            'loaded_modules': '{crystal} <b>Loaded modules:</b>\n\n',
            'system_modules': '{shield} <b>System modules:</b>\n',
            'user_modules': '{sparkle} <b>User modules:</b>\n',
            'module_line': '• <b>{name}</b> <i>({count} commands)</i>\n',
            'addrepo_usage': '{warning} <b>Usage:</b> <code>{prefix}addrepo URL</code>',
            'delrepo_usage': '{warning} <b>Usage:</b> <code>{prefix}delrepo index</code>',
            'catalog_title': '<b>🌩️ Official MCUB Repository</b> <code>{repo_url}</code>\n\n',
            'catalog_custom': '<i>{repo_name}</i> <code>{repo_url}</code>\n\n',
            'no_modules_catalog': '📭 No modules',
            'catalog_page': '📄 Page {page}/{total_pages}',
            'catalog_error': '❌ Catalog loading error: {error}',
            'btn_back': '⬅️ Back',
            'btn_next': '➡️ Next',
            'modules_not_mcub': '{warning} Module is not {mcub} type, [Heroku/Hikka]'
        },
        'ru': {
            'reply_to_py': '{warning} <b>Ответьте на .py файл</b>',
            'not_py_file': '{warning} <b>Это не .py файл</b>',
            'system_module_update_attempt': '{confused} <b>Ой, кажется ты попытался обновить системный модуль</b> <code>{module_name}</code>\n<blockquote><i>{blocked} К сожалению нельзя обновлять системные модули с помощью <code>loadera</code></i></blockquote>',
            'starting_install': '{action} модуль',
            'installing': '{test} Устанавливаю',
            'updating': '{reload} Oбновляю',
            'log_start': '=- Начинаю {action} модуля {module_name}',
            'log_filename': '=> Имя файла: {filename}',
            'log_downloading': '=- Скачиваю файл в {file_path}',
            'log_downloaded': '=> Файл успешно скачан',
            'log_file_read': '=> Файл прочитан',
            'log_checking_compatibility': '=- Проверяю совместимость модуля...',
            'log_incompatible': '=X Модуль не совместим (Heroku/Hikka тип)',
            'log_compatible': '=> Модуль совместим',
            'log_getting_metadata': 'Получаю метаданные модуля...',
            'log_author': 'Автор: {author}',
            'log_version': 'Версия: {version}',
            'log_description': 'Описание: {description}',
            'log_checking_deps': '=- Проверяю зависимости...',
            'log_deps_found': '=> Найдены зависимости: {deps}',
            'installing_deps': '{dependencies} <b>ставлю зависимости:</b>\n<code>{deps_list}</code>',
            'log_installing_dep': '=- Устанавливаю зависимость: {dep}',
            'log_dep_installed': '=> Зависимость {dep} установлена успешно',
            'log_dep_error': '=X Ошибка установки {dep}: {error}',
            'log_removing_old': '=- Удаляю старые команды модуля {module_name}',
            'log_loading_module': '=- Загружаю модуль {module_name}...',
            'log_module_loaded': '=> Модуль успешно загружен',
            'log_commands_found': '=> Найдено команд: {count}',
            'module_loaded': '{success} <b>Модуль {module_name} загружен!</b> {emoji}\n<blockquote expandable>{idea} <i>D: {description}</i> | V: <code>{version}</code></blockquote>\n<blockquote expandable>{commands_list}</blockquote>',
            'no_cmd_desc': '{no_cmd} У команды нету описания',
            'command_line': '{crystal} <code>{prefix}{cmd}</code> – <b>{desc}</b>',
            'aliases_text': ' (Aliases: {alias_text})',
            'log_aliases_found': 'Команда {cmd} имеет алиасы: {aliases}',
            'log_install_error': '=X Ошибка загрузки модуля: {error}',
            'install_failed': '<b>{blocked} Кажется установка прошла неудачно</b>\n<b>{idea} Install Log:</b>\n<pre>{log}</pre>',
            'log_conflict': '✗ Конфликт команд: {error}',
            'conflict_system': '{shield} <b>Конфликт системной команды!</b>\n<blockquote>Команда <code>{prefix}{command}</code> уже зарегистрирована системным модулем.</blockquote>\n<b>Install Log:</b>\n<pre>{log}</pre>',
            'conflict_user': '{error} <b>Конфликт команд модулей!</b>\n<blockquote>Команда <code>{prefix}{command}</code> уже зарегистрирована модулем <code>{owner_module}</code>.</blockquote>\n<b>Install Log</b>\n<pre>{log}</pre>',
            'log_critical': '=X Критическая ошибка: {error}',
            'log_traceback': 'Трейсбэк:\n{traceback}',
            'dlm_usage': '{warning} <b>Использование:</b> <code>{prefix}dlm [-send/-s/-list] название_модуля или ссылка</code>',
            'dlm_list_loading': '{loading} <b>Получаю список модулей...</b>',
            'dlm_list_title': '{folder} <b>Список модулей из репозиториев:</b>\n<blockquote expandable>{list}</blockquote>',
            'dlm_list_errors': '\n\n{warning} <b>Ошибки:</b>\n<blockquote expandable>{errors}</blockquote>',
            'dlm_list_failed': '{warning} <b>Не удалось получить список модулей</b>',
            'dlm_searching': '{loading} <b>Ищу модуль {module_name}...</b>',
            'module_info': '{file} <b>Модуль:</b> <code>{module_name}</code>\n{idea} <b>Описание:</b> <i>{description}</i>\n{crystal} <b>Версия:</b> <code>{version}</code>\n{angel} <b>Автор:</b> <i>{author}</i>\n{folder} <b>Размер:</b> <code>{size} байт</code>\n{cloud} <b>Репозиторий:</b> <code>{repo}</code>',
            'module_not_found': '{warning} <b>Модуль {module_name} не найден ни в одном репозитории</b>',
            'dlm_send_usage': '{warning} <b>Использование:</b> <code>{prefix}dlm -send название_модуля или ссылка</code>',
            'system_module_install_attempt': '{confused} <b>Ой, кажется ты попытался установить системный модуль</b> <code>{module_name}</code>\n<blockquote><i>{blocked} Системные модули нельзя устанавливать через <code>dlm</code></i></blockquote>',
            'downloading_module': '{download} скачиваю',
            'log_mode': '=+ Режим: {mode}',
            'log_type': '=+ Тип: {type}',
            'log_download_url': '=- Скачиваю модуль по URL: {url}',
            'log_download_success': '=> ✓ Модуль скачан успешно (статус: {status})',
            'log_download_failed': '=X Ошибка скачивания (статус: {status})',
            'url_download_error': '{warning} <b>Не удалось скачать модуль по ссылке</b> (статус: {status})',
            'log_download_exception': '=X Ошибка скачивания: {error}',
            'url_exception': '{warning} <b>Ошибка скачивания:</b> {error}',
            'log_checking_repos': '=- Проверяю репозитории ({count} шт.)',
            'log_using_repo': '=- Использую указанный репозиторий: {repo}',
            'log_found_in_repo': '=> Модуль найден в указанном репозитории',
            'log_not_found_in_repo': '=X Модуль не найден в указанном репозитории',
            'log_checking_repo': '=- Проверяю репозиторий {index}: {repo}',
            'log_repo_error': '=X Ошибка проверки репозитория {repo}: {error}',
            'module_not_found_repos': '{warning} <b>Модуль {module_name} не найден в репозиториях</b>',
            'log_saving_for_send': 'Сохраняю файл для отправки',
            'sending_module': '{upload} <b>Отправляю модуль {module_name}...</b>',
            'file_sent_caption': '<blockquote expandable>{file} <b>Модуль:</b> <code>{module_name}.py</code>\n{idea} <b>описание:</b> <i>{description}</i>\n{crystal} <b>версия:</b> <code>{version}</code>\n{angel} <b>автор:</b> <i>{author}</i>\n{folder} <b>Размер:</b> <code>{size} байт</code></blockquote>',
            'log_file_sent': '=> Файл отправлен, удаляю временный файл',
            'log_install_mode': '=- Режим установки, продолжаю...',
            'log_saving_file': '=- Сохраняю файл модуля: {file_path}',
            'log_loading_to_kernel': '=- Загружаю модуль в ядро',
            'log_module_loaded_kernel': '=> Модуль успешно загружен в ядро',
            'conflict_system_alt': '{shield} <b>Ой, этот модуль хотел перезаписать системную команду</b> (<code>{command}</code>)\n<blockquote><i>Это не ошибка а мера <b>предосторожности</b></i></blockquote>\n<b>Лог установки:</b>\n<pre>{log}</pre>',
            'conflict_user_alt': '{error} <b>Ой, кажется случился конфликт модулей</b> <i>(их команд)</i>\n<blockquote><i>Детали конфликта в логах 🔭</i></blockquote>\n<b>Лог установки:</b>\n<pre>{log}</pre>',
            'log_deleting_due_conflict': '=> Удаляю файл модуля из-за конфликта',
            'log_deleting_due_error': '=> Удаляю файл модуля из-за ошибки',
            'um_usage': '{warning} <b>Использование:</b> <code>{prefix}um название_модуля</code>',
            'module_not_found_um': '{warning} <b>Модуль {module_name} не найден</b>',
            'module_unloaded': '{success} <b>Модуль {module_name} удален</b>',
            'unlm_usage': '{warning} <b>Использование:</b> <code>{prefix}unlm название_модуля</code>',
            'module_file_not_found': '{warning} <b>Файл модуля не найден</b>',
            'uploading_module': '{upload} <b>Отправка модуля {module_name}...</b>',
            'file_upload_caption': '{file} <b>Модуль:</b> {module_name}.py\n\n<blockquote><code>{prefix}im</code> для установки</blockquote>',
            'reload_usage': '{warning} <b>Использование:</b> <code>{prefix}reload название_модуля</code>',
            'reloading': '{reload} <b>Перезагрузка <code>{module_name}</code>...</b>',
            'reload_success': '{success} <b>Модуль {module_name} перезагружен!</b> {emoji}\n\n<blockquote expandable>{cmd_text}</blockquote>',
            'no_commands': 'Нет команд',
            'reload_error': '{warning} <b>Ошибка, смотри логи</b>',
            'no_modules': '{folder} <b>Модули не загружены</b>',
            'loaded_modules': '{crystal} <b>Загруженные модули:</b>\n\n',
            'system_modules': '{shield} <b>Системные модули:</b>\n',
            'user_modules': '{sparkle} <b>Пользовательские модули:</b>\n',
            'module_line': '• <b>{name}</b> <i>({count} команд)</i>\n',
            'addrepo_usage': '{warning} <b>Использование:</b> <code>{prefix}addrepo URL</code>',
            'delrepo_usage': '{warning} <b>Использование:</b> <code>{prefix}delrepo индекс</code>',
            'catalog_title': '<b>🌩️ Официальный репозиторий MCUB</b> <code>{repo_url}</code>\n\n',
            'catalog_custom': '<i>{repo_name}</i> <code>{repo_url}</code>\n\n',
            'no_modules_catalog': '📭 Нет модулей',
            'catalog_page': '📄 Страница {page}/{total_pages}',
            'catalog_error': '❌ Ошибка загрузки каталога: {error}',
            'btn_back': '⬅️ Назад',
            'btn_next': '➡️ Вперёд',
            'modules_not_mcub': '{warning} Модуль не {mcub} типа <i>[Heroku/Hikka]</i>'
        }
    }

    # Получаем строки для текущего языка
    lang_strings = strings.get(language, strings['en'])


    def t(key, **kwargs):
        """Возвращает локализованную строку с подстановкой значений"""
        if key not in lang_strings:
            return key
        return lang_strings[key].format(**kwargs)

    async def mcub_handler():
        me = await kernel.client.get_me()
        mcub_emoji = (
            '<tg-emoji emoji-id="5470015630302287916">🔮</tg-emoji><tg-emoji emoji-id="5469945764069280010">🔮</tg-emoji><tg-emoji emoji-id="5469943045354984820">🔮</tg-emoji><tg-emoji emoji-id="5469879466954098867">🔮</tg-emoji>'
            if me.premium
            else "MCUB"
        )
        return mcub_emoji

    async def log_to_bot(text):
        if hasattr(kernel, "log_module"):
            await kernel.log_module(text)
        elif hasattr(kernel, "send_log_message"):
            await kernel.send_log_message(f"{CUSTOM_EMOJI['crystal']} {text}")

    async def log_error_to_bot(text):
        if hasattr(kernel, "log_error"):
            await kernel.log_error(text)
        elif hasattr(kernel, "send_log_message"):
            await kernel.send_log_message(f"{CUSTOM_EMOJI['error']} {text}")

    async def edit_with_emoji(message, text, **kwargs):
        try:
            await message.edit(text, parse_mode='html', **kwargs)
            return True
        except Exception as e:
            kernel.logger.error(f"loader: Error in edit_with_emoji: {e}")
            return False

    async def send_with_emoji(chat_id, text, **kwargs):
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
            kernel.logger.error(f"Error in send_with_emoji: {e}")
            await kernel.handle_error(e, source='send_with_emoji')
            # Fallback
            fallback_text = re.sub(r"<tg-emoji[^>]*>.*?</tg-emoji>", "", text)
            fallback_text = re.sub(r"<emoji[^>]*>.*?</emoji>", "", fallback_text)
            fallback_text = re.sub(r"<[^>]+>", "", fallback_text)
            return await client.send_message(chat_id, fallback_text, **kwargs)

    def get_module_commands(module_name, kernel):
        commands = []
        aliases_info = {}

        module = None
        if module_name in kernel.system_modules:
            module = kernel.system_modules[module_name]
        elif module_name in kernel.loaded_modules:
            module = kernel.loaded_modules[module_name]

        if module:
            for cmd, owner in kernel.command_owners.items():
                if owner == module_name:
                    commands.append(cmd)

        file_path = None
        if not commands:
            if module_name in kernel.system_modules:
                file_path = f"modules/{module_name}.py"
            elif module_name in kernel.loaded_modules:
                file_path = f"modules_loaded/{module_name}.py"

            if file_path and os.path.exists(file_path):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        code = f.read()

                        patterns = [
                            # Новый формат
                            r"@kernel\.register\.command\('([^']+)'\)",
                            r"kernel\.register\.command\('([^']+)'\)",
                            # Старый формат
                            r"@kernel\.register_command\('([^']+)'\)",
                            r"kernel\.register_command\('([^']+)'\)",
                            # Формат с client.on
                            r"@client\.on\(events\.NewMessage\(outgoing=True,\s*pattern=r'\\\\.([^']+)'\)\)",
                            # Формат с декоратором register
                            r"@register\.command\('([^']+)'\)",
                            # Формат с кастомным префиксом
                            r"pattern=r'\\{}(\[^'\]]+)'".format(re.escape(kernel.custom_prefix)),
                        ]

                        for pattern in patterns:
                            found = re.findall(pattern, code)
                            commands.extend(found)

                        for cmd in commands:
                            cmd_pattern = rf"(?:@kernel\.register\.command|kernel\.register\.command|@kernel\.register_command|kernel\.register_command)\(['\"]{cmd}['\"][^)]+alias\s*=\s*(.+?)\)"
                            cmd_match = re.search(cmd_pattern, code, re.DOTALL)
                            if cmd_match:
                                alias_part = cmd_match.group(1)
                                if alias_part.startswith("["):
                                    aliases = re.findall(r"['\"]([^'\"]+)['\"]", alias_part)
                                    if aliases:
                                        aliases_info[cmd] = aliases
                                else:

                                    alias_match = re.search(r"['\"]([^'\"]+)['\"]", alias_part)
                                    if alias_match:
                                        aliases_info[cmd] = [alias_match.group(1)]

                except Exception as e:
                    kernel.logger.error(f"Ошибка при парсинге команд модуля {module_name}: {e}")


        for alias, target_cmd in kernel.aliases.items():
            if target_cmd in commands:
                if target_cmd not in aliases_info:
                    aliases_info[target_cmd] = []
                if alias not in aliases_info[target_cmd]:
                    aliases_info[target_cmd].append(alias)

        commands = list(set([cmd for cmd in commands if cmd]))

        return commands, aliases_info

    async def load_module_from_file(file_path, module_name, is_system=False):
        try:
            return await kernel.load_module_from_file(file_path, module_name, is_system)
        except CommandConflictError as e:
            raise e
        except Exception as e:
            kernel.logger.error(f"Ошибка загрузки модуля {module_name}: {e}")
            return False, f"Ошибка загрузки: {str(e)}"

    def detect_module_type(module):
        if hasattr(module, "register"):
            sig = inspect.signature(module.register)
            params = list(sig.parameters.keys())
            if len(params) == 0:
                return "unknown"
            elif len(params) == 1:
                param_name = params[0]
                if param_name == "kernel":
                    return "new"
                elif param_name == "client":
                    return "old"
            return "unknown"
        return "none"

    async def handle_catalog(event, query_or_data):
        try:
            parts = query_or_data.split('_')

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
            except Exception:
                modules = []
                repo_name = repo_url.split("/")[-2] if "/" in repo_url else repo_url

            per_page = 8
            total_pages = (
                (len(modules) + per_page - 1) // per_page if modules else 1
            )

            if page < 1:
                page = 1
            if page > total_pages:
                page = total_pages

            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            page_modules = modules[start_idx:end_idx] if modules else []

            if repo_index == 0:
                msg = t('catalog_title', repo_url=repo_url)
            else:
                msg = t('catalog_custom', repo_name=repo_name, repo_url=repo_url)

            if page_modules:
                modules_text = " | ".join(
                    [f"<code>{m}</code>" for m in page_modules]
                )
                msg += modules_text
            else:
                msg += t('no_modules_catalog')

            msg += f"\n\n{t('catalog_page', page=page, total_pages=total_pages)}"

            buttons = []
            nav_buttons = []

            if page > 1:
                nav_buttons.append(
                    Button.inline(
                        t('btn_back'), f"catalog_{repo_index}_{page-1}".encode()
                    )
                )

            if page < total_pages:
                nav_buttons.append(
                    Button.inline(
                        t('btn_next'), f"catalog_{repo_index}_{page+1}".encode()
                    )
                )

            if nav_buttons:
                buttons.append(nav_buttons)

            if len(repos) > 1:
                repo_buttons = []
                for i in range(len(repos)):
                    repo_buttons.append(
                        Button.inline(f"{i+1}", f"catalog_{i}_1".encode())
                    )
                buttons.append(repo_buttons)

            return msg, buttons

        except Exception as e:
            logger.error(f"Ошибка в handle_catalog: {e}")
            import traceback
            traceback.print_exc()
            return t('catalog_error', error=str(e)[:100]), []

    async def catalog_inline_handler(event):
        try:

            query = event.text or ""


            if not query or query == "catalog":
                query = "catalog_0_1"

            msg, buttons = await handle_catalog(event, query)

            if buttons:
                builder = event.builder.article(
                    "Catalog",
                    text=msg,
                    buttons=buttons,
                    parse_mode="html"
                )
            else:
                builder = event.builder.article(
                    "Catalog",
                    text=msg,
                    parse_mode="html"
                )

            await event.answer([builder])

        except Exception as e:
            logger.error(f"Ошибка в catalog_inline_handler: {e}")

    async def catalog_callback_handler(event):
        try:

            data_str = event.data.decode("utf-8") if isinstance(event.data, bytes) else str(event.data)

            msg, buttons = await handle_catalog(event, data_str)

            await event.edit(msg, buttons=buttons if buttons else None, parse_mode="html")

        except Exception as e:
            logger.error(f"Ошибка в catalog_callback_handler: {e}")
            await event.answer(f"Ошибка: {str(e)[:50]}", alert=True)

    kernel.register_inline_handler("catalog", catalog_inline_handler)
    kernel.register_callback_handler("catalog_", catalog_callback_handler)

    @kernel.register.command('iload', alias='im')
    # <ответ> загрузить модуль
    async def install_module_handler(event):
        if not event.is_reply:
            await edit_with_emoji(
                event, t('reply_to_py', warning=CUSTOM_EMOJI['warning'])
            )
            return

        reply = await event.get_reply_message()
        if not reply.document or not reply.document.attributes[0].file_name.endswith(".py"):
            await edit_with_emoji(
                event, t('not_py_file', warning=CUSTOM_EMOJI['warning'])
            )
            return

        file_name = reply.document.attributes[0].file_name
        module_name = file_name[:-3]


        install_log = []

        def add_log(message):
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] {message}"
            install_log.append(log_entry)
            kernel.logger.debug(log_entry)

        if module_name in kernel.system_modules:
            await edit_with_emoji(
                event,
                t('system_module_update_attempt',
                  confused=CUSTOM_EMOJI['confused'],
                  module_name=module_name,
                  blocked=CUSTOM_EMOJI['blocked'])
            )
            return

        is_update = module_name in kernel.loaded_modules

        action = t('updating', reload=CUSTOM_EMOJI['loading']) if is_update else t('installing', test=CUSTOM_EMOJI['loading'])
        msg = await event.edit(
            t('starting_install', action=action), parse_mode="html"
        )

        add_log(t('log_start', action='обновление' if is_update else 'установку', module_name=module_name))
        add_log(t('log_filename', filename=file_name))

        file_path = os.path.join(kernel.MODULES_LOADED_DIR, file_name)

        try:

            add_log(t('log_downloading', file_path=file_path))
            await reply.download_media(file_path)
            add_log(t('log_downloaded'))

            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()
            add_log(t('log_file_read'))

            mcub = await mcub_handler()
            add_log(t('log_checking_compatibility'))
            if re.search(r'^from \.\. import', code, re.MULTILINE) or re.search(r'^import loader\b', code, re.MULTILINE):
                add_log(t('log_incompatible'))
                await edit_with_emoji(
                    msg, t('modules_not_mcub', mcub=mcub, warning=CUSTOM_EMOJI['warning'])
                )
                os.remove(file_path)
                return
            add_log(t('log_compatible'))


            add_log(t('log_getting_metadata'))
            metadata = await kernel.get_module_metadata(code)
            add_log(t('log_author', author=metadata['author']))
            add_log(t('log_version', version=metadata['version']))
            add_log(t('log_description', description=metadata['description']))

            dependencies = []
            add_log(t('log_checking_deps'))
            if "requires" in code:
                reqs = re.findall(r"# requires: (.+)", code)
                if reqs:
                    dependencies = [req.strip() for req in reqs[0].split(",")]
                    add_log(t('log_deps_found', deps=', '.join(dependencies)))

            if dependencies:
                await edit_with_emoji(
                    msg,
                    t('installing_deps',
                      dependencies=CUSTOM_EMOJI['dependencies'],
                      deps_list='\n'.join(dependencies)),
                )

                for dep in dependencies:
                    add_log(t('log_installing_dep', dep=dep))
                    result = subprocess.run(
                        [sys.executable, "-m", "pip", "install", dep],
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode == 0:
                        add_log(t('log_dep_installed', dep=dep))
                    else:
                        add_log(t('log_dep_error', dep=dep, error=result.stderr[:200]))

            if is_update:
                add_log(t('log_removing_old', module_name=module_name))
                kernel.unregister_module_commands(module_name)

            add_log(t('log_loading_module', module_name=module_name))
            success, message_text = await kernel.load_module_from_file(
                file_path, module_name, False
            )

            if success:
                add_log(t('log_module_loaded'))
                commands, aliases_info = get_module_commands(module_name, kernel)

                emoji = random.choice(RANDOM_EMOJIS)

                commands_list = ""
                if commands:
                    add_log(t('log_commands_found', count=len(commands)))
                    for cmd in commands:
                        cmd_desc = metadata["commands"].get(
                            cmd, t('no_cmd_desc', no_cmd=CUSTOM_EMOJI['no_cmd'])
                        )
                        command_line = t('command_line',
                                        crystal=CUSTOM_EMOJI['crystal'],
                                        prefix=kernel.custom_prefix,
                                        cmd=cmd,
                                        desc=cmd_desc)

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
                                command_line += t('aliases_text', alias_text=alias_text)
                                add_log(t('log_aliases_found', cmd=cmd, aliases=', '.join(aliases)))
                        commands_list += command_line + "\n"

                final_msg = t('module_loaded',
                             success=CUSTOM_EMOJI['success'],
                             module_name=module_name,
                             emoji=emoji,
                             idea=CUSTOM_EMOJI['idea'],
                             description=metadata["description"],
                             version=metadata["version"],
                             commands_list=commands_list)

                kernel.logger.info(f"Модуль {module_name} установлен")
                await edit_with_emoji(msg, final_msg)

            else:
                add_log(t('log_install_error', error=message_text))
                log_text = "\n".join(install_log)
                await edit_with_emoji(
                    msg,
                    t('install_failed',
                      blocked=CUSTOM_EMOJI['blocked'],
                      idea=CUSTOM_EMOJI['idea'],
                      log=html.escape(log_text))
                )

                if os.path.exists(file_path):
                    os.remove(file_path)

        except CommandConflictError as e:
            add_log(t('log_conflict', error=e))
            log_text = "\n".join(install_log)

            _conflict_details = f"Команда '{e.command}' уже зарегистрирована модулем '{e.conflict_type}'"

            if e.conflict_type == "system":
                await edit_with_emoji(
                    msg,
                    t('conflict_system',
                      shield=CUSTOM_EMOJI['shield'],
                      prefix=kernel.custom_prefix,
                      command=e.command,
                      log=html.escape(log_text)),
                )
            elif e.conflict_type == "user":
                owner_module = kernel.command_owners.get(e.command, 'unknown')
                await edit_with_emoji(
                    msg,
                    t('conflict_user',
                      error=CUSTOM_EMOJI['error'],
                      prefix=kernel.custom_prefix,
                      command=e.command,
                      owner_module=owner_module,
                      log=html.escape(log_text)),
                )
            if os.path.exists(file_path):
                os.remove(file_path)

        except Exception as e:
            add_log(t('log_critical', error=str(e)))
            import traceback
            add_log(t('log_traceback', traceback=traceback.format_exc()))

            log_text = "\n".join(install_log)
            await edit_with_emoji(
                msg,
                t('install_failed',
                  blocked=CUSTOM_EMOJI['blocked'],
                  idea=CUSTOM_EMOJI['idea'],
                  log=html.escape(log_text))
            )
            await kernel.handle_error(e, source="install_module_handler", event=event)
            if os.path.exists(file_path):
                os.remove(file_path)

    @kernel.register.command('dlm')
    # <args> <URL/модуль> -s отправить файлом, -list список модулей
    async def download_module_handler(event):
        args = event.text.split()

        if len(args) < 2:
            try:
                bot_username = None
                if hasattr(kernel, "bot_client") and kernel.bot_client:
                    bot_info = await kernel.bot_client.get_me()
                    bot_username = bot_info.username

                if bot_username:
                    results = await client.inline_query(bot_username, "catalog_")
                    if results:
                        await results[0].click(event.chat_id)
                        await event.delete()
                        return
            except Exception as e:
                kernel.logger.error(f"Error calling inline catalog: {e}")
                pass

            await edit_with_emoji(
                event,
                t('dlm_usage', warning=CUSTOM_EMOJI['warning'], prefix=kernel.custom_prefix),
            )
            return

        if args[1] == "-list":
            if len(args) == 2:
                await edit_with_emoji(
                    event, t('dlm_list_loading', loading=CUSTOM_EMOJI['loading'])
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
                            errors.append(f"{i+1}. {repo_name}: пустой список")
                    except Exception as e:
                        errors.append(f"{i+1}. {repo}: ошибка - {str(e)[:50]}")

                if message_lines:
                    msg_text = "\n".join(message_lines)
                    final_msg = t('dlm_list_title', folder=CUSTOM_EMOJI['folder'], list=msg_text)

                    if errors:
                        final_msg += t('dlm_list_errors', warning=CUSTOM_EMOJI['warning'], errors="<br>".join(errors))
                else:
                    final_msg = t('dlm_list_failed', warning=CUSTOM_EMOJI['warning'])
                    if errors:
                        final_msg += f'\n<blockquote expandable>{"<br>".join(errors)}</blockquote>'

                await edit_with_emoji(event, final_msg)
                return
            else:
                module_name = args[2]
                msg = await event.edit(
                    t('dlm_searching', loading=CUSTOM_EMOJI['loading'], module_name=module_name),
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

                            info = t('module_info',
                                    file=CUSTOM_EMOJI['file'],
                                    module_name=module_name,
                                    idea=CUSTOM_EMOJI['idea'],
                                    description=metadata["description"],
                                    crystal=CUSTOM_EMOJI['crystal'],
                                    version=metadata["version"],
                                    angel=CUSTOM_EMOJI['angel'],
                                    author=metadata["author"],
                                    folder=CUSTOM_EMOJI['folder'],
                                    size=size,
                                    cloud=CUSTOM_EMOJI['cloud'],
                                    repo=repo)
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
                        t('module_not_found', warning=CUSTOM_EMOJI['warning'], module_name=module_name),
                    )
                return

        send_mode = False
        module_or_url = None
        repo_index = None

        if args[1] in ["-send", "-s"]:
            if len(args) < 3:
                await edit_with_emoji(
                    event,
                    t('dlm_send_usage', warning=CUSTOM_EMOJI['warning'], prefix=kernel.custom_prefix),
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

        if module_name in kernel.system_modules:
            await edit_with_emoji(
                event,
                t('system_module_install_attempt',
                  confused=CUSTOM_EMOJI['confused'],
                  module_name=module_name,
                  blocked=CUSTOM_EMOJI['blocked']),
            )
            return

        is_update = module_name in kernel.loaded_modules

        if send_mode:
            action = t('downloading_module', download=CUSTOM_EMOJI['download'])
        else:
            action = t('updating', reload=CUSTOM_EMOJI['reload']) if is_update else t('installing', test=CUSTOM_EMOJI['reload'])

        msg = await event.edit(
            t('starting_install', action=action, module_name=module_name), parse_mode="html"
        )


        install_log = []

        def add_log(message):
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] {message}"
            install_log.append(log_entry)
            kernel.logger.debug(log_entry)

        try:
            code = None
            repo_url = None

            add_log(t('log_start', action='скачивание' if send_mode else 'установку', module_name=module_name))
            add_log(t('log_mode', mode='отправка' if send_mode else 'установка'))
            add_log(t('log_type', type='URL' if is_url else 'из репозитория'))

            if is_url:
                try:
                    add_log(t('log_download_url', url=module_or_url))
                    async with aiohttp.ClientSession() as session:
                        async with session.get(module_or_url) as resp:
                            if resp.status == 200:
                                code = await resp.text()
                                add_log(t('log_download_success', status=resp.status))
                            else:
                                add_log(t('log_download_failed', status=resp.status))
                                await edit_with_emoji(
                                    msg,
                                    t('url_download_error', warning=CUSTOM_EMOJI['warning'], status=resp.status),
                                )
                                return
                except Exception as e:
                    add_log(t('log_download_exception', error=str(e)))
                    await kernel.handle_error(e, source="install_for_url", event=event)
                    await edit_with_emoji(
                        msg,
                        t('url_exception', warning=CUSTOM_EMOJI['warning'], error=str(e)[:100]),
                    )
                    return
            else:
                repos = [kernel.default_repo] + kernel.repositories
                add_log(t('log_checking_repos', count=len(repos)))

                if repo_index is not None and 0 <= repo_index < len(repos):
                    repo_url = repos[repo_index]
                    add_log(t('log_using_repo', repo=repo_url))
                    code = await kernel.download_module_from_repo(repo_url, module_name)
                    if code:
                        add_log(t('log_found_in_repo'))
                    else:
                        add_log(t('log_not_found_in_repo'))
                else:
                    for i, repo in enumerate(repos):
                        try:
                            add_log(t('log_checking_repo', index=i+1, repo=repo))
                            code = await kernel.download_module_from_repo(repo, module_name)
                            if code:
                                repo_url = repo
                                add_log(t('log_found_in_repo'))
                                break
                            else:
                                add_log(t('log_not_found_in_repo'))
                        except Exception as e:
                            add_log(t('log_repo_error', repo=repo, error=str(e)[:100]))
                            await kernel.log_error(
                                f"Ошибка скачивания модуля {module_name} из {repo}: {e}"
                            )
                            continue

            if not code:
                add_log(t('module_not_found_repos', module_name=module_name))
                await edit_with_emoji(
                    msg,
                    t('module_not_found_repos', warning=CUSTOM_EMOJI['warning'], module_name=module_name),
                )
                return

            metadata = await kernel.get_module_metadata(code)
            add_log(t('log_getting_metadata'))
            add_log(t('log_author', author=metadata['author']))
            add_log(t('log_version', version=metadata['version']))
            add_log(t('log_description', description=metadata['description']))

            file_path = os.path.join(kernel.MODULES_LOADED_DIR, f"{module_name}.py")

            if send_mode:
                add_log(t('log_saving_for_send'))
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(code)

                await edit_with_emoji(
                    msg,
                    t('sending_module', upload=CUSTOM_EMOJI['upload'], module_name=module_name),
                )
                # await event.delete()

                await event.edit(
                    t('file_sent_caption',
                    file=CUSTOM_EMOJI['file'],
                    module_name=module_name,
                    idea=CUSTOM_EMOJI['idea'],
                    description=metadata["description"],
                    crystal=CUSTOM_EMOJI['crystal'],
                    version=metadata["version"],
                    angel=CUSTOM_EMOJI['angel'],
                    author=metadata["author"],
                    folder=CUSTOM_EMOJI['folder'],
                    size=os.path.getsize(file_path)),
                    file=file_path,
                    parse_mode="html"
                )

                add_log(t('log_file_sent'))
                os.remove(file_path)
                return

            add_log(t('log_install_mode'))

            dependencies = []
            if "requires" in code:
                reqs = re.findall(r"# requires: (.+)", code)
                if reqs:
                    dependencies = [req.strip() for req in reqs[0].split(",")]
                    add_log(t('log_deps_found', deps=', '.join(dependencies)))

            if dependencies:
                await edit_with_emoji(
                    msg,
                    t('installing_deps',
                      dependencies=CUSTOM_EMOJI['dependencies'],
                      deps_list='\n'.join(dependencies)),
                )

                for dep in dependencies:
                    add_log(t('log_installing_dep', dep=dep))
                    result = subprocess.run(
                        [sys.executable, "-m", "pip", "install", dep],
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode == 0:
                        add_log(t('log_dep_installed', dep=dep))
                    else:
                        add_log(t('log_dep_error', dep=dep, error=result.stderr[:200]))

            if is_update:
                add_log(t('log_removing_old', module_name=module_name))
                kernel.unregister_module_commands(module_name)

            add_log(t('log_saving_file', file_path=file_path))
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(code)

            add_log(t('log_loading_to_kernel'))
            success, message_text = await kernel.load_module_from_file(
                file_path, module_name, False
            )

            if success:
                add_log(t('log_module_loaded_kernel'))
                commands, aliases_info = get_module_commands(module_name, kernel)
                emoji = random.choice(RANDOM_EMOJIS)

                commands_list = ""
                if commands:
                    add_log(t('log_commands_found', count=len(commands)))
                    for cmd in commands:
                        cmd_desc = metadata["commands"].get(
                            cmd, t('no_cmd_desc', no_cmd=CUSTOM_EMOJI['no_cmd'])
                        )
                        command_line = t('command_line',
                                        crystal=CUSTOM_EMOJI['crystal'],
                                        prefix=kernel.custom_prefix,
                                        cmd=cmd,
                                        desc=cmd_desc)

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
                                command_line += t('aliases_text', alias_text=alias_text)
                                add_log(t('log_aliases_found', cmd=cmd, aliases=', '.join(aliases)))
                        commands_list += command_line + "\n"

                final_msg = t('module_loaded',
                             success=CUSTOM_EMOJI['success'],
                             module_name=module_name,
                             emoji=emoji,
                             idea=CUSTOM_EMOJI['idea'],
                             description=metadata["description"],
                             version=metadata["version"],
                             commands_list=commands_list)

                kernel.logger.info(f"Модуль {module_name} скачан")
                await edit_with_emoji(msg, final_msg)
            else:
                add_log(t('log_install_error', error=message_text))
                log_text = "\n".join(install_log)
                await edit_with_emoji(
                    msg,
                    t('install_failed',
                      blocked=CUSTOM_EMOJI['blocked'],
                      idea=CUSTOM_EMOJI['idea'],
                      log=html.escape(log_text))
                )
                if os.path.exists(file_path):
                    add_log(t('log_deleting_due_error'))
                    os.remove(file_path)

        except CommandConflictError as e:
            add_log(t('log_conflict', error=e))
            log_text = "\n".join(install_log)

            if e.conflict_type == "system":
                await edit_with_emoji(
                    msg,
                    t('conflict_system_alt',
                      shield=CUSTOM_EMOJI['shield'],
                      command=e.command,
                      log=html.escape(log_text)),
                )
            elif e.conflict_type == "user":
                await edit_with_emoji(
                    msg,
                    t('conflict_user_alt',
                      error=CUSTOM_EMOJI['error'],
                      log=html.escape(log_text)),
                )

            file_path = os.path.join(kernel.MODULES_LOADED_DIR, f"{module_name}.py")
            if os.path.exists(file_path):
                add_log(t('log_deleting_due_conflict'))
                os.remove(file_path)

        except Exception as e:
            add_log(t('log_critical', error=str(e)))
            import traceback
            add_log(t('log_traceback', traceback=traceback.format_exc()))

            log_text = "\n".join(install_log)
            await edit_with_emoji(
                msg,
                t('install_failed',
                  blocked=CUSTOM_EMOJI['blocked'],
                  idea=CUSTOM_EMOJI['idea'],
                  log=html.escape(log_text))
            )

            file_path = os.path.join(kernel.MODULES_LOADED_DIR, f"{module_name}.py")
            if os.path.exists(file_path):
                add_log(t('log_deleting_due_error'))
                os.remove(file_path)

    @kernel.register.command('um')
    # <модуль> удалить модуль
    async def unload_module_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await edit_with_emoji(
                event,
                t('um_usage', warning=CUSTOM_EMOJI['warning'], prefix=kernel.custom_prefix),
            )
            return

        module_name = args[1]

        if module_name not in kernel.loaded_modules and module_name not in kernel.system_modules:
            await edit_with_emoji(
                event,
                t('module_not_found_um', warning=CUSTOM_EMOJI['warning'], module_name=module_name),
            )
            return

        kernel.unregister_module_commands(module_name)

        file_path = os.path.join(kernel.MODULES_LOADED_DIR, f"{module_name}.py")
        if os.path.exists(file_path):
            os.remove(file_path)

        if module_name in sys.modules:
            del sys.modules[module_name]

        if module_name in kernel.loaded_modules:
            del kernel.loaded_modules[module_name]

        await log_to_bot(f"Модуль {module_name} удалён")
        await edit_with_emoji(
            event, t('module_unloaded', success=CUSTOM_EMOJI['success'], module_name=module_name)
        )

    @kernel.register.command("unlm")
    # <модуль> - выгрузить в виде файла
    async def upload_module_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await edit_with_emoji(
                event,
                t('unlm_usage', warning=CUSTOM_EMOJI['warning'], prefix=kernel.custom_prefix),
            )
            return

        module_name = args[1]

        if (
            module_name not in kernel.loaded_modules
            and module_name not in kernel.system_modules
        ):
            await edit_with_emoji(
                event,
                t('module_not_found_um', warning=CUSTOM_EMOJI['warning'], module_name=module_name),
            )
            return

        file_path = None
        if module_name in kernel.system_modules:
            file_path = os.path.join(kernel.MODULES_DIR, f"{module_name}.py")
        else:
            file_path = os.path.join(kernel.MODULES_LOADED_DIR, f"{module_name}.py")

        if not os.path.exists(file_path):
            await edit_with_emoji(
                event, t('module_file_not_found', warning=CUSTOM_EMOJI['warning'])
            )
            return

        await edit_with_emoji(
            event, t('uploading_module', upload=CUSTOM_EMOJI['upload'], module_name=module_name)
        )
        await event.edit(
            t('file_upload_caption',
              file=CUSTOM_EMOJI['file'],
              module_name=module_name,
              prefix=kernel.custom_prefix),
            parse_mode='html',
            file=file_path,
        )

    @kernel.register.command("reload")
    # <modules> reload modules
    async def reload_module_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await edit_with_emoji(
                event,
                t('reload_usage', warning=CUSTOM_EMOJI['warning'], prefix=kernel.custom_prefix),
            )
            return

        module_name = args[1]

        if module_name not in kernel.loaded_modules and module_name not in kernel.system_modules:
            await edit_with_emoji(
                event,
                t('module_not_found_um', warning=CUSTOM_EMOJI['warning'], module_name=module_name),
            )
            return

        if module_name in kernel.system_modules:
            file_path = os.path.join(kernel.MODULES_DIR, f"{module_name}.py")
            is_system = True
        else:
            file_path = os.path.join(kernel.MODULES_LOADED_DIR, f"{module_name}.py")
            is_system = False

        if not os.path.exists(file_path):
            await edit_with_emoji(
                event, t('module_file_not_found', warning=CUSTOM_EMOJI['warning'])
            )
            return

        msg = await event.edit(
            t('reloading', reload=CUSTOM_EMOJI['reload'], module_name=module_name),
            parse_mode="html",
        )

        if module_name in sys.modules:
            del sys.modules[module_name]

        kernel.unregister_module_commands(module_name)


        if is_system:
            if module_name in kernel.system_modules:
                del kernel.system_modules[module_name]
        else:
            if module_name in kernel.loaded_modules:
                del kernel.loaded_modules[module_name]

        success, message_text = await kernel.load_module_from_file(
            file_path, module_name, is_system
        )

        if success:
            commands, aliases = get_module_commands(module_name, kernel)
            cmd_text = (
                f'{CUSTOM_EMOJI["crystal"]} {", ".join([f"<code>{kernel.custom_prefix}{cmd}</code>" for cmd in commands])}'
                if commands
                else t('no_commands')
            )

            emoji = random.choice(RANDOM_EMOJIS)
            kernel.logger.info(f"Модуль {module_name} перезагружен")
            await edit_with_emoji(
                msg,
                t('reload_success',
                  success=CUSTOM_EMOJI['success'],
                  module_name=module_name,
                  emoji=emoji,
                  cmd_text=cmd_text),
            )
        else:
            await kernel.handle_error(Exception(message_text), source="reload_module_handler", event=event)
            await edit_with_emoji(
                msg, t('reload_error', warning=CUSTOM_EMOJI['warning'])
            )

    @kernel.register.command("modules")
    async def modules_list_handler(event):
        await log_to_bot("🔷 Просмотр списка модулей")

        if not kernel.loaded_modules and not kernel.system_modules:
            await edit_with_emoji(
                event, t('no_modules', folder=CUSTOM_EMOJI['folder'])
            )
            return

        msg = t('loaded_modules', crystal=CUSTOM_EMOJI['crystal'])

        if kernel.system_modules:
            msg += t('system_modules', shield=CUSTOM_EMOJI['shield'])
            for name in sorted(kernel.system_modules.keys()):
                commands, _ = get_module_commands(name, kernel)
                msg += t('module_line', name=name, count=len(commands))
            msg += "\n"

        if kernel.loaded_modules:
            msg += t('user_modules', sparkle=CUSTOM_EMOJI['sparkle'])
            for name in sorted(kernel.loaded_modules.keys()):
                commands, _ = get_module_commands(name, kernel)
                msg += t('module_line', name=name, count=len(commands))

        await edit_with_emoji(event, msg)

    @kernel.register.command('addrepo')
    # <URL> добавить репо
    async def add_repo_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await edit_with_emoji(
                event,
                t('addrepo_usage', warning=CUSTOM_EMOJI['warning'], prefix=kernel.custom_prefix),
            )
            return

        url = args[1].strip()
        success, message = await kernel.add_repository(url)

        if success:
            await edit_with_emoji(event, f'{CUSTOM_EMOJI["success"]} <b>{message}</b>')
        else:
            await edit_with_emoji(event, f'{CUSTOM_EMOJI["warning"]} <b>{message}</b>')

    @kernel.register.command('delrepo')
    # <id> удалить репо
    async def del_repo_handler(event):
        args = event.text.split()
        if len(args) < 2:
            await edit_with_emoji(
                event,
                t('delrepo_usage', warning=CUSTOM_EMOJI['warning'], prefix=kernel.custom_prefix),
            )
            return

        success, message = await kernel.remove_repository(args[1])

        if success:
            await edit_with_emoji(event, f'{CUSTOM_EMOJI["success"]} <b>{message}</b>')
        else:
            await edit_with_emoji(event, f'{CUSTOM_EMOJI["warning"]} <b>{message}</b>')
