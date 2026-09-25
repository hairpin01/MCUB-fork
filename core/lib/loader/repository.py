# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

from __future__ import annotations

import asyncio
import json
import time
from typing import TYPE_CHECKING
from urllib.parse import urlparse

try:
    import aiohttp
except ImportError:
    aiohttp = None
    print(
        "\033[93m⚠  Degraded: aiohttp not installed - repo listing/download will fail\033[0m"
    )

if TYPE_CHECKING:
    from kernel import Kernel


ALLOWED_REMOTE_PROTOCOLS = {"https"}
REPO_MODULE_LIST_FILES = ("modules.ini", "full.txt")
BLOCKED_REMOTE_HOSTS = {
    "localhost",
    "localhost.localdomain",
    "0.0.0.0",
    "127.0.0.1",
    "::1",
}

MAX_RESPONSE_SIZE = 2 * 1024 * 1024  # 2 MB
_CACHE_TTL_MODULES = 600  # 10 min
_CACHE_TTL_NAME = 3600  # 1 hour


def parse_repo_modules_list(text: str) -> list[str]:
    """Parse a repository module list file.

    ``modules.ini`` source, or ``full.txt`` can provide
    the same line-based format.  Entries may be plain module names or
    ``name.py`` filenames; comments and empty lines are ignored.
    """

    modules: list[str] = []
    seen: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("#", ";")):
            continue
        for marker in (" #", " ;"):
            if marker in line:
                line = line.split(marker, maxsplit=1)[0].strip()
        if line.endswith(".py"):
            line = line[:-3]
        if not line or line in seen:
            continue
        seen.add(line)
        modules.append(line)
    return modules


def merge_repo_modules_lists(*lists: list[str]) -> list[str]:
    """Merge repository module lists with order-preserving de-duplication."""

    merged: list[str] = []
    seen: set[str] = set()
    for modules in lists:
        for module in modules:
            if module in seen:
                continue
            seen.add(module)
            merged.append(module)
    return merged


def validate_remote_url(
    url: str,
    *,
    allowed_protocols: set[str] | None = None,
) -> tuple[bool, str]:
    """Validate remote URL against basic SSRF protections."""
    import ipaddress

    protocols = allowed_protocols or ALLOWED_REMOTE_PROTOCOLS
    try:
        parsed = urlparse(url)

        if parsed.scheme not in protocols:
            return False, f"Only {', '.join(sorted(protocols))} protocols allowed"

        host = parsed.hostname
        if not host:
            return False, "Invalid URL: no hostname"

        host_lower = host.lower()
        if host_lower in BLOCKED_REMOTE_HOSTS:
            return False, "Internal hosts not allowed"

        try:
            ip = ipaddress.ip_address(host)
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_reserved
                or ip.is_link_local
                or ip.is_unspecified
            ):
                return False, "Private/reserved IP addresses not allowed"
        except ValueError:
            # Host is a hostname, not a literal IP.
            # Resolve and validate all resulting addresses to prevent DNS-rebinding
            # and wildcard-DNS SSRF (e.g. "10.0.0.1.nip.io").
            import socket

            try:
                infos = socket.getaddrinfo(host, None)
            except socket.gaierror:
                return False, f"Cannot resolve hostname: {host}"
            for info in infos:
                addr = info[4][0]
                try:
                    resolved = ipaddress.ip_address(addr)
                    if (
                        resolved.is_private
                        or resolved.is_loopback
                        or resolved.is_reserved
                        or resolved.is_link_local
                        or resolved.is_unspecified
                    ):
                        return (
                            False,
                            f"Hostname resolves to private/reserved IP: {addr}",
                        )
                except ValueError:
                    pass

        return True, "OK"
    except Exception as e:
        return False, f"URL validation error: {e}"


