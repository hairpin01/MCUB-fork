# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

import io
import os
import re
import tarfile
import zipfile
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import aiohttp

if TYPE_CHECKING:
    from kernel import Kernel


TRUSTED_DOMAINS = {
    "raw.githubusercontent.com",
    "github.com",
    "raw.githubusercontentusercontent.com",
    "raw.github.com",
}


@dataclass
class PyProjectMeta:
    name: str | None = None
    version: str | None = None
    dependencies: list[str] = None
    main_module: str | None = None
    pack_type: str | None = None  # "single" or "pack"


@dataclass
class ModuleInfo:
    name: str
    file_path: str  # относительный путь внутри архива
    is_main: bool = False


@dataclass
class ExtractionResult:
    success: bool
    extracted_dir: str | None = None
    modules: list[ModuleInfo] | None = None
    metadata: PyProjectMeta | None = None
    pack_type: str | None = None  # "single" or "pack"
    error: str | None = None


class ArchiveManager:
    def __init__(self, kernel: Kernel) -> None:
        self.k = kernel
        self.k.logger.debug("[ArchiveManager] __init__")

    async def download(self, url: str) -> bytes | None:
        """Download archive from URL."""
        self.k.logger.debug(f"[ArchiveManager] download url={url}")

        valid, error = self._validate_url(url)
        if not valid:
            self.k.logger.error(f"[ArchiveManager] URL blocked: {error}")
            return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        self.k.logger.error(
                            f"[ArchiveManager] Download failed: HTTP {resp.status}"
                        )
                        return None
                    return await resp.read()
        except Exception as e:
            self.k.logger.error(f"[ArchiveManager] Download error: {e}")
            return None

    def _validate_url(self, url: str) -> tuple[bool, str]:
        """Validate URL for SSRF protection."""
        try:
            parsed = urlparse(url)

            if parsed.scheme not in {"https", "http"}:
                return False, "Only https/http protocols allowed"

            host = parsed.hostname
            if not host:
                return False, "Invalid URL: no hostname"

            host_lower = host.lower()
            if host_lower in {
                "localhost",
                "localhost.localdomain",
                "0.0.0.0",
                "127.0.0.1",
                "::1",
            }:
                return False, "Internal hosts not allowed"

            is_trusted = any(
                host_lower == trusted or host_lower.endswith(f".{trusted}")
                for trusted in TRUSTED_DOMAINS
            )
            if not is_trusted:
                self.k.logger.warning(
                    f"[ArchiveManager] Installing from untrusted domain: {host_lower}"
                )

            return True, "OK"
        except Exception as e:
            return False, f"URL validation error: {e}"

    def validate(self, archive_bytes: bytes) -> bool:
        """Validate archive contains Python files."""
        try:
            with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
                names = zf.namelist()
                has_py = any(f.endswith(".py") for f in names)
                if not has_py:
                    self.k.logger.error("[ArchiveManager] No .py files in archive")
                    return False
            return True
        except zipfile.BadZipFile:
            try:
                with tarfile.open(fileobj=io.BytesIO(archive_bytes)) as tf:
                    names = tf.getnames()
                    has_py = any(f.endswith(".py") for f in names)
                    if not has_py:
                        self.k.logger.error("[ArchiveManager] No .py files in archive")
                        return False
                return True
            except Exception as e:
                self.k.logger.error(f"[ArchiveManager] Invalid archive: {e}")
                return False
        except Exception as e:
            self.k.logger.error(f"[ArchiveManager] Validation error: {e}")
            return False

    async def extract(self, archive_bytes: bytes, target_dir: str) -> ExtractionResult:
        """Extract archive to target directory."""
        self.k.logger.debug(f"[ArchiveManager] extract target={target_dir}")

        os.makedirs(target_dir, exist_ok=True)

        try:
            with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
                for member in zf.namelist():
                    member_path = os.path.join(target_dir, member)
                    if ".." in member:
                        self.k.logger.error(
                            f"[ArchiveManager] Path traversal detected: {member}"
                        )
                        return ExtractionResult(
                            success=False, error="Path traversal detected"
                        )
                    if member.endswith("/"):
                        os.makedirs(member_path, exist_ok=True)
                    else:
                        os.makedirs(os.path.dirname(member_path), exist_ok=True)
                        with zf.open(member) as src, open(member_path, "wb") as dst:
                            dst.write(src.read())

            return await self._process_extracted(target_dir)

        except zipfile.BadZipFile:
            try:
                with tarfile.open(fileobj=io.BytesIO(archive_bytes)) as tf:
                    for member in tf.getmembers():
                        if ".." in member.name:
                            self.k.logger.error(
                                f"[ArchiveManager] Path traversal: {member.name}"
                            )
                            return ExtractionResult(
                                success=False, error="Path traversal detected"
                            )
                        tf.extract(member, target_dir)

                return await self._process_extracted(target_dir)
            except Exception as e:
                return ExtractionResult(success=False, error=f"Extract error: {e}")

        except Exception as e:
            return ExtractionResult(success=False, error=f"Extract error: {e}")

    async def _process_extracted(self, extracted_dir: str) -> ExtractionResult:
        """Process extracted archive: detect type, parse metadata, find modules."""
        metadata = self._parse_pyproject(extracted_dir)
        pack_type = self._detect_type(extracted_dir, metadata)

        modules = self._find_modules(extracted_dir, pack_type)

        if pack_type == "single":
            if not modules:
                return ExtractionResult(
                    success=False, error="No Python modules found in archive"
                )

            main_module = self._find_main_module(modules, extracted_dir)
            if not main_module:
                return ExtractionResult(
                    success=False,
                    error="register function not found in any module file",
                )

            for mod in modules:
                mod.is_main = mod.file_path == main_module.file_path

        return ExtractionResult(
            success=True,
            extracted_dir=extracted_dir,
            modules=modules,
            metadata=metadata,
            pack_type=pack_type,
        )

    def _parse_pyproject(self, extracted_dir: str) -> PyProjectMeta:
        """Parse pyproject.toml for metadata and dependencies."""
        meta = PyProjectMeta()
        meta.dependencies = []

        pyproject_path = os.path.join(extracted_dir, "pyproject.toml")
        if not os.path.exists(pyproject_path):
            return meta

        try:
            with open(pyproject_path, encoding="utf-8") as f:
                content = f.read()

            meta.name = self._extract_toml_value(content, "project", "name")
            meta.version = self._extract_toml_value(content, "project", "version")

            deps_section = re.search(
                r"\[project\]\s*\n(.*?)(?:\n\[|\Z)", content, re.DOTALL
            )
            if deps_section:
                deps_text = deps_section.group(1)
                dep_matches = re.findall(
                    r"^dependencies\s*=\s*\[(.*?)\]",
                    deps_text,
                    re.DOTALL | re.MULTILINE,
                )
                if dep_matches:
                    deps_str = dep_matches[0]
                    meta.dependencies = self._parse_toml_list(deps_str)

            mcub_section = re.search(
                r"\[tool\.mcub\](.*?)(?:\n\[|\Z)", content, re.DOTALL
            )
            if mcub_section:
                mcub_text = mcub_section.group(1)
                meta.main_module = self._extract_value(mcub_text, "main")
                meta.pack_type = self._extract_value(mcub_text, "type")

            req_path = os.path.join(extracted_dir, "requirements.txt")
            if os.path.exists(req_path) and not meta.dependencies:
                with open(req_path, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            meta.dependencies.append(line)

            self.k.logger.debug(
                f"[ArchiveManager] pyproject parsed: name={meta.name}, "
                f"deps={meta.dependencies}, main={meta.main_module}, type={meta.pack_type}"
            )

        except Exception as e:
            self.k.logger.error(f"[ArchiveManager] pyproject parse error: {e}")

        return meta

    def _extract_toml_value(self, content: str, section: str, key: str) -> str | None:
        """Extract value from TOML section."""
        pattern = rf"\[{section}\](.*?)(?:\n\[|\Z)"
        match = re.search(pattern, content, re.DOTALL)
        if not match:
            return None
        return self._extract_value(match.group(1), key)

    def _extract_value(self, text: str, key: str) -> str | None:
        """Extract key=value from text."""
        pattern = rf'^{key}\s*=\s*["\']?([^"\'\n]+)["\']?'
        match = re.search(pattern, text, re.MULTILINE)
        if match:
            return match.group(1).strip()
        return None

    def _parse_toml_list(self, text: str) -> list[str]:
        """Parse TOML list like ['dep1', 'dep2']."""
        deps = []
        matches = re.findall(r'"([^"]+)"', text)
        for m in matches:
            deps.append(m.strip())
        return deps

    def _detect_type(self, extracted_dir: str, metadata: PyProjectMeta) -> str:
        """Detect archive type: single or pack."""
        if metadata.pack_type:
            return metadata.pack_type

        py_files = []
        for root, _, files in os.walk(extracted_dir):
            for f in files:
                if f.endswith(".py"):
                    rel_path = os.path.relpath(os.path.join(root, f), extracted_dir)
                    py_files.append(rel_path)

        if len(py_files) == 1:
            return "single"

        has_multiple_with_register = 0
        for py_file in py_files:
            full_path = os.path.join(extracted_dir, py_file)
            try:
                with open(full_path, encoding="utf-8") as f:
                    code = f.read()
                if "def register" in code or "register(" in code:
                    has_multiple_with_register += 1
            except Exception:
                pass

        if has_multiple_with_register > 1:
            return "pack"

        return "single"

    def _find_modules(self, extracted_dir: str, pack_type: str) -> list[ModuleInfo]:
        """Find all Python modules in extracted archive."""
        modules = []

        for root, _, files in os.walk(extracted_dir):
            for f in files:
                if f.endswith(".py"):
                    rel_path = os.path.relpath(os.path.join(root, f), extracted_dir)

                    if f.startswith("_") and f != "__init__.py":
                        continue
                    if rel_path.startswith("__pycache__"):
                        continue

                    name = f[:-3]
                    if name == "__init__":
                        continue

                    modules.append(ModuleInfo(name=name, file_path=rel_path))

        self.k.logger.debug(
            f"[ArchiveManager] found modules: {[m.name for m in modules]}"
        )
        return modules

    def _find_main_module(
        self, modules: list[ModuleInfo], extracted_dir: str
    ) -> ModuleInfo | None:
        """Find main module: 1) mcub.main from pyproject, 2) first with register(), 3) error."""
        meta = getattr(self, "_cached_meta", None)

        if meta and meta.main_module:
            for mod in modules:
                if mod.name == meta.main_module or mod.file_path == meta.main_module:
                    return mod

        for mod in modules:
            full_path = os.path.join(extracted_dir, mod.file_path)
            if os.path.exists(full_path):
                try:
                    with open(full_path, encoding="utf-8") as f:
                        code = f.read()
                    if "def register" in code or "async def register" in code:
                        return mod
                except Exception:
                    pass

        return None
