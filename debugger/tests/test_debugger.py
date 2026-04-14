# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

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


class TestModuleDebugger:
    """Tests for ModuleDebugger class."""

    def test_debug_valid_file(self):
        """Should handle valid Python file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                """
async def main():
    print("Hello")
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
