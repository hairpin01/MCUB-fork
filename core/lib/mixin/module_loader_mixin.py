# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

import ast
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

    def is_archive_url(self, url: str) -> bool:
        """Check if URL points to an archive file."""
        return is_archive_url(url)

    def find_module_case_insensitive(self, name: str) -> tuple[str | None, str | None]:
        """Look up a module by name ignoring case."""
        return _find_module_case_insensitive(self, name)

    def get_module_path(self, module_name: str) -> str:
        """Return the filesystem path for a module file."""
        return _get_module_path(self, module_name)

    def pick_localized_text(
        self, values: dict[str, str] | None, lang: str | None, fallback: str = ""
    ) -> str:
        """Pick localized text by language."""
        return _pick_localized_text(values, lang, fallback)

    def parse_requires(self, code: str) -> list:
        """Parse ``# requires:`` comments from module source."""
        return _parse_requires(code)

    def _parse_source_ast(self, code: str) -> ast.Module | None:
        """Parse python source code into AST."""
        try:
            return ast.parse(code)
        except SyntaxError:
            return None

    def _collect_module_base_aliases(
        self, tree: ast.Module
    ) -> tuple[set[str], set[str], set[str]]:
        """Collect aliases that can reference ModuleBase and command decorator."""
        module_aliases: set[str] = set()
        modulebase_names: set[str] = {"ModuleBase"}
        command_names: set[str] = {"command"}

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
                        local_name = alias.asname or alias.name
                        if alias.name == "ModuleBase":
                            modulebase_names.add(local_name)
                        if alias.name == "command":
                            command_names.add(local_name)
                        if alias.name == "*":
                            modulebase_names.add("ModuleBase")
                            command_names.add("command")

        return module_aliases, modulebase_names, command_names

    def _is_module_base_expr(
        self,
        expr: ast.expr,
        module_aliases: set[str],
        modulebase_names: set[str],
    ) -> bool:
        if isinstance(expr, ast.Name):
            return expr.id in modulebase_names

        if isinstance(expr, ast.Attribute) and expr.attr == "ModuleBase":
            value = expr.value
            if isinstance(value, ast.Name) and value.id in module_aliases:
                return True
            parts: list[str] = []
            cur: ast.expr | None = expr
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                parts.append(cur.id)
                dotted = ".".join(reversed(parts))
                if dotted.endswith("module_base.ModuleBase"):
                    return True

        return False

    def _find_module_base_class_def(
        self, tree: ast.Module
    ) -> tuple[ast.ClassDef | None, set[str]]:
        module_aliases, modulebase_names, command_names = (
            self._collect_module_base_aliases(tree)
        )
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if self._is_module_base_expr(
                        base, module_aliases, modulebase_names
                    ):
                        return node, command_names
        return None, command_names

    def _literal_str(self, value: ast.AST | None) -> str | None:
        if value is None:
            return None
        try:
            parsed = ast.literal_eval(value)
        except Exception:
            return None
        if isinstance(parsed, str):
            parsed = parsed.strip()
            return parsed or None
        return None

    def _literal_dict_str_str(self, value: ast.AST | None) -> dict[str, str]:
        if value is None:
            return {}
        try:
            parsed = ast.literal_eval(value)
        except Exception:
            return {}
        if not isinstance(parsed, dict):
            return {}
        out: dict[str, str] = {}
        for key, val in parsed.items():
            if isinstance(key, str) and isinstance(val, str):
                k = key.strip().lower()
                v = val.strip()
                if k and v:
                    out[k] = v
        return out

    def _assigned_value(self, stmt: ast.stmt, attr_name: str) -> ast.AST | None:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id == attr_name:
                    return stmt.value
        elif isinstance(stmt, ast.AnnAssign):
            if isinstance(stmt.target, ast.Name) and stmt.target.id == attr_name:
                return stmt.value
        return None

    def _parse_header_author(self, raw_value: str) -> str | None:
        value = (raw_value or "").strip()
        if not value:
            return None

        # Common external format:
        # "port: @Hairpin00, author: @TypeFrag"
        nested_author = re.search(
            r"(?:^|[;,])\s*author\s*:\s*(.+)$", value, re.IGNORECASE
        )
        if nested_author:
            value = nested_author.group(1).strip()

        value = re.sub(r"^\s*(?:port|порт)\s*:\s*", "", value, flags=re.IGNORECASE)
        return value.strip() or None

    def _parse_header_description(self, raw_value: str) -> tuple[str, dict[str, str]]:
        value = (raw_value or "").strip()
        if not value:
            return "No description", {}

        # Supports patterns like:
        # "ru: Описание / en: Description"
        # "en: Description | ru: Описание"
        i18n_matches = re.findall(
            r"(?:^|\s*[|/]\s*)(ru|en)\s*:\s*(.*?)(?=\s*[|/]\s*(?:ru|en)\s*:|$)",
            value,
            flags=re.IGNORECASE,
        )
        if i18n_matches:
            desc_i18n: dict[str, str] = {}
            for lang, text in i18n_matches:
                cleaned = text.strip()
                if cleaned:
                    desc_i18n[lang.lower()] = cleaned
            if desc_i18n:
                selected = (
                    desc_i18n.get("ru")
                    or desc_i18n.get("en")
                    or next(iter(desc_i18n.values()))
                )
                return selected, desc_i18n

        return value, {}

    def _extract_command_doc(
        self, decorator: ast.AST, command_names: set[str]
    ) -> tuple[str, str] | None:
        if not isinstance(decorator, ast.Call):
            return None

        is_command_decorator = False
        if isinstance(decorator.func, ast.Name) and decorator.func.id in command_names:
            is_command_decorator = True
        elif (
            isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr == "command"
        ):
            is_command_decorator = True

        if not is_command_decorator or not decorator.args:
            return None

        cmd_name = self._literal_str(decorator.args[0])
        if not cmd_name:
            return None

        doc_ru: str | None = None
        doc_en: str | None = None
        for kw in decorator.keywords:
            if kw.arg == "doc_ru":
                doc_ru = self._literal_str(kw.value)
            elif kw.arg == "doc_en":
                doc_en = self._literal_str(kw.value)

        doc_value = doc_ru or doc_en
        if not doc_value:
            return None

        return cmd_name, doc_value

    def _iter_function_nodes(self, tree: ast.AST):
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                yield node

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

    async def get_module_version_from_file(self, file_path: str) -> str | None:
        """Extract module version from source file."""
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                code = f.read()
        except OSError:
            return None
        metadata = await self.get_module_metadata(code)
        version = metadata.get("version")
        if isinstance(version, str) and version and version != "?.?.?":
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
            header_author = self._parse_header_author(m.group(1))
            if header_author:
                metadata["author"] = header_author
        m = re.search(r"^\s*#\s*version\s*:\s*(.+)$", code, re.MULTILINE)
        if m:
            metadata["version"] = m.group(1).strip()
        m = re.search(r"^\s*#\s*description\s*:\s*(.+)$", code, re.MULTILINE)
        if m:
            header_desc, header_i18n = self._parse_header_description(m.group(1))
            metadata["description"] = header_desc
            if header_i18n:
                metadata["description_i18n"] = header_i18n
        m = re.search(r"^\s*#\s*banner(?:_url)?\s*:\s*(.+)$", code, re.MULTILINE)
        if m:
            metadata["banner_url"] = m.group(1).strip()

        tree = self._parse_source_ast(code)
        if not tree:
            return metadata

        class_node, command_names = self._find_module_base_class_def(tree)
        if class_node is not None:
            metadata["is_class_style"] = True
            metadata["class_name"] = class_node.name

            class_name = self._literal_str(
                next(
                    (
                        self._assigned_value(stmt, "name")
                        for stmt in class_node.body
                        if self._assigned_value(stmt, "name") is not None
                    ),
                    None,
                )
            )
            if class_name:
                metadata["class_name"] = class_name

            class_version = self._literal_str(
                next(
                    (
                        self._assigned_value(stmt, "version")
                        for stmt in class_node.body
                        if self._assigned_value(stmt, "version") is not None
                    ),
                    None,
                )
            )
            if class_version:
                metadata["version"] = class_version

            class_author = self._literal_str(
                next(
                    (
                        self._assigned_value(stmt, "author")
                        for stmt in class_node.body
                        if self._assigned_value(stmt, "author") is not None
                    ),
                    None,
                )
            )
            if class_author:
                metadata["author"] = class_author

            for banner_attr in ("banner_url", "banner", "image", "photo"):
                value = next(
                    (
                        self._assigned_value(stmt, banner_attr)
                        for stmt in class_node.body
                        if self._assigned_value(stmt, banner_attr) is not None
                    ),
                    None,
                )
                banner_val = self._literal_str(value)
                if banner_val:
                    metadata["banner_url"] = banner_val
                    break

            desc_value = next(
                (
                    self._assigned_value(stmt, "description")
                    for stmt in class_node.body
                    if self._assigned_value(stmt, "description") is not None
                ),
                None,
            )
            desc_i18n = self._literal_dict_str_str(desc_value)
            if desc_i18n:
                metadata["description_i18n"] = desc_i18n
                metadata["description"] = (
                    desc_i18n.get("ru")
                    or desc_i18n.get("en")
                    or next(iter(desc_i18n.values()))
                )
            else:
                desc_text = self._literal_str(desc_value)
                if desc_text:
                    metadata["description"] = desc_text
                else:
                    class_doc = ast.get_docstring(class_node)
                    if isinstance(class_doc, str):
                        class_doc = class_doc.strip()
                        if class_doc:
                            metadata["description"] = class_doc

        for func_node in self._iter_function_nodes(tree):
            for dec in func_node.decorator_list:
                command_doc = self._extract_command_doc(dec, command_names)
                if command_doc is None:
                    continue
                cmd, doc = command_doc
                metadata["commands"][cmd] = doc

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
            original_module_name = module_name
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

                    for cmd, owner in list(k.command_owners.items()):
                        if owner == original_module_name:
                            k.command_owners[cmd] = class_display_name

                    for cmd, owner in list(k.bot_command_owners.items()):
                        if owner == original_module_name:
                            k.bot_command_owners[cmd] = class_display_name

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
