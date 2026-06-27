# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

"""
Tests for MCUB Debugger rules and core functionality.
"""

import ast
import tempfile
from pathlib import Path

import pytest

from debugger.core import ModuleDebugger, SourceAnalyzer
from debugger.rules import (
    get_default_rules,
)
from debugger.types import DebugResult, Warning


class TestEventEditWithButtonsRule:
    """Tests for MCUB001 - event.edit() with deprecated buttons format."""

    def test_detects_json_buttons_in_edit(self):
        """Should detect JSON/dict buttons in event.edit() - deprecated format."""
        code = """
async def handler(event):
    await event.edit("text", buttons={"key": "value"})
"""
        rules = get_default_rules()
        analyzer = SourceAnalyzer(code, "test.py", rules)
        tree = ast.parse(code)
        analyzer.warnings = []
        ast.NodeVisitor.generic_visit(analyzer, tree)

        assert len(analyzer.warnings) > 0
        assert analyzer.warnings[0].rule_id == "MCUB001"

    def test_no_false_positive_with_button_inline(self):
        """Should not flag Button.inline() - correct format."""
        code = """
async def handler(event):
    await event.edit("text", buttons=Button.inline("Click", b"data"))
"""
        rules = get_default_rules()
        analyzer = SourceAnalyzer(code, "test.py", rules)
        tree = ast.parse(code)
        analyzer.warnings = []
        ast.NodeVisitor.generic_visit(analyzer, tree)

        mcub001 = [w for w in analyzer.warnings if w.rule_id == "MCUB001"]
        assert len(mcub001) == 0

    def test_no_false_positive_without_buttons(self):
        """Should not flag event.edit() without buttons."""
        code = """
async def handler(event):
    await event.edit("text")
"""
        rules = get_default_rules()
        analyzer = SourceAnalyzer(code, "test.py", rules)
        tree = ast.parse(code)
        analyzer.warnings = []
        ast.NodeVisitor.generic_visit(analyzer, tree)

        mcub001 = [w for w in analyzer.warnings if w.rule_id == "MCUB001"]
        assert len(mcub001) == 0

    def test_no_false_positive_with_buttons_none(self):
        """Should not flag buttons=None."""
        code = """
async def handler(event):
    await event.edit("text", buttons=None)
"""
        rules = get_default_rules()
        analyzer = SourceAnalyzer(code, "test.py", rules)
        tree = ast.parse(code)
        analyzer.warnings = []
        ast.NodeVisitor.generic_visit(analyzer, tree)

        mcub001 = [w for w in analyzer.warnings if w.rule_id == "MCUB001"]
        assert len(mcub001) == 0

        mcub001 = [w for w in analyzer.warnings if w.rule_id == "MCUB001"]
        assert len(mcub001) == 0


class TestCallbackWithoutPatternRule:
    """Tests for MCUB003 - callback without pattern."""

    def test_detects_missing_pattern(self):
        """Should detect callback event without pattern."""
        code = """
@kernel.register.event("callbackquery")
async def handler(event):
    await event.answer()
"""
        rules = get_default_rules()
        analyzer = SourceAnalyzer(code, "test.py", rules)
        tree = ast.parse(code)
        analyzer.warnings = []
        ast.NodeVisitor.generic_visit(analyzer, tree)

        assert len(analyzer.warnings) > 0

    def test_no_false_positive_with_pattern(self):
        """Should not flag callback with pattern."""
        code = """
@kernel.register.event("callbackquery", pattern=r"test")
async def handler(event):
    await event.answer()
"""
        rules = get_default_rules()
        analyzer = SourceAnalyzer(code, "test.py", rules)
        tree = ast.parse(code)
        analyzer.warnings = []
        ast.NodeVisitor.generic_visit(analyzer, tree)

        mcub003 = [w for w in analyzer.warnings if w.rule_id == "MCUB003"]
        assert len(mcub003) == 0


