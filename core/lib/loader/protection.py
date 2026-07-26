# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


class ModuleProtectionError(PermissionError):
    """Raised when a module load request violates the trust policy."""


def sanitize_module_name(name: object) -> str:
    """Return a filesystem-safe module name without changing normal names."""
    text = str(name or "").strip()
    if text.endswith(".py"):
        text = text[:-3]
    text = text.replace("\\", "/")
    text = text.rsplit("/", 1)[-1]
    text = text.replace("..", "").strip()
    return text


def _path_inside(path: str | os.PathLike[str], root: str | os.PathLike[str]) -> bool:
    try:
        resolved_path = Path(path).resolve(strict=False)
        resolved_root = Path(root).resolve(strict=False)
        resolved_path.relative_to(resolved_root)
        return True
    except (OSError, RuntimeError, ValueError):
        return False


class ModuleProtectionPolicy:
    """Centralized trust policy for MCUB module loading.

    User-installed modules may only receive the user trust level. System trust is
    reserved for the boot loader and, when present, the system module manifest.
    """

    def __init__(self, kernel: Any) -> None:
        self.kernel = kernel

    def _kernel_vars(self) -> dict[str, Any]:
        data = getattr(self.kernel, "__dict__", None)
        return data if isinstance(data, dict) else {}

    def system_loader_token(self) -> object:
        data = self._kernel_vars()
        token = data.get("_system_loader_token")
        if token is None:
            token = object()
            self.kernel._system_loader_token = token
        return token

    def begin_system_loading(self) -> object:
        token = self.system_loader_token()
        self.kernel._system_loader_active = True
        return token

    def end_system_loading(self, token: object) -> None:
        if token is self._kernel_vars().get("_system_loader_token"):
            self.kernel._system_loader_active = False

    def assert_system_load_allowed(
        self,
        file_path: str,
        *,
        token: object | None,
        code: str | None = None,
        module_name: str | None = None,
    ) -> None:
        expected_token = self._kernel_vars().get("_system_loader_token")
        if expected_token is None or token is not expected_token:
            raise ModuleProtectionError("System module loading is internal only")
        if not bool(self._kernel_vars().get("_system_loader_active", False)):
            raise ModuleProtectionError("System modules can be loaded only during boot")
        self.assert_system_path_allowed(file_path)
        if module_name and code is not None:
            self.assert_system_manifest_allowed(module_name, file_path, code)

    def assert_system_path_allowed(self, file_path: str) -> None:
        modules_dir = getattr(self.kernel, "MODULES_DIR", None)
        if modules_dir and not _path_inside(file_path, modules_dir):
            raise ModuleProtectionError(
                f"System module path must be inside MODULES_DIR: {file_path}"
            )

    def assert_user_path_allowed(self, file_path: str) -> None:
        modules_dir = getattr(self.kernel, "MODULES_DIR", None)
        if modules_dir and _path_inside(file_path, modules_dir):
            raise ModuleProtectionError(
                "User module loading cannot execute files from the system modules directory"
            )

    def iter_system_names(self) -> tuple[str, ...]:
        modules = getattr(self.kernel, "system_modules", {})
        if not isinstance(modules, dict):
            return ()

        names: set[str] = set()
        for key, module in modules.items():
            names.add(str(key))
            names.add(str(getattr(module, "__name__", "")))
            instance = getattr(module, "_class_instance", None)
            if instance is not None:
                names.add(str(getattr(instance, "name", "")))
                names.add(str(getattr(type(instance), "name", "")))

        return tuple(name for name in names if name)

    def is_system_module_name(self, module_name: str | None) -> bool:
        if not module_name:
            return False
        needle = sanitize_module_name(module_name).casefold()
        return any(name.casefold() == needle for name in self.iter_system_names())

    def assert_user_name_allowed(self, module_name: str | None) -> None:
        if self.is_system_module_name(module_name):
            raise ModuleProtectionError(
                f"User module '{module_name}' conflicts with a protected system module"
            )

    def assert_user_load_allowed(self, module_name: str | None, file_path: str) -> None:
        self.assert_user_path_allowed(file_path)
        self.assert_user_name_allowed(module_name)

    def manifest_path(self) -> Path:
        explicit = getattr(self.kernel, "SYSTEM_MODULES_MANIFEST", None)
        if explicit:
            return Path(explicit)

        modules_dir = Path(str(getattr(self.kernel, "MODULES_DIR", "modules"))).resolve(
            strict=False
        )
        return modules_dir.parent / "core" / "system_modules.json"

    def _load_manifest(self) -> tuple[Path, dict[str, Any]] | None:
        path = self.manifest_path()
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            raise ModuleProtectionError(f"Invalid system module manifest: {path}")
        modules = data.get("modules", data)
        if not isinstance(modules, dict):
            raise ModuleProtectionError(
                f"Invalid system module manifest modules: {path}"
            )
        return path, modules

    def assert_system_manifest_allowed(
        self, module_name: str, file_path: str, code: str
    ) -> None:
        loaded = self._load_manifest()
        if loaded is None:
            # Tests and local forks without a manifest keep the old boot behavior.
            return

        manifest_path, modules = loaded
        clean_name = sanitize_module_name(module_name)
        entry = modules.get(clean_name)
        if not isinstance(entry, dict):
            raise ModuleProtectionError(
                f"System module '{clean_name}' is not declared in {manifest_path}"
            )

        expected_path = entry.get("path")
        if expected_path:
            project_root = (
                manifest_path.parent.parent
                if manifest_path.parent.name == "core"
                else manifest_path.parent
            )
            declared = (project_root / str(expected_path)).resolve(strict=False)
            actual = Path(file_path).resolve(strict=False)
            if actual != declared:
                raise ModuleProtectionError(
                    f"System module '{clean_name}' path mismatch: {actual} != {declared}"
                )

        expected_hash = entry.get("sha256")
        if expected_hash:
            actual_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
            if actual_hash.lower() != str(expected_hash).lower():
                raise ModuleProtectionError(
                    f"System module '{clean_name}' hash mismatch"
                )
