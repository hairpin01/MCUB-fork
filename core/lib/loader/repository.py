import json
from typing import TYPE_CHECKING

import aiohttp

if TYPE_CHECKING:
    from kernel import Kernel


class RepositoryManager:
    """Manages module repository URLs: loading, saving, querying."""

    def __init__(self, kernel: "Kernel") -> None:
        self.k = kernel

    def load(self) -> None:
        """Load repository list from config into kernel.repositories."""
        self.k.repositories = self.k.config.get("repositories", [])
        self.k.logger.debug(f"Loaded repositories: {self.k.repositories}")

    async def save(self) -> None:
        """Persist the current repository list to config.json."""
        k = self.k
        k.config["repositories"] = k.repositories
        with open(k.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(k.config, f, ensure_ascii=False, indent=2)
        k.logger.debug("Repositories saved")

    async def add(self, url: str) -> tuple[bool, str]:
        """Add a new repository URL after verifying it has a modules.ini.

        Returns:
            (success, message)
        """
        k = self.k
        if url in k.repositories or url == k.default_repo:
            return False, "Repository already exists"
        try:
            modules = await self.get_modules_list(url)
            if modules:
                k.repositories.append(url)
                await self.save()
                return True, f"Repository added ({len(modules)} modules)"
            return False, "Could not retrieve module list"
        except Exception:
            return False, "Error verifying repository"

    async def remove(self, index: int | str) -> tuple[bool, str]:
        """Remove a repository by 1-based index.

        Returns:
            (success, message)
        """
        k = self.k
        try:
            idx = int(index) - 1
            if 0 <= idx < len(k.repositories):
                k.repositories.pop(idx)
                await self.save()
                return True, "Repository removed"
            return False, "Invalid index"
        except Exception as e:
            k.logger.error(f"Remove repository error: {e}")
            return False, f"Error: {e}"

    async def get_name(self, url: str) -> str:
        """Fetch the human-readable name from ``name.ini`` in the repository.

        Falls back to the last URL segment.
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{url}/name.ini") as resp:
                    if resp.status == 200:
                        return (await resp.text()).strip()
        except Exception:
            pass
        return url.rstrip("/").split("/")[-1]

    async def get_modules_list(self, repo_url: str) -> list[str]:
        """Fetch the list of module names from ``modules.ini``.

        Returns:
            List of module name strings, or empty list on failure.
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{repo_url}/modules.ini") as resp:
                    if resp.status == 200:
                        return [
                            line.strip()
                            for line in (await resp.text()).split("\n")
                            if line.strip()
                        ]
        except Exception:
            pass
        return []

    async def download_module(self, repo_url: str, module_name: str) -> str | None:
        """Download module source code from the repository.

        Returns:
            Source code string, or None on failure.
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{repo_url}/{module_name}.py") as resp:
                    if resp.status == 200:
                        return await resp.text()
        except Exception:
            pass
        return None