class TestEventAnswerShowAlertRule:
    """Tests for MCUB004 - show_alert vs alert."""

    def test_detects_show_alert(self):
        """Should detect show_alert argument."""
        code = """
async def handler(event):
    await event.answer("text", show_alert=True)
"""
        rules = get_default_rules()
        analyzer = SourceAnalyzer(code, "test.py", rules)
        tree = ast.parse(code)
        analyzer.warnings = []
        ast.NodeVisitor.generic_visit(analyzer, tree)

        mcub004 = [w for w in analyzer.warnings if w.rule_id == "MCUB004"]
        assert len(mcub004) > 0

    def test_no_false_positive_with_alert(self):
        """Should not flag alert argument."""
        code = """
async def handler(event):
    await event.answer("text", alert=True)
"""
        rules = get_default_rules()
        analyzer = SourceAnalyzer(code, "test.py", rules)
        tree = ast.parse(code)
        analyzer.warnings = []
        ast.NodeVisitor.generic_visit(analyzer, tree)

        mcub004 = [w for w in analyzer.warnings if w.rule_id == "MCUB004"]
        assert len(mcub004) == 0


class TestRegisterTypoRule:
    """Tests for MCUB009 - register typos."""

    def test_detects_regiser_typo(self):
        """Should detect 'regiser' typo."""
        code = """
@kernel.regiser.event("message")
async def handler(event):
    pass
"""
        rules = get_default_rules()
        analyzer = SourceAnalyzer(code, "test.py", rules)
        tree = ast.parse(code)
        analyzer.warnings = []
        ast.NodeVisitor.generic_visit(analyzer, tree)

        mcub009 = [w for w in analyzer.warnings if w.rule_id == "MCUB009"]
        assert len(mcub009) > 0
        assert "regiser" in mcub009[0].message


class TestMissingModuleEntrypointRule:
    """Tests for MCUB031 - missing MCUB module entrypoint."""

    def _warnings_for(self, code: str):
        rules = get_default_rules()
        analyzer = SourceAnalyzer(code, "test.py", rules)
        tree = ast.parse(code)
        analyzer.warnings = []
        analyzer.visit(tree)
        return [w for w in analyzer.warnings if w.rule_id == "MCUB031"]

    def test_detects_missing_register_or_module_base_class(self):
        """Should require either register(kernel/client) or ModuleBase class."""
        code = """
from telethon import events

async def handler(event):
    await event.reply("hello")
"""

        mcub031 = self._warnings_for(code)

        assert len(mcub031) == 1
        assert mcub031[0].severity == "error"
        assert "def register(kernel)" in mcub031[0].message
        assert "ModuleBase" in mcub031[0].message

    def test_allows_register_kernel(self):
        """Should allow function-style modules with register(kernel)."""
        code = """
def register(kernel):
    pass
"""

        assert self._warnings_for(code) == []

    def test_allows_register_client(self):
        """Should allow function-style modules with register(client)."""
        code = """
def register(client):
    pass
"""

        assert self._warnings_for(code) == []

    def test_rejects_register_with_wrong_argument(self):
        """Should reject register() when first argument is not kernel/client."""
        code = """
def register(bot):
    pass
"""

        assert len(self._warnings_for(code)) == 1

    def test_allows_module_base_class(self):
        """Should allow class-style modules inheriting ModuleBase."""
        code = """
from core.lib.loader.module_base import ModuleBase

class MyModule(ModuleBase):
    name = "MyModule"
"""

        assert self._warnings_for(code) == []

    def test_allows_qualified_module_base_class(self):
        """Should allow class-style modules inheriting loader.ModuleBase."""
        code = """
from core.lib import loader

class MyModule(loader.ModuleBase):
    name = "MyModule"
"""

        assert self._warnings_for(code) == []

    def test_allows_aliased_module_base_class(self):
        """Should allow class-style modules inheriting aliased ModuleBase."""
        code = """
from core.lib.loader.module_base import ModuleBase as BaseModule

class MyModule(BaseModule):
    name = "MyModule"
"""

        assert self._warnings_for(code) == []