class RepositoryManager:
    """Manages module repository URLs: loading, saving, querying."""

    ALLOWED_PROTOCOLS = ALLOWED_REMOTE_PROTOCOLS
    BLOCKED_HOSTS = BLOCKED_REMOTE_HOSTS

    def __init__(self, kernel: Kernel) -> None:
        self.k = kernel
        self._session: aiohttp.ClientSession | None = None
        self._cache: dict[str, tuple[object, float]] = {}
        self.k.logger.debug("[RepoManager] __init__")

    def _validate_url(self, url: str) -> tuple[bool, str]:
        """Validate URL for SSRF protection."""
        self.k.logger.debug(f"[RepoManager] _validate_url url={url}")
        return validate_remote_url(url, allowed_protocols=self.ALLOWED_PROTOCOLS)

    def _cache_get(self, key: str) -> object | None:
        entry = self._cache.get(key)
        if entry and time.monotonic() < entry[1]:
            return entry[0]
        self._cache.pop(key, None)
        return None

    def _cache_set(self, key: str, value: object, ttl: float) -> None:
        self._cache[key] = (value, time.monotonic() + ttl)

    async def _get_session(self) -> aiohttp.ClientSession:
        """Return (creating if needed) the shared aiohttp session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_read=15)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self) -> None:
        """Close the shared HTTP session. Call on kernel shutdown."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def _fetch_text(
        self,
        url: str,
        *,
        max_size: int = MAX_RESPONSE_SIZE,
    ) -> str | None:
        """GET *url*, returning decoded text or None on any failure"""
        session = await self._get_session()
        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                ct = resp.headers.get("Content-Type", "")
                if ct and "text" not in ct and "octet-stream" not in ct:
                    self.k.logger.warning(
                        f"[RepoManager] Unexpected Content-Type {ct!r} for {url}"
                    )
                    return None
                cl = resp.content_length
                if cl is not None and cl > max_size:
                    self.k.logger.warning(
                        f"[RepoManager] Response too large ({cl} B) for {url}"
                    )
                    return None
                data = await resp.content.read(max_size + 1)
                if len(data) > max_size:
                    self.k.logger.warning(
                        f"[RepoManager] Response exceeded {max_size} B for {url}"
                    )
                    return None
                return data.decode(errors="replace")
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            self.k.logger.debug(f"[RepoManager] _fetch_text error {url}: {e}")
            return None

    def load(self) -> None:
        """Load repository list from config into kernel.repositories."""
        self.k.logger.debug("[RepoManager] load start")
        self.k.repositories = self.k.config.get("repositories", [])

        validated_repos = []
        for repo in self.k.repositories:
            valid, _ = self._validate_url(repo)
            if valid:
                validated_repos.append(repo)
            else:
                self.k.logger.warning(f"Repository blocked by SSRF protection: {repo}")

        self.k.repositories = validated_repos
        self.k.logger.debug(f"[RepoManager] Loaded repositories: {self.k.repositories}")

    async def save(self) -> None:
        """Persist the current repository list to config.json."""
        k = self.k
        k.config["repositories"] = k.repositories
        with open(k.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(k.config, f, ensure_ascii=False, indent=2)
        k.logger.debug("Repositories saved")

    async def add(self, url: str) -> tuple[bool, str]:
        """Add a new repository URL after verifying it has a modules list.

        Returns:
            (success, message)
        """
        valid, error_msg = self._validate_url(url)
        if not valid:
            return False, f"URL blocked: {error_msg}"

        k = self.k
        if url in k.repositories or url == k.default_repo:
            return False, "Repository already exists"
        try:
            modules = await self.get_modules_list(url, use_cache=False)
            if modules:
                k.repositories.append(url)
                await self.save()
                return True, f"Repository added ({len(modules)} modules)"
            return False, "Could not retrieve module list"
        except Exception as e:
            if hasattr(self.k, "handle_error"):
                await self.k.handle_error(e, message="Repository add failed")
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
            if hasattr(k, "handle_error"):
                await k.handle_error(e, message="Repository remove failed")
            return False, f"Error: {e}"

    async def get_name(self, url: str) -> str:
        """Fetch the human-readable name from ``name.ini`` in the repository.

        Falls back to the last URL segment. Result is cached for 1 hour.
        """
        cache_key = f"name:{url}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached  # type: ignore[return-value]

        valid, _ = self._validate_url(url)
        fallback = url.rstrip("/").split("/")[-1]
        if not valid:
            return fallback

        text = await self._fetch_text(f"{url.rstrip('/')}/name.ini")
        name = text.strip() if text else fallback
        self._cache_set(cache_key, name, _CACHE_TTL_NAME)
        return name

    async def get_modules_list(
        self,
        repo_url: str,
        *,
        use_cache: bool = True,
    ) -> list[str]:
        """Fetch module names from repository list files.

        ``modules.ini`` and ``full.txt`` are fetched in parallel and merged.
        Result is cached for 10 minutes by default.

        Returns:
            List of module name strings, or empty list on failure.
        """
        cache_key = f"modules:{repo_url}"
        if use_cache:
            cached = self._cache_get(cache_key)
            if cached is not None:
                return cached  # type: ignore[return-value]

        valid, err = self._validate_url(repo_url)
        if not valid:
            self.k.logger.warning(f"[RepoManager] get_modules_list blocked: {err}")
            return []

        base = repo_url.rstrip("/")
        results = await asyncio.gather(
            *[self._fetch_text(f"{base}/{f}") for f in REPO_MODULE_LIST_FILES],
            return_exceptions=True,
        )
        lists = [parse_repo_modules_list(r) for r in results if isinstance(r, str)]
        modules = merge_repo_modules_lists(*lists)

        if use_cache:
            self._cache_set(cache_key, modules, _CACHE_TTL_MODULES)
        return modules

    async def get_legacy_modules_list(self, repo_url: str) -> list[str]:
        """Fetch only the legacy ``modules.ini`` list.

        Kept as a narrow compatibility helper for callers that explicitly need
        the old source.  Normal code should use ``get_modules_list``.
        """
        valid, err = self._validate_url(repo_url)
        if not valid:
            self.k.logger.warning(
                f"[RepoManager] get_legacy_modules_list blocked: {err}"
            )
            return []

        text = await self._fetch_text(f"{repo_url.rstrip('/')}/modules.ini")
        return parse_repo_modules_list(text) if text else []

    async def download_module(self, repo_url: str, module_name: str) -> str | None:
        """Download module source code from the repository.

        Returns:
            Source code string, or None on failure.
        """
        module_url = f"{repo_url.rstrip('/')}/{module_name}.py"
        valid, err = self._validate_url(module_url)
        if not valid:
            self.k.logger.warning(f"[RepoManager] download_module blocked: {err}")
            return None
        return await self._fetch_text(module_url)
