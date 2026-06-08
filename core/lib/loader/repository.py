# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

from __future__ import annotations

import ipaddress
import json
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
BLOCKED_REMOTE_HOSTS = {
    "localhost",
    "localhost.localdomain",
    "0.0.0.0",
    "127.0.0.1",
    "::1",
}


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
                or ip.is_multicast
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
                        or resolved.is_multicast
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
        self.k.logger.debug("[RepoManager] __init__")

    def _validate_url(self, url: str) -> tuple[bool, str]:
        """Validate URL for SSRF protection."""
        self.k.logger.debug(f"[RepoManager] _validate_url url={url}")
        return validate_remote_url(url, allowed_protocols=self.ALLOWED_PROTOCOLS)

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
        """Add a new repository URL after verifying it has a modules.ini.

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
            modules = await self.get_modules_list(url)
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

        Falls back to the last URL segment.
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{url}/name.ini") as resp:
                    if resp.status == 200:
                        return (await resp.text()).strip()
        except Exception as e:
            if hasattr(self.k, "handle_error"):
                await self.k.handle_error(e, message="Repository name fetch failed")
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
        except Exception as e:
            if hasattr(self.k, "handle_error"):
                await self.k.handle_error(
                    e, message="Repository modules list fetch failed"
                )
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