class TestParentRelativeImportRule:
    """Tests for MCUB032 - FTG-style parent-relative imports."""

    def _warnings_for(self, code: str):
        rules = get_default_rules()
        analyzer = SourceAnalyzer(code, "test.py", rules)
        tree = ast.parse(code)
        analyzer.warnings = []
        analyzer.visit(tree)
        return [w for w in analyzer.warnings if w.rule_id == "MCUB032"]

    def test_detects_parent_relative_wildcard_import(self):
        """Should reject 'from .. import *' FTG-style imports."""
        code = """
from .. import *

def register(kernel):
    pass
"""

        mcub032 = self._warnings_for(code)

        assert len(mcub032) == 1
        assert mcub032[0].severity == "error"
        assert "FTG" in mcub032[0].message

    def test_detects_parent_relative_named_import(self):
        """Should reject 'from .. import loader, utils' FTG-style imports."""
        code = """
from .. import loader, utils

def register(kernel):
    pass
"""

        assert len(self._warnings_for(code)) == 1

    def test_detects_parent_relative_module_import(self):
        """Should reject imports from parent-relative submodules."""
        code = """
from ..utils import answer

def register(kernel):
    pass
"""

        assert len(self._warnings_for(code)) == 1

    def test_allows_absolute_mcub_import(self):
        """Should allow absolute MCUB imports."""
        code = """
from core.lib.loader.module_base import ModuleBase

def register(kernel):
    pass
"""

        assert self._warnings_for(code) == []

    def test_allows_single_dot_relative_import(self):
        """Should only reject parent-relative '..' imports."""
        code = """
from .local import helper

def register(kernel):
    pass
"""

        assert self._warnings_for(code) == []


