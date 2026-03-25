# author: @Hairpin00
# version: 1.0.1
# description: Version
import time
import aiohttp
import asyncio
import subprocess
from typing import Tuple


# version kenrel MCUB
__version__ = "1.0.4.6"
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
                    return branch
        except (FileNotFoundError, asyncio.TimeoutError, subprocess.SubprocessError) as e:
            self.logger.debug(f"Git branch detection failed: {e}")

        config_branch = self.kernel.config.get("branch")
        if config_branch:
            self.logger.debug(f"Using branch from config: {config_branch}")
            return config_branch

        self.logger.debug("No branch specified, using 'main'")
        return "main"

    async def get_commit_sha(self, short: bool = True) -> str:
        """
        Возвращает SHA текущего коммита.
        Если short=True, возвращает первые 7 символов.
        """
        try:
            process = await asyncio.create_subprocess_exec(
                "git", "rev-parse", "HEAD",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            if process.returncode == 0:
                sha = stdout.decode().strip()
                return sha[:7] if short else sha
        except (FileNotFoundError, asyncio.TimeoutError, subprocess.SubprocessError) as e:
            self.logger.debug(f"Git commit SHA detection failed: {e}")
        return "unknown"

    async def get_github_commit_url(self) -> str:
        """
        Возвращает URL на текущий коммит в GitHub.
        """
        try:
            sha = await self.get_commit_sha(short=False)
            repo = self.kernel.UPDATE_REPO.rstrip('/')

            if "raw.githubusercontent.com" in repo:
                parts = repo.split('/')
                # parts: ['https:', '', 'raw.githubusercontent.com', 'user', 'repo', 'branch']
                base = f"https://github.com/{parts[3]}/{parts[4]}"
            else:
                branch = await self.detect_branch()
                base = repo[: -(len(branch) + 1)] if repo.endswith('/' + branch) else repo

            return f"{base}/commit/{sha}"
        except Exception as e:
            self.logger.debug(f"GitHub commit URL generation failed: {e}")
        return ""

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
        """Moved to core/lib/loader/compat.py — delegates to ModuleCompatChecker."""
        from core.lib.loader.compat import ModuleCompatChecker
        return await ModuleCompatChecker(self.kernel).check_module_compatibility(code)
