# author: @Hairpin00
# version: 1.0.1
# description: Version
import time
import aiohttp
import asyncio
import subprocess
import os
from typing import Tuple, Optional
import shutil


# version kenrel MCUB
__version__ = "1.0.2.3.5"
VERSION = __version__

class VersionManager:

    def __init__(self, kernel):
        self.kernel = kernel
        self.logger = kernel.logger
        self._latest_version_cache = None   # (timestamp, version)

    @staticmethod
    def _parse_version(version_str: str) -> tuple:
        """
        Преобразует строку версии '1.0.2.1' в кортеж целых чисел.
        Нечисловые части заменяются на 0.
        """
        parts = []
        for part in version_str.split('.'):
            try:
                parts.append(int(part))
            except ValueError:
                parts.append(0)
        return tuple(parts)

    @staticmethod
    def compare_versions(v1: str, v2: str) -> int:
        """
        Сравнивает две строки версий.
        Возвращает:
            -1 если v1 < v2
             0 если v1 == v2
             1 если v1 > v2
        """
        v1_tuple = VersionManager._parse_version(v1)
        v2_tuple = VersionManager._parse_version(v2)
        if v1_tuple < v2_tuple:
            return -1
        if v1_tuple > v2_tuple:
            return 1
        return 0

    async def detect_branch(self) -> str:
        """
        Приоритет:
          1. Локальный Git (если доступен)
          2. Конфиг (ключ 'branch')
          3. По умолчанию 'main'
        """
        try:
            process = await asyncio.create_subprocess_exec(
                "git", "rev-parse", "--abbrev-ref", "HEAD",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            if process.returncode == 0:
                branch = stdout.decode().strip()
                if branch:
                    self.logger.debug(f"Detected git branch: {branch}")
                    return branch
        except (FileNotFoundError, asyncio.TimeoutError, subprocess.SubprocessError) as e:
            self.logger.debug(f"Git branch detection failed: {e}")

        config_branch = self.kernel.config.get("branch")
        if config_branch:
            self.logger.debug(f"Using branch from config: {config_branch}")
            return config_branch

        self.logger.debug("No branch specified, using 'main'")
        return "main"

    def get_update_base_url(self) -> str:
        """
        Возвращает базовый URL для обновлений с учётом ветки.
        По умолчанию используется self.kernel.UPDATE_REPO
        """
        base = self.kernel.UPDATE_REPO.rstrip('/')
        return base

    async def get_latest_kernel_version(self) -> str:
        """
        Получает последнюю версию ядра из репозитория (с кэшированием на 1 час).
        """
        if self._latest_version_cache:
            cache_time, version = self._latest_version_cache
            if time.time() - cache_time < 3600:
                return version

        branch = await self.detect_branch()
        base_url = self.get_update_base_url()
        if not base_url.endswith(branch + '/'):

            parts = base_url.split('/')
            if parts[-1] == '':
                parts = parts[:-1]
            parts[-1] = branch
            base_url = '/'.join(parts) + '/'
        url = base_url + "version.txt"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as resp:
                    if resp.status == 200:
                        version = (await resp.text()).strip()
                        self._latest_version_cache = (time.time(), version)
                        return version
        except Exception as e:
            self.logger.error(f"Error fetching latest kernel version: {e}")

        return self.kernel.VERSION




    async def check_module_compatibility(self, code: str) -> Tuple[bool, str]:
        """
        Анализирует исходный код модуля на наличие директив '# scop: ...'
        и проверяет выполнение всех требований.
        Возвращает (True, "") если совместимо, иначе (False, сообщение об ошибке).
        """
        lines = code.split('\n')
        directives = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith('# scop:'):
                rest = stripped[len('# scop:'):].strip()
                space_index = rest.find(' ')
                if space_index == -1:
                    scope = rest
                    params = ''
                else:
                    scope = rest[:space_index]
                    params = rest[space_index+1:].strip()
                directives.append((scope, params))

        if not directives:
            return True, ""

        current_version = self.kernel.VERSION
        latest_version = None

        for scope, params in directives:
            if scope == 'kernel':
                parts = params.split()
                if not parts:
                    continue

                if parts[0] == 'min':
                    if len(parts) >= 2 and parts[1].startswith('v'):
                        required = parts[1][1:]
                        if self.compare_versions(current_version, required) < 0:
                            return False, f"Module requires kernel version ≥ {required}, current is {current_version}"
                elif parts[0] == 'max':
                    if len(parts) >= 2 and parts[1].startswith('v'):
                        required = parts[1][1:]
                        if self.compare_versions(current_version, required) > 0:
                            return False, f"Module requires kernel version ≤ {required}, current is {current_version}"
                else:
                    if not parts[0].startswith('v'):
                        continue
                    spec = parts[0][1:]
                    if spec == '[__lastest__]':
                        if latest_version is None:
                            latest_version = await self.get_latest_kernel_version()
                        if self.compare_versions(current_version, latest_version) != 0:
                            return False, f"Module requires the latest kernel version ({latest_version}), but current is {current_version}"
                    else:
                        if self.compare_versions(current_version, spec) != 0:
                            return False, f"Module requires kernel version exactly {spec}, but current is {current_version}"

            elif scope == 'inline':
                if not hasattr(self.kernel, 'bot_client') or self.kernel.bot_client is None:
                    return False, "Module requires inline bot to be enabled, but bot_client is not available"
                if not self.kernel.bot_client.is_connected():
                    return False, "Module requires inline bot to be connected, but bot_client is disconnected"

            elif scope == 'ffmpeg':
                ffmpeg_path = shutil.which('ffmpeg')
                if ffmpeg_path is None:
                    return False, "Module requires ffmpeg to be installed on the system"

        return True, ""