class TestModuleStructureRules:
    """Tests for module-level MCUB module structure rules."""

    def _warnings_for(self, code: str, rule_id: str):
        rules = get_default_rules()
        analyzer = SourceAnalyzer(code, "test.py", rules)
        tree = ast.parse(code)
        analyzer.warnings = []
        analyzer.visit(tree)
        return [w for w in analyzer.warnings if w.rule_id == rule_id]

    def test_detects_ftg_only_imports(self):
        """Should reject imports from Hikka/Heroku-only APIs."""
        code = """
# name: Demo
# version: 1.0.0
# description: Demo module
# author: @demo
from hikka import loader

def register(kernel):
    pass
"""

        mcub033 = self._warnings_for(code, "MCUB033")

        assert len(mcub033) == 1
        assert mcub033[0].severity == "error"
        assert "Hikka" in mcub033[0].message

    def test_detects_function_style_missing_name_header(self):
        """Should reject function-style modules without required # name."""
        code = """
# version: 1.0.0
# description: Demo module
# author: @demo
def register(kernel):
    pass
"""

        mcub034 = self._warnings_for(code, "MCUB034")

        assert len(mcub034) == 1
        assert mcub034[0].severity == "error"

    def test_detects_mixed_function_and_class_styles(self):
        """Should reject modules that mix register() and ModuleBase class."""
        code = """
from core.lib.loader.module_base import ModuleBase

class Demo(ModuleBase):
    name = "Demo"
    version = "1.0.0"
    description = "Demo module"
    author = "@demo"

def register(kernel):
    pass
"""

        mcub035 = self._warnings_for(code, "MCUB035")

        assert len(mcub035) == 1
        assert mcub035[0].severity == "error"

    def test_detects_function_style_missing_metadata_headers(self):
        """Should warn about missing function-style metadata headers."""
        code = """
# name: Demo
def register(kernel):
    pass
"""

        assert len(self._warnings_for(code, "MCUB036")) == 1
        assert len(self._warnings_for(code, "MCUB037")) == 1
        assert len(self._warnings_for(code, "MCUB038")) == 1

    def test_detects_class_style_missing_metadata_attributes(self):
        """Should warn about missing class-style metadata attributes."""
        code = """
from core.lib.loader.module_base import ModuleBase

class Demo(ModuleBase):
    name = "Demo"
    author = "@demo"
"""

        assert len(self._warnings_for(code, "MCUB036")) == 1
        assert len(self._warnings_for(code, "MCUB037")) == 1

    def test_allows_present_metadata_for_both_styles(self):
        """Should not warn when function/class metadata is present."""
        function_code = """
# name: Demo
# version: 1.0.0
# description: Demo module
# author: @demo
def register(client):
    pass
"""
        class_code = """
from core.lib.loader.module_base import ModuleBase

class Demo(ModuleBase):
    name = "Demo"
    version = "1.0.0"
    description = "Demo module"
    author = "@demo"
"""

        for rule_id in ("MCUB036", "MCUB037", "MCUB038"):
            assert self._warnings_for(function_code, rule_id) == []
        for rule_id in ("MCUB036", "MCUB037"):
            assert self._warnings_for(class_code, rule_id) == []

    def test_detects_unused_module_base_import(self):
        """Should report unused ModuleBase import as info."""
        code = """
# name: Demo
# version: 1.0.0
# description: Demo module
# author: @demo
from core.lib.loader.module_base import ModuleBase

def register(kernel):
    pass
"""

        mcub039 = self._warnings_for(code, "MCUB039")

        assert len(mcub039) == 1
        assert mcub039[0].severity == "info"

    def test_detects_mixed_comment_and_class_metadata(self):
        """Should warn when class-style module duplicates metadata in headers."""
        code = """
# name: HeaderDemo
# version: 1.0.0
# description: Header description
# author: @header
from core.lib.loader.module_base import ModuleBase

class Demo(ModuleBase):
    name = "Demo"
    version = "1.0.1"
    description = "Class description"
    author = "@class"
"""

        mcub040 = self._warnings_for(code, "MCUB040")

        assert len(mcub040) == 4
        assert all(w.severity == "warning" for w in mcub040)
        assert all("Class-style module mixes" in w.message for w in mcub040)

    def test_allows_function_style_comment_metadata(self):
        """Should allow comment metadata for function-style modules."""
        code = """
# name: Demo
# version: 1.0.0
# description: Demo module
# author: @demo
def register(kernel):
    pass
"""

        assert self._warnings_for(code, "MCUB040") == []

    def test_allows_class_style_single_metadata_source(self):
        """Should allow class-style modules that only use class attributes."""
        code = """
from core.lib.loader.module_base import ModuleBase

class Demo(ModuleBase):
    name = "Demo"
    version = "1.0.0"
    description = "Demo module"
    author = "@demo"
"""

        assert self._warnings_for(code, "MCUB040") == []

    def test_detects_function_author_without_username(self):
        """Should warn when # author metadata has no @username."""
        code = """
# name: Demo
# version: 1.0.0
# description: Demo module
# author: OpenAgent
def register(kernel):
    pass
"""

        mcub041 = self._warnings_for(code, "MCUB041")

        assert len(mcub041) == 1
        assert mcub041[0].severity == "warning"
        assert "@username" in mcub041[0].message

    def test_detects_class_author_without_username(self):
        """Should warn when class author attribute has no @username."""
        code = """
from core.lib.loader.module_base import ModuleBase

class Demo(ModuleBase):
    name = "Demo"
    version = "1.0.0"
    description = "Demo module"
    author = "OpenAgent"
"""

        mcub041 = self._warnings_for(code, "MCUB041")

        assert len(mcub041) == 1
        assert mcub041[0].severity == "warning"

    def test_allows_author_with_username(self):
        """Should allow author metadata that includes an @username."""
        function_code = """
# name: Demo
# version: 1.0.0
# description: Demo module
# author: @OpenAgent / port by OpenAgent
def register(kernel):
    pass
"""
        class_code = """
from core.lib.loader.module_base import ModuleBase

class Demo(ModuleBase):
    name = "Demo"
    version = "1.0.0"
    description = "Demo module"
    author = "@OpenAgent / port by OpenAgent"
"""

        assert self._warnings_for(function_code, "MCUB041") == []
        assert self._warnings_for(class_code, "MCUB041") == []


