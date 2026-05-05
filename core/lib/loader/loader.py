# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

from __future__ import annotations

from ..mixin.module_loader_mixin import ModuleLoaderMixin
from ..mixin.system_loader_mixin import SystemLoaderMixin
from ..mixin.user_loader_mixin import UserLoaderMixin
from ..mixin.module_unloader_mixin import ModuleUnloaderMixin
from ..mixin.dependency_manager_mixin import DependencyManagerMixin
from ..mixin.module_detector_mixin import ModuleDetectorMixin
from ..mixin.module_utils import is_archive_url

from ..utils.exceptions import CommandConflictError
from .archive import ArchiveManager


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
        self._archive_mgr = ArchiveManager(kernel)
        super().__init__()
