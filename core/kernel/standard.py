# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01
# ---- meta data ------ kernel ----------------------
# author: @Hairpin00
# description: kernel core - main Kernel class
# --- meta data end ---------------------------------
# 🌐 fork MCUBFB: https://github.com/Mitrichdfklwhcluio/MCUBFB
# 🌐 github MCUB-fork: https://github.com/hairpin01/MCUB-fork
# [🌐 https://github.com/hairpin01, 🌐 https://github.com/Mitrichdfklwhcluio, 🌐 https://t.me/HenerTLG]
# ----------------------- end -----------------------
from __future__ import annotations


class _MissingMeta(type):
    """Metaclass for a kernel that failed to load its mixins."""

    def __getattr__(cls, name):
        return cls


class _MissingKernel(metaclass=_MissingMeta):
    """Fallback kernel when mixin imports fail - prevents crash."""

    def __init__(self, *a, **kw):
        print("\033[91m\033[1mKernel unavailable - mixin imports failed\033[0m")

    def __getattr__(self, name):
        return self

    async def __call__(self, *a, **kw):
        pass

    def __bool__(self):
        return False


def _make_fallback(name: str):
    """Create a unique fallback class for a failed mixin import."""
    return type(f"_{name}Fallback", (), {})


# Import mixins - if any fails, use the fallback
try:
    from core.lib.kernel_core import KernelCoreMixin
except Exception as e:
    print(f"\033[93mKernelCoreMixin import failed: {e}\033[0m")
    KernelCoreMixin = _MissingKernel  # type: ignore

try:
    from core.lib.kernel_handlers import KernelHandlersMixin
except Exception as e:
    print(f"\033[93mKernelHandlersMixin import failed: {e}\033[0m")
    KernelHandlersMixin = _make_fallback("KernelHandlers")  # type: ignore

try:
    from core.lib.kernel_lifecycle import KernelLifecycleMixin
except Exception as e:
    print(f"\033[93mKernelLifecycleMixin import failed: {e}\033[0m")
    KernelLifecycleMixin = _make_fallback("KernelLifecycle")  # type: ignore

try:
    from core.lib.kernel_pipeline import KernelPipelineMixin
except Exception as e:
    print(f"\033[93mKernelPipelineMixin import failed: {e}\033[0m")
    KernelPipelineMixin = _make_fallback("KernelPipeline")  # type: ignore


class Kernel(
    KernelCoreMixin,
    KernelHandlersMixin,
    KernelPipelineMixin,
    KernelLifecycleMixin,
):
    """MCUB kernel - orchestrates clients, modules, commands and scheduler.

    This is a thin wrapper class that combines four mixins:
    - KernelCoreMixin: initialization, config, registries, utilities
    - KernelHandlersMixin: handler registration, middleware, modules
    - KernelPipelineMixin: pipeline execution, regex validation, script engine
    - KernelLifecycleMixin: run, shutdown, restart, command processing
    """

    pass