class TestBareOrUnsafeExceptRule:
    """Tests for MCUB027 - broad and bare except handling."""

    def test_detects_bare_except(self):
        """Should detect bare except even in fallback helpers."""
        code = """
def detect_value():
    try:
        return risky_probe()
    except:
        return "fallback"
"""
        rules = get_default_rules()
        analyzer = SourceAnalyzer(code, "test.py", rules)
        tree = ast.parse(code)
        analyzer.warnings = []
        ast.NodeVisitor.generic_visit(analyzer, tree)

        mcub027 = [w for w in analyzer.warnings if w.rule_id == "MCUB027"]
        assert len(mcub027) > 0
        assert "Bare 'except:'" in mcub027[0].message

    def test_allows_helper_fallback_return_default(self):
        """Should not flag helper probes that fall back to a safe default."""
        code = """
def detect_branch():
    try:
        return read_branch()
    except Exception:
        pass
    return "main"

async def check_update():
    try:
        return await has_updates()
    except Exception:
        return False
"""
        rules = get_default_rules()
        analyzer = SourceAnalyzer(code, "test.py", rules)
        tree = ast.parse(code)
        analyzer.warnings = []
        ast.NodeVisitor.generic_visit(analyzer, tree)

        mcub027 = [w for w in analyzer.warnings if w.rule_id == "MCUB027"]
        assert len(mcub027) == 0

    def test_allows_specific_exception_safe_fallback(self):
        """Should not flag specific exceptions that return safe fallback values."""
        code = """
async def check_update():
    try:
        return await fetch_update_state()
    except TimeoutError:
        return False
"""
        rules = get_default_rules()
        analyzer = SourceAnalyzer(code, "test.py", rules)
        tree = ast.parse(code)
        analyzer.warnings = []
        ast.NodeVisitor.generic_visit(analyzer, tree)

        mcub027 = [w for w in analyzer.warnings if w.rule_id == "MCUB027"]
        assert len(mcub027) == 0

    def test_allows_nested_helper_probe_fallback(self):
        """Should not flag nested helper probes that keep initialized defaults."""
        code = """
def get_system_info():
    cpu_usage = "N/A"
    ram_usage = "N/A"
    try:
        try:
            cpu_usage = read_cpu()
            ram_usage = read_ram()
        except Exception:
            pass
    except Exception:
        return "N/A", "N/A"
    return cpu_usage, ram_usage
"""
        rules = get_default_rules()
        analyzer = SourceAnalyzer(code, "test.py", rules)
        tree = ast.parse(code)
        analyzer.warnings = []
        ast.NodeVisitor.generic_visit(analyzer, tree)

        mcub027 = [w for w in analyzer.warnings if w.rule_id == "MCUB027"]
        assert len(mcub027) == 0

    def test_allows_best_effort_error_feedback_fallback(self):
        """Should not flag pass after a failed best-effort user notification."""
        code = """
@command("demo")
async def handler(event):
    try:
        await risky_action()
    except Exception:
        self.log.error("failed")
        try:
            await event.edit("error")
        except Exception:
            pass
"""
        rules = get_default_rules()
        analyzer = SourceAnalyzer(code, "test.py", rules)
        tree = ast.parse(code)
        analyzer.warnings = []
        ast.NodeVisitor.generic_visit(analyzer, tree)

        mcub027 = [w for w in analyzer.warnings if w.rule_id == "MCUB027"]
        assert len(mcub027) == 0

    def test_allows_helper_localized_error_fallback(self):
        """Should not flag helper builders that return localized fallback text."""
        code = """
async def build_custom_text():
    try:
        return await resolve_placeholders()
    except Exception as e:
        return self.strings("custom_text_error", error=str(e))
"""
        rules = get_default_rules()
        analyzer = SourceAnalyzer(code, "test.py", rules)
        tree = ast.parse(code)
        analyzer.warnings = []
        ast.NodeVisitor.generic_visit(analyzer, tree)

        mcub027 = [w for w in analyzer.warnings if w.rule_id == "MCUB027"]
        assert len(mcub027) == 0

    def test_detects_silent_broad_except_in_command_handler(self):
        """Should still flag broad exceptions swallowed inside commands."""
        code = """
@command("demo")
async def handler(event):
    try:
        await risky_action()
    except Exception:
        return False
"""
        rules = get_default_rules()
        analyzer = SourceAnalyzer(code, "test.py", rules)
        tree = ast.parse(code)
        analyzer.warnings = []
        ast.NodeVisitor.generic_visit(analyzer, tree)

        mcub027 = [w for w in analyzer.warnings if w.rule_id == "MCUB027"]
        assert len(mcub027) > 0


