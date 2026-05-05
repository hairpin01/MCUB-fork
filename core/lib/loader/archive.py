# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

import ast
import io
import os
import tarfile
import tomllib
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

            data = tomllib.loads(content)

            project = data.get("project")
            if isinstance(project, dict):
                name = project.get("name")
                if isinstance(name, str) and name.strip():
                    meta.name = name.strip()

                version = project.get("version")
                if isinstance(version, str) and version.strip():
                    meta.version = version.strip()

                dependencies = project.get("dependencies")
                if isinstance(dependencies, list):
                    meta.dependencies = [
                        dep.strip()
                        for dep in dependencies
                        if isinstance(dep, str) and dep.strip()
                    ]

            tool = data.get("tool")
            if isinstance(tool, dict):
                mcub = tool.get("mcub")
                if isinstance(mcub, dict):
                    main_module = mcub.get("main")
                    if isinstance(main_module, str) and main_module.strip():
                        meta.main_module = main_module.strip()

                    pack_type = mcub.get("type")
                    if isinstance(pack_type, str) and pack_type.strip():
                        meta.pack_type = pack_type.strip()

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
            if self._has_module_entrypoint(full_path):
                has_multiple_with_register += 1

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
        """Find main module: 1) mcub.main from pyproject, 2) first with entrypoint, 3) error."""
        meta = getattr(self, "_cached_meta", None)

        if meta and meta.main_module:
            for mod in modules:
                if mod.name == meta.main_module or mod.file_path == meta.main_module:
                    return mod

        for mod in modules:
            full_path = os.path.join(extracted_dir, mod.file_path)
            if self._has_module_entrypoint(full_path):
                return mod

        return None

    def _has_module_entrypoint(self, file_path: str) -> bool:
        if not os.path.exists(file_path):
            return False
        try:
            with open(file_path, encoding="utf-8") as f:
                code = f.read()
            tree = ast.parse(code)
        except Exception:
            return False

        return self._has_register_function(tree) or self._has_module_base_class(tree)

    def _has_register_function(self, tree: ast.AST) -> bool:
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == "register":
                    return True
        return False

    def _has_module_base_class(self, tree: ast.AST) -> bool:
        module_aliases: set[str] = set()
        modulebase_names: set[str] = {"ModuleBase"}

        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported = alias.name
                    as_name = alias.asname or imported.split(".")[-1]
                    if imported.endswith("module_base"):
                        module_aliases.add(as_name)
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if mod.endswith("module_base"):
                    for alias in node.names:
                        if alias.name == "ModuleBase":
                            modulebase_names.add(alias.asname or alias.name)

        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            for base in node.bases:
                if isinstance(base, ast.Name) and base.id in modulebase_names:
                    return True
                if isinstance(base, ast.Attribute) and base.attr == "ModuleBase":
                    if (
                        isinstance(base.value, ast.Name)
                        and base.value.id in module_aliases
                    ):
                        return True

        return False
