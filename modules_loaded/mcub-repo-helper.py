# requires: aiohttp
# author: MCUB Team
# version: 1.1.0
# description: Модуль для загрузки модулей в официальный репозиторий MCUB

import os
import re
import aiohttp
import base64
from urllib.parse import urljoin


def register(kernel):
    client = kernel.client
    prefix = kernel.custom_prefix

    # Конфигурация по умолчанию
    kernel.config.setdefault("upload-user-key", "")
    kernel.config.setdefault("upload-user-name", "")
    kernel.config.setdefault("upload-repo-name", "")

    # GitHub API базовый URL
    GITHUB_API = "https://api.github.com"

    async def get_repo_info():
        """Получить информацию о репозитории"""
        token = kernel.config.get("upload-user-key", "")
        username = kernel.config.get("upload-user-name", "")
        repo = kernel.config.get("upload-repo-name", "")

        if not all([token, username, repo]):
            return None, "Не настроены ключи доступа. Используйте .mru -e для настройки"

        return {"token": token, "username": username, "repo": repo}, None

    async def github_request(method, endpoint, data=None, headers=None):
        """Выполнить запрос к GitHub API"""
        repo_info, error = await get_repo_info()
        if error:
            return None, error

        url = urljoin(GITHUB_API, endpoint)

        default_headers = {
            "Authorization": f'token {repo_info["token"]}',
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "MCUB-Upload-Module",
        }

        if headers:
            default_headers.update(headers)

        async with aiohttp.ClientSession() as session:
            try:
                async with session.request(
                    method,
                    url,
                    json=data,
                    headers=default_headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status == 204:
                        return True, None

                    response_data = await response.json()

                    if response.status >= 400:
                        error_msg = response_data.get("message", "Unknown error")
                        return None, f"GitHub API error: {error_msg}"

                    return response_data, None
            except Exception as e:
                return None, f"Request failed: {str(e)}"

    async def get_file_content(path):
        """Получить содержимое файла из репозитория"""
        repo_info, error = await get_repo_info()
        if error:
            return None, error

        endpoint = f"/repos/{repo_info['username']}/{repo_info['repo']}/contents/{path}"
        data, error = await github_request("GET", endpoint)

        if error:
            return None, error

        if data and "content" in data:
            content = base64.b64decode(data["content"]).decode("utf-8")
            return content, None

        return "", None  # Файл не существует, возвращаем пустую строку

    async def update_file(path, content, message):
        """Обновить или создать файл в репозитории"""
        repo_info, error = await get_repo_info()
        if error:
            return None, error

        endpoint = f"/repos/{repo_info['username']}/{repo_info['repo']}/contents/{path}"

        # Получить текущий sha файла, если он существует
        current_data, _ = await github_request("GET", endpoint)
        sha = current_data.get("sha") if current_data else None

        data = {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
        }

        if sha:
            data["sha"] = sha

        result, error = await github_request("PUT", endpoint, data)
        return result, error

    async def upload_module_content(
        file_content, original_filename, module_name, user_id
    ):
        """Загрузить содержимое файла модуля в репозиторий"""
        repo_info, error = await get_repo_info()
        if error:
            return False, error, None

        # Создаем имя файла с суффиксом
        base_name = os.path.basename(original_filename)
        name_without_ext = os.path.splitext(base_name)[0]

        # Удаляем существующий суффикс, если есть
        name_without_suffix = re.sub(r"-MCUB-repo$", "", name_without_ext)

        # Добавляем суффикс
        new_filename = f"{name_without_suffix}-MCUB-repo.py"

        # Коммит сообщение
        commit_message = f"{module_name} – {user_id}-Uploaded the module"

        # Загружаем файл
        result, error = await update_file(new_filename, file_content, commit_message)

        return result, error, new_filename

    async def update_modules_ini(module_name, user_id):
        """Обновить modules.ini, добавив новый модуль"""
        # Получаем текущий modules.ini
        content, error = await get_file_content("modules.ini")
        if error and "404" not in error:
            return False, error

        # Разбиваем на строки
        modules = content.strip().split("\n") if content else []

        # Проверяем, есть ли уже этот модуль
        if module_name in modules:
            return True, "Модуль уже существует в modules.ini"

        # Добавляем новый модуль
        modules.append(module_name)

        # Обновляем файл
        new_content = "\n".join(modules) + "\n"
        commit_message = f"Add {module_name} to modules.ini"

        result, error = await update_file("modules.ini", new_content, commit_message)
        return result, error

    async def update_name_ini(repo_name):
        """Обновить name.ini с именем репозитория"""
        commit_message = f"Update repository name to {repo_name}"
        result, error = await update_file("name.ini", repo_name, commit_message)
        return result, error

    @kernel.register_command("mru")
    # Загрузить модуль в репозиторий MCUB
    # Использование: .mru -s [имя_файла] -n [имя_модуля]
    # или: .mru -e [новое_имя_репозитория]
    async def mru_command(event):
        try:
            args = event.text.split()

            # Проверка на команду изменения репозитория
            if "-e" in args:
                idx = args.index("-e")
                if idx + 1 >= len(args):
                    await event.edit("❌ Укажите имя репозитория после -e")
                    return

                new_repo = args[idx + 1]

                # Обновляем конфиг
                kernel.config["upload-repo-name"] = new_repo
                kernel.save_config()

                # Обновляем name.ini
                result, error = await update_name_ini(new_repo)

                if error:
                    await event.edit(f"❌ Ошибка обновления репозитория: {error}")
                else:
                    await event.edit(f"✅ Репозиторий обновлен на: {new_repo}")
                return

            # Проверка на загрузку модуля
            if not event.is_reply:
                await event.edit("❌ Ответьте на файл для загрузки")
                return

            reply = await event.get_reply_message()

            if not reply.file:
                await event.edit("❌ В ответе должен быть файл")
                return

            # Парсим аргументы
            file_name = None
            module_name = None

            if "-s" in args:
                idx = args.index("-s")
                if idx + 1 < len(args):
                    file_name = args[idx + 1]

            if "-n" in args:
                idx = args.index("-n")
                if idx + 1 < len(args):
                    module_name = args[idx + 1]

            # Определяем имя файла
            if not file_name:
                file_name = reply.file.name or "module.py"

            # Определяем имя модуля
            if not module_name:
                module_name = os.path.splitext(os.path.basename(file_name))[0]
                # Удаляем суффикс, если есть
                module_name = re.sub(r"-MCUB-repo$", "", module_name)

            # Скачиваем файл в память
            await event.edit("📥 Скачиваю файл...")

            # Скачиваем файл как байты
            file_bytes = await reply.download_media(file=bytes)

            if not file_bytes:
                await event.edit("❌ Не удалось скачать файл")
                return

            # Конвертируем байты в строку
            try:
                file_content = file_bytes.decode("utf-8")
            except UnicodeDecodeError:
                await event.edit("❌ Файл должен быть текстовым (UTF-8)")
                return

            # Загружаем в репозиторий
            await event.edit("⬆️ Загружаю в репозиторий...")

            result, error, uploaded_filename = await upload_module_content(
                file_content, file_name, module_name, event.sender_id
            )

            if error:
                await event.edit(f"❌ Ошибка загрузки файла: {error}")
                return

            # Обновляем modules.ini
            await event.edit("📝 Обновляю modules.ini...")

            result2, error2 = await update_modules_ini(module_name, event.sender_id)

            if error2:
                await event.edit(
                    f"⚠️ Файл загружен как {uploaded_filename}, но ошибка обновления modules.ini: {error2}"
                )
                return

            await event.edit(
                f"✅ Модуль успешно загружен!\n"
                f"📄 Файл: {uploaded_filename}\n"
                f"🏷️  Имя в modules.ini: {module_name}\n"
                f"👤 ID пользователя: {event.sender_id}"
            )

        except Exception as e:
            await kernel.handle_error(e, source="mru_command", event=event)
            await event.edit("❌ Ошибка при загрузке модуля. Проверьте логи.")

    @kernel.register_command("mru-setup")
    # Настройка параметров загрузки
    async def mru_setup_command(event):
        try:
            args = event.text.split()

            if len(args) < 4:
                await event.edit(
                    "📝 Использование:\n"
                    f"{prefix}mru-setup <ключ_github> <имя_пользователя> <репозиторий>\n\n"
                    "Пример:\n"
                    f"{prefix}mru-setup ghp_abc123 username repo-name"
                )
                return

            token = args[1]
            username = args[2]
            repo = args[3]

            kernel.config["upload-user-key"] = token
            kernel.config["upload-user-name"] = username
            kernel.config["upload-repo-name"] = repo
            kernel.save_config()

            await event.edit(
                f"✅ Настройки сохранены:\n"
                f"🔑 Ключ: {token[:10]}...\n"
                f"👤 Пользователь: {username}\n"
                f"📁 Репозиторий: {repo}"
            )

        except Exception as e:
            await kernel.handle_error(e, source="mru_setup_command", event=event)
            await event.edit("❌ Ошибка при сохранении настроек")

    @kernel.register_command("mru-status")
    # Показать текущие настройки
    async def mru_status_command(event):
        try:
            token = kernel.config.get("upload-user-key", "Не задан")
            username = kernel.config.get("upload-user-name", "Не задан")
            repo = kernel.config.get("upload-repo-name", "Не задан")

            token_display = f"{token[:10]}..." if len(token) > 10 else token

            await event.edit(
                "📊 Статус модуля загрузки:\n\n"
                f"🔑 GitHub токен: {token_display}\n"
                f"👤 Имя пользователя: {username}\n"
                f"📁 Репозиторий: {repo}\n\n"
                f"📌 Для загрузки модуля: ответьте на файл командой {prefix}mru"
            )

        except Exception as e:
            await kernel.handle_error(e, source="mru_status_command", event=event)
            await event.edit("❌ Ошибка при получении статуса")

    @kernel.register_command("mru-test")
    # Тест подключения к GitHub
    async def mru_test_command(event):
        try:
            await event.edit("🔍 Тестирую подключение к GitHub...")

            repo_info, error = await get_repo_info()
            if error:
                await event.edit(f"❌ {error}")
                return

            # Проверяем доступ к репозиторию
            endpoint = f"/repos/{repo_info['username']}/{repo_info['repo']}"
            data, error = await github_request("GET", endpoint)

            if error:
                await event.edit(f"❌ Ошибка подключения: {error}")
                return

            # Проверяем существование modules.ini
            modules_content, error = await get_file_content("modules.ini")

            if error and "404" not in error:
                await event.edit(f"⚠️ Репозиторий доступен, но modules.ini: {error}")
                return

            module_count = (
                len(modules_content.strip().split("\n")) if modules_content else 0
            )

            await event.edit(
                f"✅ Подключение успешно!\n\n"
                f"📁 Репозиторий: {data.get('full_name', 'Unknown')}\n"
                f"📝 Описание: {data.get('description', 'None')}\n"
                f"⭐ Звёзд: {data.get('stargazers_count', 0)}\n"
                f"📦 Модулей в modules.ini: {module_count}\n"
                f"🔗 URL: {data.get('html_url', 'Unknown')}"
            )

        except Exception as e:
            await kernel.handle_error(e, source="mru_test_command", event=event)
            await event.edit("❌ Ошибка при тестировании подключения")
