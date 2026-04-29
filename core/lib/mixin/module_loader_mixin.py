# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import aiohttp

from ..utils.exceptions import CommandConflictError
from ..loader.module_base import ModuleBase
from .module_utils import (
    find_module_case_insensitive as _find_module_case_insensitive,
    get_module_path as _get_module_path,
    is_archive_url,
    parse_requires as _parse_requires,
    pick_localized_text as _pick_localized_text,
)

if TYPE_CHECKING:
    from kernel import Kernel


class ModuleLoaderMixin:
    """Mixin for loading modules from file, URL, and archives."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    def get_module_commands(
        self, module_name: str, lang: str | None = None
    ) -> tuple[list[str], dict[str, list[str]], dict[str, str]]:
        """Return module commands, aliases, and localized descriptions."""
        k = self.k
        language = (lang or "en").lower()
        language_base = None
        try:
            from core.langpacks import get_langpacks

            packs = get_langpacks()
            base_lang = packs.get(language, {}).get("lang")
            if isinstance(base_lang, str) and base_lang.strip():
                language_base = base_lang.strip().lower()
        except Exception:
            language_base = None

        commands = [
            cmd
            for cmd, owner in getattr(k, "command_owners", {}).items()
            if owner == module_name
        ]

        aliases_info: dict[str, list[str]] = {}
        for alias, target in getattr(k, "aliases", {}).items():
            if target in commands:
                aliases_info.setdefault(target, []).append(alias)

        descriptions: dict[str, str] = {}
        docs_map = getattr(k, "command_docs", {}) or {}
        for cmd in commands:
            doc = docs_map.get(cmd)
            if isinstance(doc, str):
                descriptions[cmd] = doc
                continue
            if not isinstance(doc, dict):
                continue
            picked = (
                doc.get(language)
                or doc.get(language.split("-", 1)[0])
                or (doc.get(language_base) if language_base else None)
                or doc.get("ru")
                or doc.get("en")
            )
            if isinstance(picked, str) and picked.strip():
                descriptions[cmd] = picked.strip()

        return commands, aliases_info, descriptions

    def find_module_case_insensitive(self, name: str) -> tuple[str | None, str | None]:
        return _find_module_case_insensitive(self, name)

    def get_module_path(self, module_name: str) -> str:
        return _get_module_path(self, module_name)

    def pick_localized_text(
        self,
        values: dict[str, str] | None,
        lang: str | None,
        fallback: str = "",
    ) -> str:
        return _pick_localized_text(values, lang, fallback)

    def parse_requires(self, code: str) -> list:
        return _parse_requires(code)

    async def get_module_version_from_file(self, file_path: str) -> str | None:
        """Extract module version from source file."""
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                code = f.read()
        except OSError:
            return None

        # Class-style: version = "1.2.3"
        m = re.search(
            r"^\s*version\s*:\s*[^=]+=\s*['\"]([^'\"]+)['\"]",
            code,
            re.MULTILINE,
        ) or re.search(
            r"^\s*version\s*=\s*['\"]([^'\"]+)['\"]",
            code,
            re.MULTILINE,
        )
        if m:
            version = (m.group(1) or "").strip()
            if version:
                return version

        # Header metadata: # version: 1.2.3
        m = re.search(r"^\s*#\s*version\s*:\s*([^\n#]+)", code, re.MULTILINE)
        if m:
            version = (m.group(1) or "").strip()
            if version:
                return version

        return None

    async def get_module_metadata(self, code: str) -> dict:
        """Parse basic module metadata from source code."""
        metadata: dict[str, Any] = {
            "commands": {},
            "description": "No description",
            "description_i18n": {},
            "version": "?.?.?",
            "author": "unknown",
            "banner_url": None,
            "is_class_style": False,
            "class_name": None,
        }
        if not isinstance(code, str) or not code.strip():
            return metadata

        # Header comments: # author: ..., # version: ..., # description: ...
        m = re.search(r"^\s*#\s*author\s*:\s*(.+)$", code, re.MULTILINE)
        if m:
            metadata["author"] = m.group(1).strip()
        m = re.search(r"^\s*#\s*version\s*:\s*(.+)$", code, re.MULTILINE)
        if m:
            metadata["version"] = m.group(1).strip()
        m = re.search(r"^\s*#\s*description\s*:\s*(.+)$", code, re.MULTILINE)
        if m:
            metadata["description"] = m.group(1).strip()
        m = re.search(r"^\s*#\s*banner(?:_url)?\s*:\s*(.+)$", code, re.MULTILINE)
        if m:
            metadata["banner_url"] = m.group(1).strip()

        # Class-style module detection and attributes.
        class_match = re.search(
            r"class\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*ModuleBase\s*\)\s*:",
            code,
        )
        if class_match:
            metadata["is_class_style"] = True
            class_block_start = class_match.end()
            class_block = code[class_block_start:]
            metadata["class_name"] = class_match.group(1)

            m = re.search(
                r"^\s*name\s*=\s*['\"]([^'\"]+)['\"]", class_block, re.MULTILINE
            )
            if m:
                metadata["class_name"] = m.group(1).strip()

            m = re.search(
                r"^\s*version\s*(?::\s*[^=]+)?=\s*['\"]([^'\"]+)['\"]",
                class_block,
                re.MULTILINE,
            )
            if m:
                metadata["version"] = m.group(1).strip()

            m = re.search(
                r"^\s*author\s*(?::\s*[^=]+)?=\s*['\"]([^'\"]+)['\"]",
                class_block,
                re.MULTILINE,
            )
            if m:
                metadata["author"] = m.group(1).strip()

            for banner_attr in ("banner_url", "banner", "image", "photo"):
                m = re.search(
                    rf"^\s*{banner_attr}\s*(?::\s*[^=]+)?=\s*['\"]([^'\"]+)['\"]",
                    class_block,
                    re.MULTILINE,
                )
                if m:
                    metadata["banner_url"] = m.group(1).strip()
                    break

            # description: dict[str, str] = {"ru": "...", "en": "..."}
            m = re.search(
                r"^\s*description\s*(?::\s*[^=]+)?=\s*(\{[\s\S]*?\})",
                class_block,
                re.MULTILINE,
            )
            if m:
                desc_blob = m.group(1)
                pairs = re.findall(
                    r"['\"]([a-zA-Z_-]+)['\"]\s*:\s*['\"]([^'\"]+)['\"]", desc_blob
                )
                if pairs:
                    i18n = {k.lower(): v.strip() for k, v in pairs}
                    metadata["description_i18n"] = i18n
                    metadata["description"] = (
                        i18n.get("ru") or i18n.get("en") or next(iter(i18n.values()))
                    )
            else:
                m = re.search(
                    r"^\s*description\s*(?::\s*[^=]+)?=\s*['\"]([^'\"]+)['\"]",
                    class_block,
                    re.MULTILINE,
                )
                if m:
                    metadata["description"] = m.group(1).strip()

        # Extract command docs from decorators.
        for cmd, ru_doc, en_doc in re.findall(
            r"@command\(\s*['\"]([^'\"]+)['\"][\s\S]*?doc_ru\s*=\s*['\"]([^'\"]+)['\"][\s\S]*?doc_en\s*=\s*['\"]([^'\"]+)['\"][\s\S]*?\)",
            code,
        ):
            metadata["commands"][cmd] = ru_doc or en_doc

        for cmd, en_doc, ru_doc in re.findall(
            r"@command\(\s*['\"]([^'\"]+)['\"][\s\S]*?doc_en\s*=\s*['\"]([^'\"]+)['\"][\s\S]*?doc_ru\s*=\s*['\"]([^'\"]+)['\"][\s\S]*?\)",
            code,
        ):
            metadata["commands"][cmd] = ru_doc or en_doc

        return metadata

    async def load_module_from_file(
        self,
        file_path: str,
        module_name: str,
        is_system: bool = False,
        is_reload: bool = False,
    ) -> tuple[bool, str]:
        """Load a Python module from *file_path* and register it with the kernel.

        Args:
            file_path: Path to the .py file.
            module_name: Name to register the module under.
            is_system: If True, stores in kernel.system_modules.

        Returns:
            (success, message)

        Raises:
            CommandConflictError: When the module registers a conflicting command.
        """
        k = self.k
        try:
            with open(file_path, encoding="utf-8") as f:
                code = f.read()
            k.logger.debug(
                "[loader.load] start module=%r path=%r system=%s size=%d",
                module_name,
                file_path,
                is_system,
                len(code),
            )

            try:
                from core.lib.loader.hikka_compat import (
                    _detect_module_type,
                    load_hikka_module,
                )

                module_type = _detect_module_type(code)
                if module_type in ("hikka", "geek"):
                    import os as _os

                    abs_path = (
                        file_path
                        if _os.path.isabs(file_path)
                        else _os.path.abspath(file_path)
                    )
                    ok, err, _ = await load_hikka_module(k, abs_path, module_name)
                    return ok, err
            except ImportError:
                pass  # hikka_compat.py not installed, fall through

            ok, msg = await self._check_module_compatibility(code)
            if not ok:
                return False, f"Kernel version mismatch: {msg}"

            incompatible = [
                "from .. import",
                "import loader",
                "__import__('loader')",
                "from hikkalt import",
                "from herokult import",
            ]
            for pat in incompatible:
                if pat in code:
                    try:
                        import os as _os

                        from core.lib.loader.hikka_compat import (
                            load_hikka_module,
                        )

                        abs_path = (
                            file_path
                            if _os.path.isabs(file_path)
                            else _os.path.abspath(file_path)
                        )
                        ok, err, _ = await load_hikka_module(k, abs_path, module_name)
                        return ok, err
                    except ImportError:
                        return (
                            False,
                            "Incompatible module (Heroku/hikka style not supported)",
                        )

            sys.modules.pop(module_name, None)

            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None:
                return False, f"Cannot create module spec for {module_name}"

            module = self._build_module(spec, file_path, module_name)
            sys.modules[module_name] = module

            try:
                module = await self.exec_with_auto_deps(
                    spec, module, file_path, module_name, code
                )
            except ImportError as e:
                return await self.handle_missing_dependency(
                    e, file_path, module_name, is_system
                )
            except SyntaxError as e:
                return False, (
                    f"Syntax error in {Path(file_path).name}: {e.msg}\n"
                    f"  Line {e.lineno}: {e.text}"
                )

            mod_type = await self.detect_module_type(module)
            k.logger.debug(
                "[loader.load] detected module=%r mod_type=%r register=%r",
                module_name,
                mod_type,
                hasattr(module, "register"),
            )

            k.set_loading_module(module_name, "system" if is_system else "user")

            if not await self.register_module(module, mod_type, module_name):
                k.clear_loading_module()
                return False, "Module registration failed"

            class_display_name = None
            if mod_type == "class":
                cls = self._find_module_base_class(module)
                class_display_name = getattr(cls, "name", None) if cls else None

                if (
                    class_display_name
                    and class_display_name != "Unnamed"
                    and class_display_name != module_name
                ):
                    import os

                    old_path = file_path
                    new_path = os.path.join(
                        os.path.dirname(file_path), f"{class_display_name}.py"
                    )

                    if not os.path.exists(new_path):
                        try:
                            os.rename(old_path, new_path)
                            k.logger.info(
                                f"Renamed module file: {module_name} -> {class_display_name}"
                            )
                            file_path = new_path
                        except Exception as e:
                            k.logger.warning(f"Failed to rename module file: {e}")

                    module_name = class_display_name

                k.logger.info(f"Module loaded [class-style]: {module_name}")
                if is_system:
                    k.system_modules[module_name] = module
                else:
                    k.loaded_modules[module_name] = module
            else:
                if is_system:
                    k.system_modules[module_name] = module
                    k.logger.info(f"System module loaded: {module_name}")
                else:
                    k.loaded_modules[module_name] = module
                    k.logger.info(f"User module loaded: {module_name}")

            await self.run_post_load(
                module,
                module_name,
                is_install=not is_reload,
                is_reload=is_reload,
            )
            k.logger.debug(
                "[loader.load] finished module=%r commands=%r aliases=%r",
                module_name,
                [
                    cmd
                    for cmd, owner in k.command_owners.items()
                    if owner == module_name
                ],
                {
                    alias: target
                    for alias, target in k.aliases.items()
                    if target in k.command_handlers
                    and k.command_owners.get(target) == module_name
                },
            )

            if hasattr(module, "init") and callable(module.init):
                try:
                    await module.init()
                except Exception as e:
                    k.logger.error(f"Module {module_name} init() failed: {e}")

            final_module_name = (
                class_display_name if mod_type == "class" else module_name
            )
            return (
                True,
                f"Module {final_module_name} loaded ({mod_type} type)",
            )

        except CommandConflictError:
            raise
        except Exception as e:
            k.logger.error(f"Failed to load {module_name}: {e}", exc_info=True)
            if hasattr(k, "_log") and k._log:
                await k._log.log_error_from_exc(f"load_module:{module_name}")
            return False, f"Module loading error: {e}"
        finally:
            k.clear_loading_module()

    async def install_from_url(
        self,
        url: str,
        module_name: str | None = None,
        auto_dependencies: bool = True,
        expected_hash: str | None = None,
        verify_signature: bool = False,
    ) -> tuple[bool, str]:
        """Download a module from *url* and load it.

        SECURITY WARNING: Loading code from remote URLs without verification
        can lead to RCE (Remote Code Execution) attacks.

        Args:
            url: Direct URL to the .py file.
            module_name: Override the module name (default: derived from URL).
            auto_dependencies: Parse and install ``# requires:`` packages.
            expected_hash: SHA256 hash to verify module code (optional, recommended).
            verify_signature: If True, require signature verification (not implemented).

        Returns:
            (success, message)
        """
        import hashlib
        import os
        import tempfile
        from urllib.parse import urlparse

        k = self.k
        k.logger.debug(
            f"[Loader] install_from_url start url={url} module_name={module_name}"
        )

        TRUSTED_DOMAINS = [
            "raw.githubusercontent.com",
            "github.com",
            "raw.githubusercontentusercontent.com",
        ]

        try:
            parsed = urlparse(url)
            host = (parsed.hostname or "").lower()
            domain = parsed.netloc.lower()
            is_trusted = any(
                host == trusted or host.endswith(f".{trusted}")
                for trusted in TRUSTED_DOMAINS
            )

            if not is_trusted:
                k.logger.warning(
                    f"⚠️ SECURITY: Installing from untrusted domain: {domain}\n"
                    f"   URL: {url}\n"
                    f"   Trusted domains: {', '.join(TRUSTED_DOMAINS)}"
                )

            if not module_name:
                base = os.path.basename(parsed.path)
                module_name = os.path.splitext(base)[0] or "unnamed_module"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as resp:
                    if resp.status != 200:
                        return False, f"HTTP {resp.status} for {url}"
                    code = await resp.text()

            if expected_hash:
                actual = hashlib.sha256(code.encode()).hexdigest()
                if actual != expected_hash:
                    return (
                        False,
                        f"Hash mismatch: expected {expected_hash}, got {actual}",
                    )

            if auto_dependencies:
                await self.pre_install_requirements(code, module_name)

            temp_dir = tempfile.mkdtemp(prefix="mcub_install_")
            file_path = os.path.join(temp_dir, f"{module_name}.py")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(code)

            ok, msg = await self.load_module_from_file(
                file_path, module_name, is_system=False
            )

            if ok:
                import shutil

                final_path = os.path.join(k.MODULES_LOADED_DIR, f"{module_name}.py")
                shutil.move(file_path, final_path)
                shutil.rmtree(temp_dir, ignore_errors=True)
                return True, f"Module {module_name} installed from URL"
            else:
                import shutil

                shutil.rmtree(temp_dir, ignore_errors=True)
                return False, msg

        except Exception as e:
            k.logger.error(f"[Loader] install_from_url error: {e}")
            return False, f"Install from URL failed: {e}"

    async def install_from_archive(
        self,
        url: str,
        module_name: str | None = None,
        auto_dependencies: bool = True,
    ) -> tuple[bool, str]:
        """Download an archive, extract modules, and load them.

        Args:
            url: URL to .zip, .tar.gz, or .tgz archive.
            module_name: Override module name (for single-module archives).
            auto_dependencies: Install ``# requires:`` packages.

        Returns:
            (success, message)
        """
        import os
        import shutil
        import tempfile
        from urllib.parse import urlparse

        k = self.k
        k.logger.debug(f"[Loader] install_from_archive start url={url}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=60) as resp:
                    if resp.status != 200:
                        return False, f"HTTP {resp.status} for {url}"
                    archive_data = await resp.read()

            temp_dir = tempfile.mkdtemp(prefix="mcub_archive_")
            archive_path = os.path.join(temp_dir, "archive.zip")

            with open(archive_path, "wb") as f:
                f.write(archive_data)

            extract_dir = os.path.join(temp_dir, "extracted")
            os.makedirs(extract_dir, exist_ok=True)

            import zipfile
            import tarfile

            if archive_path.endswith((".zip", ".tar.gz", ".tgz", ".tar")):
                if zipfile.is_zipfile(archive_path):
                    with zipfile.ZipFile(archive_path, "r") as zf:
                        zf.extractall(extract_dir)
                elif tarfile.is_tarfile(archive_path):
                    with tarfile.open(archive_path, "r:*") as tf:
                        tf.extractall(extract_dir)
                else:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    return False, "Unknown archive format"
            else:
                shutil.rmtree(temp_dir, ignore_errors=True)
                return False, "Not an archive URL"

            loaded_modules = []
            failed_modules = []

            for root, _dirs, files in os.walk(extract_dir):
                for fname in files:
                    if not fname.endswith(".py"):
                        continue
                    file_path = os.path.join(root, fname)
                    name = module_name or os.path.splitext(fname)[0]

                    with open(file_path, encoding="utf-8") as f:
                        code = f.read()

                    if auto_dependencies:
                        await self.pre_install_requirements(code, name)

                    ok, msg = await self.load_module_from_file(
                        file_path, name, is_system=False
                    )

                    if ok:
                        final_path = os.path.join(k.MODULES_LOADED_DIR, f"{name}.py")
                        shutil.copy2(file_path, final_path)
                        loaded_modules.append(name)
                    else:
                        failed_modules.append(f"{name}: {msg}")

            shutil.rmtree(temp_dir, ignore_errors=True)

            if loaded_modules:
                k.logger.info(
                    f"[Loader] Archive loaded: {loaded_modules}",
                    {"loaded": loaded_modules, "failed": failed_modules},
                )
                return True, f"Loaded modules from archive: {loaded_modules}"
            else:
                return False, f"Failed to load any module: {failed_modules}"

        except Exception as e:
            k.logger.error(f"[Loader] install_from_archive error: {e}")
            return False, f"Install from archive failed: {e}"

    async def handle_missing_dependency(
        self, error: ImportError, file_path: str, module_name: str, is_system: bool
    ) -> tuple[bool, str]:
        """Handle missing dependency by attempting to install it."""
        k = self.k
        error_msg = str(error)
        missing_module = self._extract_missing_module(error_msg)

        if missing_module is None:
            return False, f"Import error: {error_msg}"

        pip_name = self.resolve_pip_name(missing_module)
        k.logger.info(f"[{module_name}] Auto-installing: {pip_name}")

        try:
            await self._pip_install(pip_name, module_name)
        except Exception as install_error:
            k.logger.error(
                f"[{module_name}] Could not install '{pip_name}': {install_error}"
            )
            raise

        k.logger.info(f"[{module_name}] Installed '{pip_name}', reloading...")

        sys.modules.pop(module_name, None)
        new_spec = importlib.util.spec_from_file_location(module_name, file_path)
        if new_spec is None:
            raise ImportError(f"Cannot create spec for {module_name}")

        new_mod = importlib.util.module_from_spec(new_spec)
        new_mod.kernel = k
        new_mod.client = k.client
        new_mod.custom_prefix = k.custom_prefix
        new_mod.__file__ = file_path
        new_mod.__name__ = module_name
        sys.modules[module_name] = new_mod

        await self.exec_with_auto_deps(
            new_spec, new_mod, file_path, module_name, "", 1, {module_name}
        )
        return True, f"Module {module_name} loaded after installing '{pip_name}'"

    @staticmethod
    def _extract_missing_module(error_msg: str) -> str | None:
        """Extract module name from ImportError message."""
        patterns = [
            r"No module named '([^']+)'",
            r"cannot import name '([^']+)'",
        ]
        for pattern in patterns:
            match = re.search(pattern, error_msg)
            if match:
                return match.group(1).split(".")[0]
        return None
