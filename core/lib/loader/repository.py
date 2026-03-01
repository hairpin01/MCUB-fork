import json
import ipaddress
import sys
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from kernel import Kernel


class RepositoryManager:
    """Manages module repository URLs: loading, saving, querying."""

    ALLOWED_PROTOCOLS = {"https"}
    BLOCKED_HOSTS = {
        "localhost",
        "localhost.localdomain",
        "0.0.0.0",
        "127.0.0.1",
        "::1",
    }

    def __init__(self, kernel: "Kernel") -> None:
        self.k = kernel
        self._session = None  # shared aiohttp.ClientSession, lazy init

    @property
    def _aiohttp(self):
        """Return the aiohttp module already imported by the kernel."""
        mod = sys.modules.get("aiohttp")
        if mod is None:
            raise RuntimeError(
                "aiohttp is not loaded. Make sure the kernel imported it first."
            )
        return mod

    async def _get_session(self):
        """Return (or lazily create) a shared ClientSession."""
        if self._session is None or self._session.closed:
            self._session = self._aiohttp.ClientSession()
        return self._session

    async def _http_get(self, url: str) -> tuple[int, str | None]:
        """Perform a GET request using the shared session.

        Returns:
            (status_code, text) — text is None on connection error or non-200.
        """
        try:
            session = await self._get_session()
            async with session.get(url) as resp:
                text = await resp.text() if resp.status == 200 else None
                return resp.status, text
        except Exception as exc:
            self.k.logger.debug(f"HTTP GET {url} failed: {exc}")
            return 0, None

    async def close(self) -> None:
        """Close the shared session (call on kernel shutdown)."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None


    def _validate_url(self, url: str) -> tuple[bool, str]:
        """Validate URL for SSRF protection."""
        try:
            parsed = urlparse(url)

            if parsed.scheme not in self.ALLOWED_PROTOCOLS:
                return False, f"Only {', '.join(self.ALLOWED_PROTOCOLS)} protocols allowed"

            host = parsed.hostname
            if not host:
                return False, "Invalid URL: no hostname"

            if host.lower() in self.BLOCKED_HOSTS:
                return False, "Internal hosts not allowed"

            try:
                ip = ipaddress.ip_address(host)
                if ip.is_private or ip.is_loopback or ip.is_reserved:
                    return False, "Private/reserved IP addresses not allowed"
            except ValueError:
                pass  # hostname, not a raw IP — that's fine

            return True, "OK"
        except Exception as exc:
            return False, f"URL validation error: {exc}"

    def load(self) -> None:
        """Load repository list from config into kernel.repositories."""
        self.k.repositories = self.k.config.get("repositories", [])

        validated = []
        for repo in self.k.repositories:
            valid, _ = self._validate_url(repo)
            if valid:
                validated.append(repo)
            else:
                self.k.logger.warning(f"Repository blocked by SSRF protection: {repo}")

        self.k.repositories = validated
        self.k.logger.debug(f"Loaded repositories: {self.k.repositories}")

    async def save(self) -> None:
        """Persist the current repository list to config.json."""
        k = self.k
        k.config["repositories"] = k.repositories
        with open(k.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(k.config, f, ensure_ascii=False, indent=2)
        k.logger.debug("Repositories saved")

    async def add(self, url: str) -> tuple[bool, str]:
        """Add a new repository URL after verifying it has a modules.ini."""
        valid, error_msg = self._validate_url(url)
        if not valid:
            return False, f"URL blocked: {error_msg}"

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
        """Remove a repository by 1-based index."""
        k = self.k
        try:
            idx = int(index) - 1
            if 0 <= idx < len(k.repositories):
                k.repositories.pop(idx)
                await self.save()
                return True, "Repository removed"
            return False, "Invalid index"
        except Exception as exc:
            k.logger.error(f"Remove repository error: {exc}")
            return False, f"Error: {exc}"

    async def get_name(self, url: str) -> str:
        """Fetch the human-readable name from name.ini. Falls back to last URL segment."""
        _, text = await self._http_get(f"{url}/name.ini")
        if text:
            return text.strip()
        return url.rstrip("/").split("/")[-1]

    async def get_modules_list(self, repo_url: str) -> list[str]:
        """Fetch the list of module names from modules.ini."""
        _, text = await self._http_get(f"{repo_url}/modules.ini")
        if text:
            return [line.strip() for line in text.split("\n") if line.strip()]
        return []

    async def download_module(self, repo_url: str, module_name: str) -> str | None:
        """Download module source code from the repository."""
        _, text = await self._http_get(f"{repo_url}/{module_name}.py")
        return text
