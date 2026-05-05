# SPDX-License-Identifier: MIT

from core.lib.loader.hikka_compat.fake_package import _detect_module_type


def test_detect_hikka_type_from_loader_patterns():
    code = """
from .. import loader

@loader.tds
class Demo(loader.Module):
    pass
"""
    assert _detect_module_type(code) == "hikka"


def test_detect_native_type_from_register_kernel():
    code = """
from core.lib.loader import something

def register(kernel):
    return kernel
"""
    assert _detect_module_type(code) == "native"


def test_detect_native_type_from_module_base_loader_alias():
    code = """
import core.lib.loader.module_base as loader

class Fastfetch(loader.ModuleBase):
    @loader.command("fastfetch", doc_en="Run fastfetch")
    async def fastfetchcmd(self, event):
        pass
"""
    assert _detect_module_type(code) == "native"


def test_detect_geek_type_from_inline_bot_usage():
    code = """
class X:
    async def run(self):
        return self.inline._bot
"""
    assert _detect_module_type(code) == "geek"


def test_detect_unknown_for_plain_module():
    code = "x = 1\n"
    assert _detect_module_type(code) == "unknown"