class TestModuleDebugger:
    """Tests for ModuleDebugger class."""

    def test_debug_valid_file(self):
        """Should handle a valid MCUB module file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                """
# name: TestModule
# version: 1.0.0
# description: Test module
# author: @test
def register(kernel):
    pass
"""
            )
            f.flush()

            debugger = ModuleDebugger()
            result = debugger.debug_file(f.name)

            assert result.file_path == f.name
            assert result.is_clean

    def test_debug_file_with_issues(self):
        """Should detect issues in file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                """
@kernel.register.event("callbackquery")
async def handler(event):
    await event.answer("test", show_alert=True)
"""
            )
            f.flush()

            debugger = ModuleDebugger()
            result = debugger.debug_file(f.name)

            assert result.has_warnings or result.has_errors

    def test_debug_directory(self):
        """Should debug all Python files in directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "module1.py").write_text(
                """
async def handler():
    pass
"""
            )
            Path(tmpdir, "module2.py").write_text(
                """
@kernel.regiser.event("message")
async def handler():
    pass
"""
            )

            debugger = ModuleDebugger()
            results = debugger.debug_directory(tmpdir)

            assert len(results) == 2

            issue_files = [r for r in results if r.has_warnings]
            assert len(issue_files) >= 1


class TestWarning:
    """Tests for Warning dataclass."""

    def test_format_warning(self):
        """Should format warning correctly."""
        warning = Warning(
            rule_id="MCUB001",
            severity="warning",
            message="Test message",
            file_path="test.py",
            line=10,
            column=5,
            code_snippet="    await event.edit(text, buttons=btn)",
            fix_suggestion="Use Button.inline()",
        )

        formatted = warning.format()

        assert "WARNING" in formatted
        assert "MCUB001" in formatted
        assert "Test message" in formatted
        assert "Fix:" in formatted

    def test_format_error(self):
        """Should format error severity correctly."""
        warning = Warning(
            rule_id="MCUB031",
            severity="error",
            message="Missing module entrypoint",
            file_path="test.py",
            line=1,
            column=1,
        )

        formatted = warning.format()

        assert "ERROR" in formatted
        assert "MCUB031" in formatted
        assert "Missing module entrypoint" in formatted

    def test_format_info(self):
        """Should format info severity correctly."""
        warning = Warning(
            rule_id="MCUB039",
            severity="info",
            message="Unused ModuleBase import",
            file_path="test.py",
            line=1,
            column=1,
        )

        formatted = warning.format()

        assert "INFO" in formatted
        assert "MCUB039" in formatted
        assert "Unused ModuleBase import" in formatted


class TestDebugResult:
    """Tests for DebugResult dataclass."""

    def test_is_clean_with_no_issues(self):
        """Should return True when no issues."""
        result = DebugResult(file_path="test.py", module_name="test")

        assert result.is_clean

    def test_has_warnings(self):
        """Should detect warnings."""
        result = DebugResult(
            file_path="test.py",
            module_name="test",
            warnings=[
                Warning(
                    rule_id="MCUB001",
                    severity="warning",
                    message="test",
                    file_path="test.py",
                    line=1,
                    column=1,
                )
            ],
        )

        assert result.has_warnings
        assert not result.is_clean


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
