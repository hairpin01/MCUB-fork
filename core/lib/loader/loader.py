# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

from __future__ import annotations


def _mkfallback(name: str):
    return type(f"_{name}Fallback", (), {})


try:
    from ..mixin.dependency_manager_mixin import DependencyManagerMixin
except ImportError:
    DependencyManagerMixin = _mkfallback("DependencyManager")

try:
    from ..mixin.module_detector_mixin import ModuleDetectorMixin
except ImportError:
    ModuleDetectorMixin = _mkfallback("ModuleDetector")

try:
    from ..mixin.module_loader_mixin import ModuleLoaderMixin
except ImportError:
    ModuleLoaderMixin = _mkfallback("ModuleLoader")

try:
    from ..mixin.module_unloader_mixin import ModuleUnloaderMixin
except ImportError:
    ModuleUnloaderMixin = _mkfallback("ModuleUnloader")

try:
    from ..mixin.system_loader_mixin import SystemLoaderMixin
except ImportError:
    SystemLoaderMixin = _mkfallback("SystemLoader")

try:
    from ..mixin.user_loader_mixin import UserLoaderMixin
except ImportError:
    UserLoaderMixin = _mkfallback("UserLoader")

try:
    from .archive import ArchiveManager
except ImportError:
    ArchiveManager = None


class ModuleLoader(
    ModuleLoaderMixin,
    SystemLoaderMixin,
    UserLoaderMixin,
    ModuleUnloaderMixin,
    DependencyManagerMixin,
    ModuleDetectorMixin,
):
    """Handles dynamic loading, registration, and unloading of modules."""

    def __init__(self, kernel: Kernel) -> None:
        self.k = kernel
        self._archive_mgr = ArchiveManager(kernel) if ArchiveManager else None
        super().__init__()
