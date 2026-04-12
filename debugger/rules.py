"""
MCUB Debugger Rules - Detection rules for common MCUB errors.
"""

import ast
import re
from abc import abstractmethod
from dataclasses import dataclass
from typing import Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from debugger.core import SourceAnalyzer

from debugger.types import Warning


class WarningRule:
    """Base class for warning rules."""

    rule_id: str = ""
    severity: str = "warning"
    message: str = ""

    def should_check(self, analyzer: "SourceAnalyzer") -> bool:
        """Determine if this rule should run for current context."""
        return True

    @abstractmethod
    def check(
        self, analyzer: "SourceAnalyzer", node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[Warning]:
        """Check for violations and return warnings."""
        pass


class RuleRegistry:
    """Registry for all warning rules."""

    def __init__(self):
        self._rules: list[WarningRule] = []

    def register(self, rule: WarningRule) -> None:
        self._rules.append(rule)

    def get_rules(self) -> list[WarningRule]:
        return self._rules.copy()

    def get_by_severity(self, severity: str) -> list[WarningRule]:
        return [r for r in self._rules if r.severity == severity]


class EventEditWithButtonsRule(WarningRule):
    """Check for event.edit() with buttons argument - warns if using deprecated JSON format."""

    rule_id = "MCUB001"
    severity = "warning"
    message = "event.edit() with buttons argument uses deprecated format. Use Button.inline() in the first call or build message separately."

    def check(
        self, analyzer: "SourceAnalyzer", node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[Warning]:
        warnings = []

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if self._is_event_edit_call(child):
                    for keyword in child.keywords:
                        if keyword.arg == "buttons":
                            if self._is_invalid_buttons(keyword.value, analyzer):
                                line = child.lineno
                                code = analyzer.get_line(line)

                                warnings.append(
                                    Warning(
                                        rule_id=self.rule_id,
                                        severity=self.severity,
                                        message=self.message,
                                        file_path=analyzer.file_path,
                                        line=line,
                                        column=child.col_offset + 1,
                                        end_column=(
                                            child.end_col_offset
                                            if hasattr(child, "end_col_offset")
                                            and child.end_col_offset
                                            else len(code)
                                        ),
                                        code_snippet=analyzer.get_code_snippet(line),
                                        fix_suggestion="Use: await message.edit(text, buttons=...) with Button.inline() OR await event.reply(..., buttons=...)",
                                    )
                                )
                            break

        return warnings

    def _is_event_edit_call(self, node: ast.Call) -> bool:
        if isinstance(node.func, ast.Attribute):
            if node.func.attr == "edit":
                if isinstance(node.func.value, ast.Name):
                    if node.func.value.id == "event":
                        return True
        return False

    def _is_invalid_buttons(self, node: ast.expr, analyzer: "SourceAnalyzer") -> bool:
        if node is None:
            return False
        if isinstance(node, ast.Constant):
            if node.value is None:
                return False
            return True
        if isinstance(node, ast.Name):
            var_type = analyzer.get_symbol_type(node.id)
            if var_type in ("None", None):
                return False
            if var_type in ("Button", "ButtonList"):
                return False
            if var_type in ("Call", "unknown", "List"):
                return False
            return True
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in ("inline", "url", "switch_inline", "text"):
                    return False
            if isinstance(node.func, ast.Name):
                if node.func.id == "Button":
                    return False
            return False
        if isinstance(node, ast.List):
            for elem in node.elts:
                if self._is_button_call(elem):
                    return False
            return True
        if isinstance(node, ast.Dict):
            return True
        return False

    def _is_button_call(self, node: ast.expr) -> bool:
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in ("inline", "url", "switch_inline", "text"):
                    return True
            elif isinstance(node.func, ast.Name):
                if "Button" in node.func.id:
                    return True
        elif isinstance(node, ast.List):
            for elem in node.elts:
                if self._is_button_call(elem):
                    return True
        elif isinstance(node, ast.Name):
            return "Button" in node.id
        return False


class EventEditWithReplyMarkupRule(WarningRule):
    """Check for event.edit() with reply_markup argument - warns if using deprecated format."""

    rule_id = "MCUB002"
    severity = "warning"
    message = "event.edit() with reply_markup argument uses deprecated format. Use buttons= parameter with Button.inline()"

    def check(
        self, analyzer: "SourceAnalyzer", node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[Warning]:
        warnings = []

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Attribute):
                    if child.func.attr == "edit":
                        if isinstance(child.func.value, ast.Name):
                            if child.func.value.id == "event":
                                for keyword in child.keywords:
                                    if keyword.arg == "reply_markup":
                                        if self._is_invalid_reply_markup(
                                            keyword.value, analyzer
                                        ):
                                            line = child.lineno
                                            code = analyzer.get_line(line)

                                            warnings.append(
                                                Warning(
                                                    rule_id=self.rule_id,
                                                    severity=self.severity,
                                                    message=self.message,
                                                    file_path=analyzer.file_path,
                                                    line=line,
                                                    column=child.col_offset + 1,
                                                    end_column=(
                                                        child.end_col_offset
                                                        if hasattr(
                                                            child, "end_col_offset"
                                                        )
                                                        and child.end_col_offset
                                                        else len(code)
                                                    ),
                                                    code_snippet=analyzer.get_code_snippet(
                                                        line
                                                    ),
                                                    fix_suggestion="Replace reply_markup= with buttons=Button.inline(...)",
                                                )
                                            )
                                        break

        return warnings

    def _is_invalid_reply_markup(
        self, node: ast.expr, analyzer: "SourceAnalyzer"
    ) -> bool:
        if node is None:
            return False
        if isinstance(node, ast.Constant):
            if node.value is None:
                return False
            return True
        if isinstance(node, ast.Name):
            var_type = analyzer.get_symbol_type(node.id)
            if var_type in ("None", None):
                return False
            if var_type in ("Button", "ButtonList"):
                return False
            if var_type in ("Call", "unknown", "List"):
                return False
            return True
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in ("inline", "url", "switch_inline", "text"):
                    return False
            if isinstance(node.func, ast.Name):
                if node.func.id == "Button":
                    return False
            return False
        if isinstance(node, ast.List):
            for elem in node.elts:
                if self._is_button_call(elem):
                    return False
            return True
        if isinstance(node, ast.Dict):
            return True
        return False

    def _is_button_call(self, node: ast.expr) -> bool:
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in ("inline", "url", "switch_inline", "text"):
                    return True
            elif isinstance(node.func, ast.Name):
                if "Button" in node.func.id:
                    return True
        elif isinstance(node, ast.List):
            for elem in node.elts:
                if self._is_button_call(elem):
                    return True
        elif isinstance(node, ast.Name):
            return "Button" in node.id
        return False


class CallbackWithoutPatternRule(WarningRule):
    """Check for callback/inline events without pattern."""

    rule_id = "MCUB003"
    severity = "error"
    message = "kernel.register.event('callbackquery'/'inlinequery') must have pattern or data filter."

    def should_check(self, analyzer: "SourceAnalyzer") -> bool:
        return any(
            "register.event" in dec["name"] for dec in analyzer.current_decorators
        )

    def check(
        self, analyzer: "SourceAnalyzer", node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[Warning]:
        warnings = []
        for dec in analyzer.current_decorators:
            if "register.event" in dec["name"]:
                has_pattern = "pattern" in dec["kwargs"] or "data" in dec["kwargs"]
                if not has_pattern:
                    warnings.append(
                        Warning(
                            rule_id=self.rule_id,
                            severity=self.severity,
                            message=self.message,
                            file_path=analyzer.file_path,
                            line=node.lineno,
                            column=node.col_offset + 1,
                            end_column=(
                                node.end_col_offset
                                if hasattr(node, "end_col_offset")
                                and node.end_col_offset
                                else len(analyzer.get_line(node.lineno))
                            ),
                            code_snippet=analyzer.get_code_snippet(node.lineno),
                            fix_suggestion="Add pattern=r'...' or data=... to @kernel.register.event() decorator",
                        )
                    )
        return warnings


class EventAnswerShowAlertRule(WarningRule):
    """Check for event.answer() with show_alert instead of alert."""

    rule_id = "MCUB004"
    severity = "warning"
    message = (
        "event.answer() does not have show_alert argument. Use alert=True instead."
    )

    def check(
        self, analyzer: "SourceAnalyzer", node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[Warning]:
        warnings = []

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if self._is_event_answer_call(child):
                    for keyword in child.keywords:
                        if keyword.arg == "show_alert":
                            line = child.lineno
                            code = analyzer.get_line(line)

                            warnings.append(
                                Warning(
                                    rule_id=self.rule_id,
                                    severity=self.severity,
                                    message=self.message,
                                    file_path=analyzer.file_path,
                                    line=line,
                                    column=child.col_offset + 1,
                                    end_column=(
                                        child.end_col_offset
                                        if hasattr(child, "end_col_offset")
                                        and child.end_col_offset
                                        else len(code)
                                    ),
                                    code_snippet=analyzer.get_code_snippet(line),
                                    fix_suggestion="Replace show_alert=True with alert=True",
                                )
                            )
                            break

        return warnings

    def _is_event_answer_call(self, node: ast.Call) -> bool:
        if isinstance(node.func, ast.Attribute):
            if node.func.attr == "answer":
                if isinstance(node.func.value, ast.Name):
                    if node.func.value.id == "event":
                        return True
        return False


class EventDeleteBotMessageRule(WarningRule):
    """Check for event.delete() on bot client messages."""

    rule_id = "MCUB005"
    severity = "warning"
    message = "event.delete() cannot delete bot client messages. Use client.delete_messages(chat_id, [message_id]) instead."

    def check(
        self, analyzer: "SourceAnalyzer", node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[Warning]:
        warnings = []

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if self._is_event_delete_call(child):
                    is_bot_context = any(
                        "bot_client" in dec["name"]
                        for dec in analyzer.current_decorators
                    )

                    if is_bot_context:
                        line = child.lineno
                        code = analyzer.get_line(line)

                        warnings.append(
                            Warning(
                                rule_id=self.rule_id,
                                severity=self.severity,
                                message=self.message,
                                file_path=analyzer.file_path,
                                line=line,
                                column=child.col_offset + 1,
                                end_column=(
                                    child.end_col_offset
                                    if hasattr(child, "end_col_offset")
                                    and child.end_col_offset
                                    else len(code)
                                ),
                                code_snippet=analyzer.get_code_snippet(line),
                                fix_suggestion="Use: await client.delete_messages(event.chat_id, [event.message_id])",
                            )
                        )

        return warnings

    def _is_event_delete_call(self, node: ast.Call) -> bool:
        if isinstance(node.func, ast.Attribute):
            if node.func.attr == "delete":
                if isinstance(node.func.value, ast.Name):
                    if node.func.value.id == "event":
                        return True
        return False


class BotClientDeleteMessageRule(WarningRule):
    """Check for kernel.bot_client.delete_messages() or delete_message() calls."""

    rule_id = "MCUB030"
    severity = "warning"
    message = "Bot cannot delete its own messages. Use client (user account) instead of bot_client for deleting messages."

    def check(
        self, analyzer: "SourceAnalyzer", node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[Warning]:
        warnings = []

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if self._is_bot_client_delete_call(child):
                    warnings.append(
                        Warning(
                            rule_id=self.rule_id,
                            severity=self.severity,
                            message=self.message,
                            file_path=analyzer.file_path,
                            line=child.lineno,
                            column=child.col_offset + 1,
                            code_snippet=analyzer.get_code_snippet(child.lineno),
                            fix_suggestion="Use: await client.delete_messages(chat_id, [message_id]) instead of bot_client",
                        )
                    )
        return warnings

    def _is_bot_client_delete_call(self, node: ast.Call) -> bool:
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in ("delete_messages", "delete_message", "delete"):
                if isinstance(node.func.value, ast.Attribute):
                    if node.func.value.attr == "bot_client":
                        if isinstance(node.func.value.value, ast.Name):
                            if node.func.value.value.id == "kernel":
                                return True
        return False


class MissingBotClientRule(WarningRule):
    """Check for inline/callback events without bot_client=True."""

    rule_id = "MCUB006"
    severity = "warning"
    message = "inlinequery/callbackquery events must use bot_client=True. Userbots don't receive these events."

    def should_check(self, analyzer: "SourceAnalyzer") -> bool:
        return bool(analyzer.current_decorators)

    def check(
        self, analyzer: "SourceAnalyzer", node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[Warning]:
        warnings = []

        bot_only_events = {"inline", "inlinequery", "callback", "callbackquery"}

        for dec in analyzer.current_decorators:
            if "register.event" in dec["name"] or "register.callback" in dec["name"]:
                for event_type in bot_only_events:
                    if event_type in dec["name"].lower():
                        bot_client = dec["kwargs"].get("bot_client")
                        if bot_client is not True:
                            warnings.append(
                                Warning(
                                    rule_id=self.rule_id,
                                    severity=self.severity,
                                    message=self.message,
                                    file_path=analyzer.file_path,
                                    line=node.lineno,
                                    column=node.col_offset + 1,
                                    end_column=(
                                        node.end_col_offset
                                        if hasattr(node, "end_col_offset")
                                        and node.end_col_offset
                                        else len(analyzer.get_line(node.lineno))
                                    ),
                                    code_snippet=analyzer.get_code_snippet(node.lineno),
                                    fix_suggestion="Add bot_client=True to @kernel.register.event() decorator",
                                )
                            )
                        break

        return warnings


class AsyncWithoutAwaitRule(WarningRule):
    """Check for async functions that don't await anything."""

    rule_id = "MCUB008"
    severity = "warning"
    message = "Async function '{name}' does not use 'await'. Consider making it a regular function."

    def check(
        self, analyzer: "SourceAnalyzer", node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[Warning]:
        warnings = []

        if not analyzer._in_async_function:
            return warnings

        has_await = False
        for child in ast.walk(node):
            if isinstance(child, ast.Await):
                has_await = True
                break

        if not has_await and node.name not in (
            "main",
            "run",
            "start",
            "init",
            "setup",
            "close",
            "cleanup",
        ):
            warnings.append(
                Warning(
                    rule_id=self.rule_id,
                    severity=self.severity,
                    message=self.message.format(name=node.name),
                    file_path=analyzer.file_path,
                    line=node.lineno,
                    column=node.col_offset + 1,
                    end_column=(
                        node.end_col_offset
                        if hasattr(node, "end_col_offset") and node.end_col_offset
                        else len(analyzer.get_line(node.lineno))
                    ),
                    code_snippet=analyzer.get_code_snippet(node.lineno),
                    fix_suggestion=f"Remove 'async' or add 'await' keyword if calling async code",
                )
            )

        return warnings


class RegisterTypoRule(WarningRule):
    """Check for typos in register method names."""

    rule_id = "MCUB009"
    severity = "error"
    message = (
        "Possible typo in register method: '{method}'. Did you mean '{suggestion}'?"
    )

    _typos = {
        "regiser": "register",
        "regsiter": "register",
        "regiset": "register",
        "registr": "register",
        "regoster": "register",
    }

    def check(
        self, analyzer: "SourceAnalyzer", node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[Warning]:
        warnings = []

        for dec in analyzer.current_decorators:
            name = dec["name"]
            for typo, correct in self._typos.items():
                if typo in name:
                    warnings.append(
                        Warning(
                            rule_id=self.rule_id,
                            severity=self.severity,
                            message=self.message.format(
                                method=name, suggestion=name.replace(typo, correct)
                            ),
                            file_path=analyzer.file_path,
                            line=node.lineno,
                            column=node.col_offset + 1,
                            end_column=(
                                node.end_col_offset
                                if hasattr(node, "end_col_offset")
                                and node.end_col_offset
                                else len(analyzer.get_line(node.lineno))
                            ),
                            code_snippet=analyzer.get_code_snippet(node.lineno),
                            fix_suggestion=f"Fix typo: '{typo}' -> '{correct}'",
                        )
                    )

        return warnings


class ButtonInlineFormatRule(WarningRule):
    """Check for incorrect button format in edit calls."""

    rule_id = "MCUB010"
    severity = "warning"
    message = "Use Button.inline() format for inline keyboard buttons. JSON format is deprecated."

    def check(
        self, analyzer: "SourceAnalyzer", node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[Warning]:
        warnings = []

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if self._is_event_edit_call(child):
                    for keyword in child.keywords:
                        if keyword.arg == "buttons":
                            if self._is_invalid_buttons(keyword.value, analyzer):
                                line = child.lineno
                                code = analyzer.get_line(line)

                                warnings.append(
                                    Warning(
                                        rule_id=self.rule_id,
                                        severity=self.severity,
                                        message=self.message,
                                        file_path=analyzer.file_path,
                                        line=line,
                                        column=child.col_offset + 1,
                                        code_snippet=analyzer.get_code_snippet(line),
                                        fix_suggestion="Use Button.inline() or Button.url() for inline keyboards",
                                    )
                                )

        return warnings

    def _is_event_edit_call(self, node: ast.Call) -> bool:
        if isinstance(node.func, ast.Attribute):
            return node.func.attr == "edit"
        return False

    def _is_invalid_buttons(self, node: ast.expr, analyzer: "SourceAnalyzer") -> bool:
        if node is None:
            return False
        if isinstance(node, ast.Constant):
            if node.value is None:
                return False
            return True
        if isinstance(node, ast.Name):
            var_type = analyzer.get_symbol_type(node.id)
            if var_type in ("None", None):
                return False
            if var_type in ("Button", "ButtonList"):
                return False
            if var_type in ("Call", "unknown", "List"):
                return False
            return True
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in ("inline", "url", "switch_inline", "text"):
                    return False
            if isinstance(node.func, ast.Name):
                if node.func.id == "Button":
                    return False
            return False
        if isinstance(node, ast.List):
            for elem in node.elts:
                if self._is_button_call(elem):
                    return False
            return True
        if isinstance(node, ast.Dict):
            return True
        return False

    def _is_button_call(self, node: ast.expr) -> bool:
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in ("inline", "url", "switch_inline", "text"):
                    return True
            elif isinstance(node.func, ast.Name):
                if "Button" in node.func.id:
                    return True
        elif isinstance(node, ast.List):
            for elem in node.elts:
                if self._is_button_call(elem):
                    return True
        elif isinstance(node, ast.Name):
            return "Button" in node.id
        return False


class WrongEventTypeRule(WarningRule):
    """Check for unknown event types in register."""

    rule_id = "MCUB011"
    severity = "error"
    message = "Unknown event type '{event_type}'. Valid: newmessage, messageedited, messagedeleted, userupdate, inlinequery, callbackquery, raw"

    _valid_events = {
        "newmessage",
        "message",
        "messageedited",
        "edited",
        "messagedeleted",
        "deleted",
        "userupdate",
        "user",
        "inlinequery",
        "inline",
        "callbackquery",
        "callback",
        "raw",
        "custom",
    }

    def should_check(self, analyzer: "SourceAnalyzer") -> bool:
        return bool(analyzer.current_decorators)

    def check(
        self, analyzer: "SourceAnalyzer", node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[Warning]:
        warnings = []

        for dec in analyzer.current_decorators:
            if "register.event" in dec["name"]:
                if dec["args"]:
                    event_type = dec["args"][0]
                    if (
                        isinstance(event_type, str)
                        and event_type.lower() not in self._valid_events
                    ):
                        warnings.append(
                            Warning(
                                rule_id=self.rule_id,
                                severity=self.severity,
                                message=self.message.format(event_type=event_type),
                                file_path=analyzer.file_path,
                                line=node.lineno,
                                column=node.col_offset + 1,
                                end_column=(
                                    node.end_col_offset
                                    if hasattr(node, "end_col_offset")
                                    and node.end_col_offset
                                    else len(analyzer.get_line(node.lineno))
                                ),
                                code_snippet=analyzer.get_code_snippet(node.lineno),
                                fix_suggestion=f"Use one of: {', '.join(sorted(self._valid_events))}",
                            )
                        )

        return warnings


class ClientDeleteMessagesRule(WarningRule):
    """Recommend client.delete_messages over event.delete for bot messages."""

    rule_id = "MCUB012"
    severity = "info"
    message = "For bot client messages, use client.delete_messages(chat_id, [message_id]) instead of event.delete()"

    def should_check(self, analyzer: "SourceAnalyzer") -> bool:
        return "bot_client" in str(analyzer.current_decorators)

    def check(
        self, analyzer: "SourceAnalyzer", node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[Warning]:
        warnings = []

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Attribute):
                    if child.func.attr == "delete" and isinstance(
                        child.func.value, ast.Name
                    ):
                        if child.func.value.id == "event":
                            line = child.lineno
                            code = analyzer.get_line(line)

                            warnings.append(
                                Warning(
                                    rule_id=self.rule_id,
                                    severity=self.severity,
                                    message=self.message,
                                    file_path=analyzer.file_path,
                                    line=line,
                                    column=child.col_offset + 1,
                                    code_snippet=analyzer.get_code_snippet(line),
                                    fix_suggestion="Use: await client.delete_messages(event.chat_id, [event.message_id])",
                                )
                            )

        return warnings


class RawEventInHandlerRule(WarningRule):
    """Check for raw event usage in handlers."""

    rule_id = "MCUB013"
    severity = "warning"
    message = "Accessing event.message inside 'deleted' event handler. Deleted messages don't have message attribute."

    def should_check(self, analyzer: "SourceAnalyzer") -> bool:
        return any(
            "register.event" in dec["name"] for dec in analyzer.current_decorators
        )

    def check(
        self, analyzer: "SourceAnalyzer", node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[Warning]:
        warnings = []

        for dec in analyzer.current_decorators:
            if "register.event" in dec["name"]:
                if dec["args"] and dec["args"][0] in ("deleted", "messagedeleted"):
                    for child in ast.walk(node):
                        if isinstance(child, ast.Attribute):
                            if child.attr == "message":
                                if isinstance(child.value, ast.Name):
                                    if child.value.id == "event":
                                        line = child.lineno
                                        code = analyzer.get_line(line)

                                        warnings.append(
                                            Warning(
                                                rule_id=self.rule_id,
                                                severity=self.severity,
                                                message=self.message,
                                                file_path=analyzer.file_path,
                                                line=line,
                                                column=child.col_offset + 1,
                                                code_snippet=analyzer.get_code_snippet(
                                                    line
                                                ),
                                                fix_suggestion="Use event.original_update or check event attributes directly",
                                            )
                                        )

        return warnings


class EventEditInCallbackRule(WarningRule):
    """Check for event.edit in callback handlers."""

    rule_id = "MCUB014"
    severity = "warning"
    message = "Using event.edit() in callback. Note: event.delete() cannot delete callback messages."

    def should_check(self, analyzer: "SourceAnalyzer") -> bool:
        return any(
            "callback" in dec["name"].lower() for dec in analyzer.current_decorators
        )

    def check(
        self, analyzer: "SourceAnalyzer", node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[Warning]:
        warnings = []

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Attribute):
                    if child.func.attr == "edit" and isinstance(
                        child.func.value, ast.Name
                    ):
                        if child.func.value.id == "event":
                            line = child.lineno
                            code = analyzer.get_line(line)

                            warnings.append(
                                Warning(
                                    rule_id=self.rule_id,
                                    severity=self.severity,
                                    message=self.message,
                                    file_path=analyzer.file_path,
                                    line=line,
                                    column=child.col_offset + 1,
                                    code_snippet=analyzer.get_code_snippet(line),
                                    fix_suggestion="Use: await event.edit(...) to edit the callback message",
                                )
                            )

        return warnings


class AsyncFunctionRequiredRule(WarningRule):
    """Check that command/event handlers are async functions."""

    rule_id = "MCUB015"
    severity = "error"
    message = "Handler '{name}' must be an async function (use 'async def')."

    def should_check(self, analyzer: "SourceAnalyzer") -> bool:
        return any(
            any(
                x in dec["name"]
                for x in [
                    "register.command",
                    "register.event",
                    "register.watcher",
                    "register.loop",
                    "register.bot_command",
                ]
            )
            for dec in analyzer.current_decorators
        )

    def check(
        self, analyzer: "SourceAnalyzer", node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[Warning]:
        warnings = []

        if not isinstance(node, ast.AsyncFunctionDef):
            warnings.append(
                Warning(
                    rule_id=self.rule_id,
                    severity=self.severity,
                    message=self.message.format(name=node.name),
                    file_path=analyzer.file_path,
                    line=node.lineno,
                    column=node.col_offset + 1,
                    end_column=(
                        node.end_col_offset
                        if hasattr(node, "end_col_offset") and node.end_col_offset
                        else len(analyzer.get_line(node.lineno))
                    ),
                    code_snippet=analyzer.get_code_snippet(node.lineno),
                    fix_suggestion="Change 'def' to 'async def'",
                )
            )
        return warnings


class IncorrectCallbackDataRule(WarningRule):
    """Check that callback data in Button.inline() is bytes, not string."""

    rule_id = "MCUB016"
    severity = "warning"
    message = "Button callback data should be bytes (b'...'), not string."

    def check(
        self, analyzer: "SourceAnalyzer", node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[Warning]:
        warnings = []

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if self._is_button_inline_call(child):
                    for kw in child.keywords:
                        if kw.arg == "data":
                            if isinstance(kw.value, ast.Constant) and isinstance(
                                kw.value.value, str
                            ):
                                line = child.lineno
                                code = analyzer.get_line(line)
                                warnings.append(
                                    Warning(
                                        rule_id=self.rule_id,
                                        severity=self.severity,
                                        message=self.message,
                                        file_path=analyzer.file_path,
                                        line=line,
                                        column=child.col_offset + 1,
                                        end_column=(
                                            child.end_col_offset
                                            if hasattr(child, "end_col_offset")
                                            and child.end_col_offset
                                            else len(code)
                                        ),
                                        code_snippet=analyzer.get_code_snippet(line),
                                        fix_suggestion=f"Change data='{kw.value.value}' to data=b'{kw.value.value}'",
                                    )
                                )
        return warnings

    def _is_button_inline_call(self, node: ast.Call) -> bool:
        if isinstance(node.func, ast.Attribute):
            if node.func.attr == "inline":
                if (
                    isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "Button"
                ):
                    return True
        return False


class MissingBotClientInEventRule(WarningRule):
    """Check that callback/inline events have bot_client=True."""

    rule_id = "MCUB017"
    severity = "warning"
    message = "Event '{event_type}' requires bot_client=True."

    def should_check(self, analyzer: "SourceAnalyzer") -> bool:
        return bool(analyzer.current_decorators)

    def check(
        self, analyzer: "SourceAnalyzer", node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[Warning]:
        warnings = []
        bot_only_events = {"inlinequery", "callbackquery", "inline", "callback"}

        for dec in analyzer.current_decorators:
            if "register.event" in dec["name"]:
                event_type = None
                if dec["args"]:
                    event_type = dec["args"][0]
                elif "event" in dec["kwargs"]:
                    event_type = dec["kwargs"]["event"]

                if event_type and event_type in bot_only_events:
                    bot_client = dec["kwargs"].get("bot_client")
                    if bot_client is not True:
                        warnings.append(
                            Warning(
                                rule_id=self.rule_id,
                                severity=self.severity,
                                message=self.message.format(event_type=event_type),
                                file_path=analyzer.file_path,
                                line=node.lineno,
                                column=node.col_offset + 1,
                                end_column=(
                                    node.end_col_offset
                                    if hasattr(node, "end_col_offset")
                                    and node.end_col_offset
                                    else len(analyzer.get_line(node.lineno))
                                ),
                                code_snippet=analyzer.get_code_snippet(node.lineno),
                                fix_suggestion="Add bot_client=True to @kernel.register.event() decorator",
                            )
                        )
        return warnings


class MissingPatternInEventRule(WarningRule):
    """Check that event handlers have pattern or data filter."""

    rule_id = "MCUB018"
    severity = "warning"
    message = "Event handler should have a pattern or data filter to avoid catching all events."

    def should_check(self, analyzer: "SourceAnalyzer") -> bool:
        return any(
            "register.event" in dec["name"] for dec in analyzer.current_decorators
        )

    def check(
        self, analyzer: "SourceAnalyzer", node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[Warning]:
        warnings = []

        for dec in analyzer.current_decorators:
            if "register.event" in dec["name"]:
                has_pattern = "pattern" in dec["kwargs"] or "data" in dec["kwargs"]
                if not has_pattern:
                    warnings.append(
                        Warning(
                            rule_id=self.rule_id,
                            severity=self.severity,
                            message=self.message,
                            file_path=analyzer.file_path,
                            line=node.lineno,
                            column=node.col_offset + 1,
                            end_column=(
                                node.end_col_offset
                                if hasattr(node, "end_col_offset")
                                and node.end_col_offset
                                else len(analyzer.get_line(node.lineno))
                            ),
                            code_snippet=analyzer.get_code_snippet(node.lineno),
                            fix_suggestion="Add pattern=r'...' or data=... to @kernel.register.event()",
                        )
                    )
        return warnings


class WatcherTagsRule(WarningRule):
    """Check for valid tags in @kernel.register.watcher decorator."""

    rule_id = "MCUB019"
    severity = "warning"
    message = "Invalid or missing tag in @kernel.register.watcher. Valid tags: out, incoming, only_pm, no_pm, only_groups, no_groups, only_channels, no_channels, only_media, no_media, only_photos, only_videos, only_audios, only_docs, only_stickers, no_photos, no_videos, no_audios, no_docs, no_stickers, only_forwards, no_forwards, only_reply, no_reply, regex, startswith, endswith, contains, from_id, chat_id"

    _valid_tags = {
        "out",
        "incoming",
        "only_pm",
        "no_pm",
        "only_groups",
        "no_groups",
        "only_channels",
        "no_channels",
        "only_media",
        "no_media",
        "only_photos",
        "only_videos",
        "only_audios",
        "only_docs",
        "only_stickers",
        "no_photos",
        "no_videos",
        "no_audios",
        "no_docs",
        "no_stickers",
        "only_forwards",
        "no_forwards",
        "only_reply",
        "no_reply",
        "regex",
        "startswith",
        "endswith",
        "contains",
        "from_id",
        "chat_id",
    }
    _bool_tags = {
        "out",
        "incoming",
        "only_pm",
        "no_pm",
        "only_groups",
        "no_groups",
        "only_channels",
        "no_channels",
        "only_media",
        "no_media",
        "only_photos",
        "only_videos",
        "only_audios",
        "only_docs",
        "only_stickers",
        "no_photos",
        "no_videos",
        "no_audios",
        "no_docs",
        "no_stickers",
        "only_forwards",
        "no_forwards",
        "only_reply",
        "no_reply",
    }
    _str_tags = {"regex", "startswith", "endswith", "contains"}
    _int_tags = {"from_id", "chat_id"}

    def should_check(self, analyzer: "SourceAnalyzer") -> bool:
        return any(
            "register.watcher" in dec["name"] for dec in analyzer.current_decorators
        )

    def check(
        self, analyzer: "SourceAnalyzer", node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[Warning]:
        warnings = []

        for dec in analyzer.current_decorators:
            if "register.watcher" in dec["name"]:
                for kw, value in dec["kwargs"].items():
                    if kw not in self._valid_tags:
                        warnings.append(
                            Warning(
                                rule_id=self.rule_id,
                                severity=self.severity,
                                message=f"Invalid watcher tag '{kw}'. Valid tags: {', '.join(sorted(self._valid_tags))}",
                                file_path=analyzer.file_path,
                                line=node.lineno,
                                column=node.col_offset + 1,
                                code_snippet=analyzer.get_code_snippet(node.lineno),
                                fix_suggestion=f"Remove invalid tag '{kw}' or use valid tag from the list",
                            )
                        )
                    elif kw in self._bool_tags and not isinstance(value, bool):
                        warnings.append(
                            Warning(
                                rule_id=self.rule_id,
                                severity=self.severity,
                                message=f"Tag '{kw}' must be a boolean, got {type(value).__name__}",
                                file_path=analyzer.file_path,
                                line=node.lineno,
                                column=node.col_offset + 1,
                                code_snippet=analyzer.get_code_snippet(node.lineno),
                                fix_suggestion=f"Use {kw}=True or {kw}=False",
                            )
                        )
                    elif (
                        kw in self._str_tags
                        and value is not None
                        and not isinstance(value, str)
                    ):
                        warnings.append(
                            Warning(
                                rule_id=self.rule_id,
                                severity=self.severity,
                                message=f"Tag '{kw}' must be a string, got {type(value).__name__}",
                                file_path=analyzer.file_path,
                                line=node.lineno,
                                column=node.col_offset + 1,
                                code_snippet=analyzer.get_code_snippet(node.lineno),
                                fix_suggestion=f"Use {kw}='value'",
                            )
                        )
                    elif (
                        kw in self._int_tags
                        and value is not None
                        and not isinstance(value, int)
                    ):
                        warnings.append(
                            Warning(
                                rule_id=self.rule_id,
                                severity=self.severity,
                                message=f"Tag '{kw}' must be an integer, got {type(value).__name__}",
                                file_path=analyzer.file_path,
                                line=node.lineno,
                                column=node.col_offset + 1,
                                code_snippet=analyzer.get_code_snippet(node.lineno),
                                fix_suggestion=f"Use {kw}=123456789",
                            )
                        )
        return warnings


class LoopParamsRule(WarningRule):
    """Check for valid parameters in @kernel.register.loop decorator."""

    rule_id = "MCUB020"
    severity = "warning"
    message = "Invalid parameters in @kernel.register.loop. interval must be int > 0, autostart and wait_before must be bool."

    def should_check(self, analyzer: "SourceAnalyzer") -> bool:
        return any(
            "register.loop" in dec["name"] for dec in analyzer.current_decorators
        )

    def check(
        self, analyzer: "SourceAnalyzer", node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[Warning]:
        warnings = []

        for dec in analyzer.current_decorators:
            if "register.loop" in dec["name"]:
                interval = dec["kwargs"].get("interval")
                if interval is not None:
                    if not isinstance(interval, int):
                        warnings.append(
                            Warning(
                                rule_id=self.rule_id,
                                severity=self.severity,
                                message=f"interval must be an integer, got {type(interval).__name__}",
                                file_path=analyzer.file_path,
                                line=node.lineno,
                                column=node.col_offset + 1,
                                code_snippet=analyzer.get_code_snippet(node.lineno),
                                fix_suggestion="Use interval=60 (seconds)",
                            )
                        )
                    elif interval <= 0:
                        warnings.append(
                            Warning(
                                rule_id=self.rule_id,
                                severity=self.severity,
                                message=f"interval must be > 0, got {interval}",
                                file_path=analyzer.file_path,
                                line=node.lineno,
                                column=node.col_offset + 1,
                                code_snippet=analyzer.get_code_snippet(node.lineno),
                                fix_suggestion="Use interval=60 or higher",
                            )
                        )
                for param in ("autostart", "wait_before"):
                    value = dec["kwargs"].get(param)
                    if value is not None and not isinstance(value, bool):
                        warnings.append(
                            Warning(
                                rule_id=self.rule_id,
                                severity=self.severity,
                                message=f"{param} must be a boolean, got {type(value).__name__}",
                                file_path=analyzer.file_path,
                                line=node.lineno,
                                column=node.col_offset + 1,
                                code_snippet=analyzer.get_code_snippet(node.lineno),
                                fix_suggestion=f"Use {param}=True or {param}=False",
                            )
                        )
        return warnings


class LifecycleHandlerRule(WarningRule):
    """Check that lifecycle handlers (on_load, on_install, uninstall) are async and accept kernel."""

    rule_id = "MCUB021"
    severity = "warning"
    message = "Lifecycle handler must be an async function accepting exactly one argument (kernel)."

    _lifecycle_decorators = {
        "register.on_load",
        "register.on_install",
        "register.uninstall",
    }

    def should_check(self, analyzer: "SourceAnalyzer") -> bool:
        return any(
            any(dec in self._lifecycle_decorators for dec in [d["name"]])
            for d in analyzer.current_decorators
        )

    def check(
        self, analyzer: "SourceAnalyzer", node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[Warning]:
        warnings = []

        for dec in analyzer.current_decorators:
            if dec["name"] in self._lifecycle_decorators:
                if not isinstance(node, ast.AsyncFunctionDef):
                    warnings.append(
                        Warning(
                            rule_id=self.rule_id,
                            severity=self.severity,
                            message=f"'{dec['name']}' handler must be async. Use 'async def'.",
                            file_path=analyzer.file_path,
                            line=node.lineno,
                            column=node.col_offset + 1,
                            code_snippet=analyzer.get_code_snippet(node.lineno),
                            fix_suggestion="Change 'def' to 'async def'",
                        )
                    )
                else:
                    args = node.args
                    num_args = len(args.args) - len(args.defaults)
                    if num_args != 1:
                        warnings.append(
                            Warning(
                                rule_id=self.rule_id,
                                severity=self.severity,
                                message=f"'{dec['name']}' handler must accept exactly 1 argument (kernel)",
                                file_path=analyzer.file_path,
                                line=node.lineno,
                                column=node.col_offset + 1,
                                code_snippet=analyzer.get_code_snippet(node.lineno),
                                fix_suggestion="Use: async def handler(kernel):",
                            )
                        )
        return warnings


class MethodDecoratorRule(WarningRule):
    """Check that @kernel.register.method decorated functions accept kernel."""

    rule_id = "MCUB022"
    severity = "info"
    message = "Method decorated with @kernel.register.method should accept 'kernel' as argument."

    def should_check(self, analyzer: "SourceAnalyzer") -> bool:
        return any(
            "register.method" in dec["name"] for dec in analyzer.current_decorators
        )

    def check(
        self, analyzer: "SourceAnalyzer", node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[Warning]:
        warnings = []

        for dec in analyzer.current_decorators:
            if "register.method" in dec["name"]:
                args = node.args
                if args.args:
                    first_arg = args.args[0].arg
                    if first_arg != "kernel":
                        warnings.append(
                            Warning(
                                rule_id=self.rule_id,
                                severity=self.severity,
                                message=f"Method should accept 'kernel' as first argument, got '{first_arg}'",
                                file_path=analyzer.file_path,
                                line=node.lineno,
                                column=node.col_offset + 1,
                                code_snippet=analyzer.get_code_snippet(node.lineno),
                                fix_suggestion=f"Use: async def {node.name}(kernel):",
                            )
                        )
        return warnings


class InlineFormUsageRule(WarningRule):
    """Check for correct usage of kernel.inline_form and kernel._inline.gallery/list."""

    rule_id = "MCUB023"
    severity = "warning"
    message = "Invalid parameter in inline form/gallery/list call. chat_id must be int, fields must be dict/list, buttons must be list, auto_send must be bool."

    _inline_methods = {"inline_form", "gallery", "list"}

    def check(
        self, analyzer: "SourceAnalyzer", node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[Warning]:
        warnings = []

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if self._is_inline_call(child):
                    chat_id = self._get_arg_value(child, "chat_id", 0)
                    if chat_id is not None and not isinstance(chat_id, int):
                        warnings.append(
                            Warning(
                                rule_id=self.rule_id,
                                severity=self.severity,
                                message=f"chat_id must be int, got {type(chat_id).__name__}",
                                file_path=analyzer.file_path,
                                line=child.lineno,
                                column=child.col_offset + 1,
                                code_snippet=analyzer.get_code_snippet(child.lineno),
                                fix_suggestion="Use event.chat_id (int)",
                            )
                        )
                    auto_send = self._get_kwarg_value(child, "auto_send")
                    if auto_send is not None and not isinstance(auto_send, bool):
                        warnings.append(
                            Warning(
                                rule_id=self.rule_id,
                                severity=self.severity,
                                message=f"auto_send must be bool, got {type(auto_send).__name__}",
                                file_path=analyzer.file_path,
                                line=child.lineno,
                                column=child.col_offset + 1,
                                code_snippet=analyzer.get_code_snippet(child.lineno),
                                fix_suggestion="Use auto_send=True or auto_send=False",
                            )
                        )
        return warnings

    def _is_inline_call(self, node: ast.Call) -> bool:
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in self._inline_methods:
                if isinstance(node.func.value, ast.Attribute):
                    if node.func.value.attr == "_inline" and isinstance(
                        node.func.value.value, ast.Name
                    ):
                        if node.func.value.value.id == "kernel":
                            return True
                elif isinstance(node.func.value, ast.Name):
                    if (
                        node.func.value.id == "kernel"
                        and node.func.attr == "inline_form"
                    ):
                        return True
        return False

    def _get_arg_value(self, node: ast.Call, arg_name: str, pos: int) -> Any:
        if pos < len(node.args):
            return self._get_value(node.args[pos])
        for kw in node.keywords:
            if kw.arg == arg_name:
                return self._get_value(kw.value)
        return None

    def _get_kwarg_value(self, node: ast.Call, kw_name: str) -> Any:
        for kw in node.keywords:
            if kw.arg == kw_name:
                return self._get_value(kw.value)
        return None

    def _get_value(self, node: ast.expr) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        return None


class InlineQueryAndClickRule(WarningRule):
    """Check for correct usage of kernel.inline_query_and_click."""

    rule_id = "MCUB024"
    severity = "warning"
    message = "Invalid parameter in inline_query_and_click. chat_id must be int, query must be str, result_index must be int >= 0, timeout must be positive int."

    def check(
        self, analyzer: "SourceAnalyzer", node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[Warning]:
        warnings = []

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if self._is_inline_query_and_click(child):
                    chat_id = self._get_arg_value(child, "chat_id", 0)
                    if chat_id is not None and not isinstance(chat_id, int):
                        warnings.append(
                            Warning(
                                rule_id=self.rule_id,
                                severity=self.severity,
                                message=f"chat_id must be int, got {type(chat_id).__name__}",
                                file_path=analyzer.file_path,
                                line=child.lineno,
                                column=child.col_offset + 1,
                                code_snippet=analyzer.get_code_snippet(child.lineno),
                                fix_suggestion="Use event.chat_id (int)",
                            )
                        )
                    query = self._get_kwarg_value(child, "query")
                    if query is not None and not isinstance(query, str):
                        warnings.append(
                            Warning(
                                rule_id=self.rule_id,
                                severity=self.severity,
                                message=f"query must be str, got {type(query).__name__}",
                                file_path=analyzer.file_path,
                                line=child.lineno,
                                column=child.col_offset + 1,
                                code_snippet=analyzer.get_code_snippet(child.lineno),
                                fix_suggestion="Use query='text'",
                            )
                        )
                    result_index = self._get_kwarg_value(child, "result_index")
                    if result_index is not None:
                        if not isinstance(result_index, int):
                            warnings.append(
                                Warning(
                                    rule_id=self.rule_id,
                                    severity=self.severity,
                                    message=f"result_index must be int, got {type(result_index).__name__}",
                                    file_path=analyzer.file_path,
                                    line=child.lineno,
                                    column=child.col_offset + 1,
                                    code_snippet=analyzer.get_code_snippet(
                                        child.lineno
                                    ),
                                    fix_suggestion="Use result_index=0",
                                )
                            )
                        elif result_index < 0:
                            warnings.append(
                                Warning(
                                    rule_id=self.rule_id,
                                    severity=self.severity,
                                    message=f"result_index must be >= 0, got {result_index}",
                                    file_path=analyzer.file_path,
                                    line=child.lineno,
                                    column=child.col_offset + 1,
                                    code_snippet=analyzer.get_code_snippet(
                                        child.lineno
                                    ),
                                    fix_suggestion="Use result_index=0 or higher",
                                )
                            )
                    timeout = self._get_kwarg_value(child, "timeout")
                    if timeout is not None:
                        if not isinstance(timeout, int):
                            warnings.append(
                                Warning(
                                    rule_id=self.rule_id,
                                    severity=self.severity,
                                    message=f"timeout must be int, got {type(timeout).__name__}",
                                    file_path=analyzer.file_path,
                                    line=child.lineno,
                                    column=child.col_offset + 1,
                                    code_snippet=analyzer.get_code_snippet(
                                        child.lineno
                                    ),
                                    fix_suggestion="Use timeout=10",
                                )
                            )
                        elif timeout <= 0:
                            warnings.append(
                                Warning(
                                    rule_id=self.rule_id,
                                    severity=self.severity,
                                    message=f"timeout must be > 0, got {timeout}",
                                    file_path=analyzer.file_path,
                                    line=child.lineno,
                                    column=child.col_offset + 1,
                                    code_snippet=analyzer.get_code_snippet(
                                        child.lineno
                                    ),
                                    fix_suggestion="Use timeout=10 or higher",
                                )
                            )
        return warnings

    def _is_inline_query_and_click(self, node: ast.Call) -> bool:
        if isinstance(node.func, ast.Attribute):
            if node.func.attr == "inline_query_and_click":
                if isinstance(node.func.value, ast.Name):
                    if node.func.value.id == "kernel":
                        return True
        return False

    def _get_arg_value(self, node: ast.Call, arg_name: str, pos: int) -> Any:
        if pos < len(node.args):
            return self._get_value(node.args[pos])
        for kw in node.keywords:
            if kw.arg == arg_name:
                return self._get_value(kw.value)
        return None

    def _get_kwarg_value(self, node: ast.Call, kw_name: str) -> Any:
        for kw in node.keywords:
            if kw.arg == kw_name:
                return self._get_value(kw.value)
        return None

    def _get_value(self, node: ast.expr) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        return None


class DatabaseKeyFormatRule(WarningRule):
    """Check that module and key in kernel.db_set/get/delete match ^[a-zA-Z0-9_-]{1,64}$."""

    rule_id = "MCUB025"
    severity = "warning"
    message = "Invalid module/key format. Must match ^[a-zA-Z0-9_-]{{1,64}}$ (alphanumeric, underscore, hyphen, max 64 chars)."

    _key_pattern = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
    _db_methods = {"db_set", "db_get", "db_delete"}

    def check(
        self, analyzer: "SourceAnalyzer", node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[Warning]:
        warnings = []

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if self._is_db_call(child):
                    module = self._get_arg_value(child, "module", 0)
                    if module is not None:
                        if not isinstance(module, str):
                            warnings.append(
                                Warning(
                                    rule_id=self.rule_id,
                                    severity=self.severity,
                                    message=f"module must be str, got {type(module).__name__}",
                                    file_path=analyzer.file_path,
                                    line=child.lineno,
                                    column=child.col_offset + 1,
                                    code_snippet=analyzer.get_code_snippet(
                                        child.lineno
                                    ),
                                    fix_suggestion="Use module='modulename'",
                                )
                            )
                        elif not self._key_pattern.match(module):
                            invalid_chars = set(
                                c for c in module if not c.isalnum() and c not in "_-"
                            )
                            if invalid_chars:
                                warnings.append(
                                    Warning(
                                        rule_id=self.rule_id,
                                        severity=self.severity,
                                        message=f"module contains invalid characters: {invalid_chars}",
                                        file_path=analyzer.file_path,
                                        line=child.lineno,
                                        column=child.col_offset + 1,
                                        code_snippet=analyzer.get_code_snippet(
                                            child.lineno
                                        ),
                                        fix_suggestion="Use only alphanumeric, underscore, hyphen",
                                    )
                                )
                            if len(module) > 64:
                                warnings.append(
                                    Warning(
                                        rule_id=self.rule_id,
                                        severity=self.severity,
                                        message=f"module exceeds 64 characters ({len(module)})",
                                        file_path=analyzer.file_path,
                                        line=child.lineno,
                                        column=child.col_offset + 1,
                                        code_snippet=analyzer.get_code_snippet(
                                            child.lineno
                                        ),
                                        fix_suggestion="Use shorter module name (max 64 chars)",
                                    )
                                )
                    key = self._get_arg_value(child, "key", 1)
                    if key is not None:
                        if not isinstance(key, str):
                            warnings.append(
                                Warning(
                                    rule_id=self.rule_id,
                                    severity=self.severity,
                                    message=f"key must be str, got {type(key).__name__}",
                                    file_path=analyzer.file_path,
                                    line=child.lineno,
                                    column=child.col_offset + 1,
                                    code_snippet=analyzer.get_code_snippet(
                                        child.lineno
                                    ),
                                    fix_suggestion="Use key='keyname'",
                                )
                            )
                        elif not self._key_pattern.match(key):
                            invalid_chars = set(
                                c for c in key if not c.isalnum() and c not in "_-"
                            )
                            if invalid_chars:
                                warnings.append(
                                    Warning(
                                        rule_id=self.rule_id,
                                        severity=self.severity,
                                        message=f"key contains invalid characters: {invalid_chars}",
                                        file_path=analyzer.file_path,
                                        line=child.lineno,
                                        column=child.col_offset + 1,
                                        code_snippet=analyzer.get_code_snippet(
                                            child.lineno
                                        ),
                                        fix_suggestion="Use only alphanumeric, underscore, hyphen",
                                    )
                                )
                            if len(key) > 64:
                                warnings.append(
                                    Warning(
                                        rule_id=self.rule_id,
                                        severity=self.severity,
                                        message=f"key exceeds 64 characters ({len(key)})",
                                        file_path=analyzer.file_path,
                                        line=child.lineno,
                                        column=child.col_offset + 1,
                                        code_snippet=analyzer.get_code_snippet(
                                            child.lineno
                                        ),
                                        fix_suggestion="Use shorter key name (max 64 chars)",
                                    )
                                )
        return warnings

    def _is_db_call(self, node: ast.Call) -> bool:
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in self._db_methods:
                if isinstance(node.func.value, ast.Name):
                    if node.func.value.id == "kernel":
                        return True
        return False

    def _get_arg_value(self, node: ast.Call, arg_name: str, pos: int) -> Any:
        if pos < len(node.args):
            return self._get_value(node.args[pos])
        for kw in node.keywords:
            if kw.arg == arg_name:
                return self._get_value(kw.value)
        return None

    def _get_value(self, node: ast.expr) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        return None


class MissingCommandDescriptionRule(WarningRule):
    """Check that commands have descriptions in comments or docstring."""

    rule_id = "MCUB026"
    severity = "warning"
    message = "Command handler should have a description in comment or docstring."

    def should_check(self, analyzer: "SourceAnalyzer") -> bool:
        return any(
            "register.command" in dec["name"] for dec in analyzer.current_decorators
        )

    def check(
        self, analyzer: "SourceAnalyzer", node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[Warning]:
        warnings = []

        for dec in analyzer.current_decorators:
            if "register.command" in dec["name"]:
                if not self._has_description(analyzer, node):
                    warnings.append(
                        Warning(
                            rule_id=self.rule_id,
                            severity=self.severity,
                            message=self.message,
                            file_path=analyzer.file_path,
                            line=node.lineno,
                            column=node.col_offset + 1,
                            code_snippet=analyzer.get_code_snippet(node.lineno),
                            fix_suggestion="Add description in comment after decorator or in docstring",
                        )
                    )
        return warnings

    def _has_description(
        self, analyzer: "SourceAnalyzer", node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> bool:
        source_lines = analyzer.source_lines
        if not source_lines:
            return False

        line_idx = node.lineno - 1
        if line_idx > 0 and line_idx <= len(source_lines):
            prev_line = source_lines[line_idx - 1].strip()
            if prev_line.startswith("#"):
                return True

        if node.decorator_list:
            for dec in node.decorator_list:
                if hasattr(dec, "lineno") and dec.lineno > 0:
                    dec_idx = dec.lineno - 1
                    if 0 <= dec_idx < len(source_lines):
                        dec_line = source_lines[dec_idx]
                        if "#" in dec_line:
                            return True

        if ast.get_docstring(node):
            return True

        return False


class BareOrUnsafeExceptRule(WarningRule):
    """Check for try-except without proper error handling or bare except."""

    rule_id = "MCUB027"
    severity = "warning"
    message = "try-except block should call kernel.handle_error() or kernel.logger.error(), not silently swallow exceptions."

    def check(
        self, analyzer: "SourceAnalyzer", node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[Warning]:
        warnings = []

        for child in ast.walk(node):
            if isinstance(child, ast.Try):
                for handler in child.handlers:
                    if self._is_bare_except(handler):
                        warnings.append(
                            Warning(
                                rule_id=self.rule_id,
                                severity=self.severity,
                                message="Bare 'except:' catches all exceptions. Use 'except Exception:' for better error handling.",
                                file_path=analyzer.file_path,
                                line=handler.lineno,
                                column=handler.col_offset + 1,
                                code_snippet=analyzer.get_code_snippet(handler.lineno),
                                fix_suggestion="Use 'except Exception as e:' and handle error properly",
                            )
                        )
                    elif not self._has_error_handling(handler, analyzer):
                        warnings.append(
                            Warning(
                                rule_id=self.rule_id,
                                severity=self.severity,
                                message=self.message,
                                file_path=analyzer.file_path,
                                line=handler.lineno,
                                column=handler.col_offset + 1,
                                code_snippet=analyzer.get_code_snippet(handler.lineno),
                                fix_suggestion="Add kernel.handle_error(e, source=..., event=event) or kernel.logger.error(...)",
                            )
                        )
        return warnings

    def _is_bare_except(self, handler: ast.ExceptHandler) -> bool:
        return handler.type is None

    def _has_error_handling(
        self, handler: ast.ExceptHandler, analyzer: "SourceAnalyzer"
    ) -> bool:
        for stmt in handler.body:
            if self._contains_error_handling(stmt, analyzer):
                return True
        return False

    def _contains_error_handling(
        self, node: ast.AST, analyzer: "SourceAnalyzer"
    ) -> bool:
        for child in ast.walk(node):
            if isinstance(child, ast.Await):
                if isinstance(child.value, ast.Call):
                    if self._is_kernel_error_call(child.value):
                        return True
            elif isinstance(child, ast.Call):
                if self._is_kernel_error_call(child):
                    return True
            elif isinstance(child, ast.Raise):
                return True
        return False

    def _is_kernel_error_call(self, node: ast.Call) -> bool:
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in (
                "handle_error",
                "error",
                "warning",
                "info",
                "debug",
                "critical",
                "exception",
            ):
                if isinstance(node.func.value, ast.Attribute):
                    if node.func.value.attr == "logger":
                        if isinstance(node.func.value.value, ast.Name):
                            if node.func.value.value.id == "kernel":
                                return True
                elif isinstance(node.func.value, ast.Name):
                    if (
                        node.func.value.id == "kernel"
                        and node.func.attr == "handle_error"
                    ):
                        return True
        return False


class LoggerWithoutAwaitRule(WarningRule):
    """Check for kernel.handle_error called without await (should be async)."""

    rule_id = "MCUB028"
    severity = "warning"
    message = "kernel.handle_error() is async - must use 'await'. This is a common AI/agent mistake."

    def check(
        self, analyzer: "SourceAnalyzer", node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[Warning]:
        warnings = []

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if self._is_kernel_handle_error_call(child):
                    if not self._has_await_parent(child, node):
                        warnings.append(
                            Warning(
                                rule_id=self.rule_id,
                                severity=self.severity,
                                message=self.message,
                                file_path=analyzer.file_path,
                                line=child.lineno,
                                column=child.col_offset + 1,
                                code_snippet=analyzer.get_code_snippet(child.lineno),
                                fix_suggestion="Add 'await' before the call",
                            )
                        )
        return warnings

    def _is_kernel_handle_error_call(self, node: ast.Call) -> bool:
        if isinstance(node.func, ast.Attribute):
            if node.func.attr == "handle_error":
                if isinstance(node.func.value, ast.Name):
                    if node.func.value.id == "kernel":
                        return True
        return False

    def _has_await_parent(self, node: ast.Call, parent: ast.AST) -> bool:
        for child in ast.walk(parent):
            if isinstance(child, ast.Await):
                if isinstance(child.value, ast.Call):
                    if child.value is node:
                        return True
        return False


class MissingParseModeForHtmlRule(WarningRule):
    """Check for HTML tags in message without parse_mode='html'."""

    rule_id = "MCUB029"
    severity = "warning"
    message = "HTML tags detected in message but parse_mode='html' is missing."

    _html_tags = {
        "<b>",
        "<i>",
        "<u>",
        "<s>",
        "<spoiler>",
        "<code>",
        "<pre>",
        "<a ",
        "<emoji",
        "<blockquote",
        "<tg-emoji",
    }

    def check(
        self, analyzer: "SourceAnalyzer", node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[Warning]:
        warnings = []

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if self._is_message_call(child):
                    text_arg = self._get_text_arg(child)
                    if text_arg and self._has_html_tags(text_arg):
                        if not self._has_html_parse_mode(child):
                            warnings.append(
                                Warning(
                                    rule_id=self.rule_id,
                                    severity=self.severity,
                                    message=self.message,
                                    file_path=analyzer.file_path,
                                    line=child.lineno,
                                    column=child.col_offset + 1,
                                    code_snippet=analyzer.get_code_snippet(
                                        child.lineno
                                    ),
                                    fix_suggestion="Add parse_mode='html' parameter or remove HTML tags",
                                )
                            )
        return warnings

    def _is_message_call(self, node: ast.Call) -> bool:
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in ("edit", "reply", "respond", "send_message"):
                if isinstance(node.func.value, ast.Name):
                    if node.func.value.id == "event":
                        return True
        return False

    def _get_text_arg(self, node: ast.Call) -> str:
        if node.args:
            first_arg = node.args[0]
            if isinstance(first_arg, ast.Constant):
                return str(first_arg.value)
        for kw in node.keywords:
            if kw.arg in ("message", "text"):
                if isinstance(kw.value, ast.Constant):
                    return str(kw.value.value)
        return ""

    def _has_html_parse_mode(self, node: ast.Call) -> bool:
        for kw in node.keywords:
            if kw.arg == "parse_mode":
                if isinstance(kw.value, ast.Constant):
                    if kw.value.value == "html":
                        return True
        return False

    def _has_html_tags(self, text: str) -> bool:
        if not text:
            return False
        text_lower = text.lower()
        for tag in self._html_tags:
            if tag in text_lower:
                return True
        return False

    def _has_await_parent(self, node: ast.Call, parent: ast.AST) -> bool:
        for child in ast.walk(parent):
            if isinstance(child, ast.Await):
                if isinstance(child.value, ast.Call):
                    if child.value is node:
                        return True
        return False

    def _has_await_parent(self, node: ast.Call, parent: ast.AST) -> bool:
        for child in ast.walk(parent):
            if isinstance(child, ast.Await):
                if isinstance(child.value, ast.Call):
                    if child.value is node:
                        return True
        return False


def get_default_rules() -> RuleRegistry:
    """Get registry with all default rules."""
    registry = RuleRegistry()

    rules = [
        EventEditWithButtonsRule(),
        EventEditWithReplyMarkupRule(),
        CallbackWithoutPatternRule(),
        EventAnswerShowAlertRule(),
        EventDeleteBotMessageRule(),
        BotClientDeleteMessageRule(),
        MissingBotClientRule(),
        AsyncWithoutAwaitRule(),
        RegisterTypoRule(),
        ButtonInlineFormatRule(),
        WrongEventTypeRule(),
        ClientDeleteMessagesRule(),
        RawEventInHandlerRule(),
        EventEditInCallbackRule(),
        AsyncFunctionRequiredRule(),
        IncorrectCallbackDataRule(),
        MissingBotClientInEventRule(),
        MissingPatternInEventRule(),
        WatcherTagsRule(),
        LoopParamsRule(),
        LifecycleHandlerRule(),
        MethodDecoratorRule(),
        InlineFormUsageRule(),
        InlineQueryAndClickRule(),
        DatabaseKeyFormatRule(),
        MissingCommandDescriptionRule(),
        BareOrUnsafeExceptRule(),
        LoggerWithoutAwaitRule(),
        MissingParseModeForHtmlRule(),
    ]

    for rule in rules:
        registry.register(rule)

    return registry
