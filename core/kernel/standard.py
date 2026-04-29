# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01
# ---- meta data ------ kernel ----------------------
# author: @Hairpin00
# description: kernel core — main Kernel class
# --- meta data end ---------------------------------
# 🌐 fork MCUBFB: https://github.com/Mitrichdfklwhcluio/MCUBFB
# 🌐 github MCUB-fork: https://github.com/hairpin01/MCUB-fork
# [🌐 https://github.com/hairpin01, 🌐 https://github.com/Mitrichdfklwhcluio, 🌐 https://t.me/HenerTLG]
# ----------------------- end -----------------------
from __future__ import annotations

# Import all mixins for seamless backward compatibility
from core.lib.kernel_core import KernelCoreMixin
from core.lib.kernel_handlers import KernelHandlersMixin
from core.lib.kernel_pipeline import KernelPipelineMixin
from core.lib.kernel_lifecycle import KernelLifecycleMixin


class Kernel(
    KernelCoreMixin,
    KernelHandlersMixin,
    KernelPipelineMixin,
    KernelLifecycleMixin,
):
    """MCUB kernel — orchestrates clients, modules, commands and scheduler.

    This is a thin wrapper class that combines four mixins:
    - KernelCoreMixin: initialization, config, registries, utilities
    - KernelHandlersMixin: handler registration, middleware, modules
    - KernelPipelineMixin: pipeline execution, regex validation, script engine
    - KernelLifecycleMixin: run, shutdown, restart, command processing
    """

    pass
