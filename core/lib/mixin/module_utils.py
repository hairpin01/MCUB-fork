# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

import ast
import os
from typing import TYPE_CHECKING, Any
import re

if TYPE_CHECKING:
    from kernel import Kernel


def is_archive_url(url: str) -> bool:
    """Check if URL points to an archive file."""
    url_lower = url.lower()
    return any(url_lower.endswith(ext) for ext in [".zip", ".tar.gz", ".tgz", ".tar"])


def find_module_case_insensitive(
    loader: Any, name: str
) -> tuple[str | None, str | None]:
    """Look up a module by name ignoring case across loaded and system dicts.

    Args:
        loader: ModuleLoader instance with k (kernel) attribute.
        name: Module name to search for (case-insensitive).

    Returns:
        ``(actual_name, location)`` where *location* is ``'loaded'`` or
        ``'system'``, or ``(None, None)`` if not found.
    """
    name_lower = name.lower()
    for key in loader.k.loaded_modules:
        if key.lower() == name_lower:
            return key, "loaded"
    for key in loader.k.system_modules:
        if key.lower() == name_lower:
            return key, "system"
    return None, None


def get_module_path(loader: Any, module_name: str) -> str:
    """Return the filesystem path for a module file.

    System modules are resolved from ``MODULES_DIR``; user modules from
    ``MODULES_LOADED_DIR``. For archive packages, returns __init__.py path.

    Args:
        loader: ModuleLoader instance with k (kernel) attribute.
        module_name: Module name.

    Returns:
        Absolute path string to the module file.
    """
    k = loader.k

    if module_name in k.system_modules:
        return os.path.join(k.MODULES_DIR, f"{module_name}.py")

    # Check for package directory (archive modules with local imports)
    package_dir = os.path.join(k.MODULES_LOADED_DIR, module_name)
    if os.path.isdir(package_dir):
        init_file = os.path.join(package_dir, "__init__.py")
        if os.path.exists(init_file):
            return init_file

    default_path = os.path.join(k.MODULES_LOADED_DIR, f"{module_name}.py")
    if os.path.exists(default_path):
        return default_path

    # Search for class-style modules by class attribute name parsed via AST.
    try:
        for fname in os.listdir(k.MODULES_LOADED_DIR):
            fpath = os.path.join(k.MODULES_LOADED_DIR, fname)
            if not (os.path.isfile(fpath) and fname.endswith(".py")):
                continue
            try:
                with open(fpath, encoding="utf-8") as f:
                    code = f.read()
                try:
                    tree = ast.parse(code)
                except SyntaxError:
                    continue

                for node in tree.body:
                    if not isinstance(node, ast.ClassDef):
                        continue
                    for stmt in node.body:
                        value_node = None
                        if isinstance(stmt, ast.Assign):
                            for target in stmt.targets:
                                if isinstance(target, ast.Name) and target.id == "name":
                                    value_node = stmt.value
                                    break
                        elif isinstance(stmt, ast.AnnAssign):
                            if (
                                isinstance(stmt.target, ast.Name)
                                and stmt.target.id == "name"
                            ):
                                value_node = stmt.value

                        if value_node is None:
                            continue

                        try:
                            value = ast.literal_eval(value_node)
                        except Exception:
                            continue

                        if isinstance(value, str) and value == module_name:
                            return fpath
            except Exception:
                pass
    except OSError:
        pass

    return default_path


def pick_localized_text(
    values: dict[str, str] | None,
    lang: str | None,
    fallback: str = "",
) -> str:
    """Pick localized text by language with safe fallbacks."""
    if not isinstance(values, dict) or not values:
        return fallback

    normalized = (lang or "en").lower()
    candidates = [normalized]
    if "-" in normalized:
        candidates.append(normalized.split("-", 1)[0])

    # Respect langpack base language (e.g. rofl -> ru) before global fallbacks.
    try:
        from core.langpacks import get_langpacks

        packs = get_langpacks()
        base_lang = packs.get(normalized, {}).get("lang")
        if isinstance(base_lang, str) and base_lang.strip():
            candidates.append(base_lang.strip().lower())
    except Exception:
        pass

    candidates.extend(["ru", "en"])

    for key in candidates:
        value = values.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    for value in values.values():
        if isinstance(value, str) and value.strip():
            return value.strip()

    return fallback


def _parse_class_dependencies(code: str) -> list[str]:
    """Parse class-level ``dependencies`` lists from module source via AST."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    deps: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        for stmt in node.body:
            value: ast.AST | None = None
            if isinstance(stmt, ast.Assign):
                if any(
                    isinstance(target, ast.Name) and target.id == "dependencies"
                    for target in stmt.targets
                ):
                    value = stmt.value
            elif isinstance(stmt, ast.AnnAssign):
                if (
                    isinstance(stmt.target, ast.Name)
                    and stmt.target.id == "dependencies"
                ):
                    value = stmt.value

            if value is None:
                continue

            try:
                parsed = ast.literal_eval(value)
            except Exception:
                continue

            if isinstance(parsed, (list, tuple, set)):
                deps.extend(
                    dep.strip()
                    for dep in parsed
                    if isinstance(dep, str) and dep.strip()
                )

    return deps


def parse_requires(code: str) -> list:
    """Parse dependency declarations from module source.

    Supports both ``# requires: pkg1, pkg2`` comments and class-style
    ``dependencies = ["pkg1", "pkg2"]`` declarations. Unlike
    :meth:`pre_install_requirements`, this method only *parses* the list — it
    does **not** install anything.

    Args:
        code: Module source code string.

    Returns:
        List of requirement strings.
    """
    reqs = []
    for line in code.splitlines():
        match = re.match(r"^\s*#\s*requires\s*:\s*(.*)$", line, re.IGNORECASE)
        if match is None:
            continue

        reqs_line = match.group(1).strip()
        if not reqs_line:
            continue

        parts = [
            token.strip() for token in re.split(r"[,\s]+", reqs_line) if token.strip()
        ]
        reqs.extend(parts)
    reqs.extend(_parse_class_dependencies(code))

    seen: set[str] = set()
    result: list[str] = []
    for req in reqs:
        if req not in seen:
            seen.add(req)
            result.append(req)
    return result


def get_module_commands(loader: Any, module_name: str) -> list:
    """Get all commands registered by a module.

    Args:
        loader: ModuleLoader instance with k (kernel) attribute.
        module_name: Name of the module.

    Returns:
        List of command names.
    """
    k = loader.k
    commands = []

    for cmd, owner in k.command_owners.items():
        if owner == module_name:
            commands.append(cmd)

    return commands
