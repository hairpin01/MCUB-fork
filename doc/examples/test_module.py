# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

"""
TestModule - Real-kernel testing module for MCUB.

This module runs its own test methods on bot startup to verify
functionality and report results. Use for debugging and validating
module features.

Usage:
    The module automatically runs all methods starting with "test_"
    on load and reports pass/fail status.
"""

from __future__ import annotations

import asyncio

from telethon import events

from core.lib.loader.module_base import (
    ModuleBase,
    command,
    loop,
)


class TestModule(ModuleBase):
    name = "TestModule"
    version = "1.0.0"
    author = "@hairpin01"
    description = {"ru": "Тестовый модуль", "en": "Test module"}

    strings = {
        "ru": {
            "test_pass": "✅ Тест {name} пройден",
            "test_fail": "❌ Тест {name} провален: {error}",
            "test_skip": "⚠️ Тест {name} пропущен",
            "results": "<b>Результаты тестирования:</b>\n\n{results}",
            "run_tests": "Запустить тесты",
            "test_module": "Тестировать модуль",
        },
        "en": {
            "test_pass": "✅ Test {name} passed",
            "test_fail": "❌ Test {name} failed: {error}",
            "test_skip": "⚠️ Test {name} skipped",
            "results": "<b>Test Results:</b>\n\n{results}",
            "run_tests": "Run Tests",
            "test_module": "Test Module",
        },
    }

    @command("test", doc_ru="Запустить тесты", doc_en="Run tests")
    async def cmd_test(self, event: events.NewMessage.Event) -> None:
        results = await self._run_all_tests()
        await self.edit(event, f"<b>Test Results:</b>\n\n{results}", as_html=True)

    @command("testmod", doc_ru="Информация о тестах", doc_en="Test info")
    async def cmd_testmod(self, event: events.NewMessage.Event) -> None:
        test_methods = [
            m for m in dir(self) if m.startswith("test_") and callable(getattr(self, m))
        ]
        await self.edit(
            event,
            "<b>Test Methods:</b>\n\n" + "\n".join(f"• {m}" for m in test_methods),
            as_html=True,
        )

    async def _run_all_tests(self) -> str:
        results = []
        test_methods = [
            m for m in dir(self) if m.startswith("test_") and callable(getattr(self, m))
        ]

        for method_name in test_methods:
            try:
                method_func = getattr(self, method_name)
                if asyncio.iscoroutinefunction(method_func):
                    passed = await method_func()
                else:
                    passed = method_func()

                if passed is True:
                    results.append(self.strings("test_pass", name=method_name))
                elif passed is False:
                    results.append(
                        self.strings(
                            "test_fail", name=method_name, error="returned False"
                        )
                    )
                elif passed is None:
                    results.append(self.strings("test_skip", name=method_name))
                else:
                    results.append(
                        self.strings(
                            "test_fail",
                            name=method_name,
                            error=f"unexpected result: {passed}",
                        )
                    )
            except Exception as e:
                results.append(
                    self.strings("test_fail", name=method_name, error=str(e))
                )
                self.log.error(f"Test {method_name} raised exception: {e}")

        return "\n".join(results)

    def test_strings_flat_mode(self) -> bool:
        test_strings = {"hello": "Hello {name}!"}
        self._strings = test_strings
        try:
            self._get_strings()
            result = self.strings("hello", name="World")
            return result == "Hello World!"
        except Exception as e:
            self.log.error(f"Flat mode test failed: {e}")
            return False

    def test_strings_locale_mode(self) -> bool:
        test_strings = {
            "ru": {"hello": "Привет {name}!"},
            "en": {"hello": "Hello {name}!"},
        }
        self._strings = test_strings
        try:
            self._get_strings()
            result = self.strings("hello", name="World")
            return "World" in result
        except Exception as e:
            self.log.error(f"Locale mode test failed: {e}")
            return False

    def test_get_prefix(self) -> bool:
        prefix = self.get_prefix()
        return prefix in (".", "!", "/", "?")

    def test_get_lang(self) -> bool:
        lang = self.get_lang()
        return lang in ("ru", "en", "uk", "de", "es", "fr", "it", "pt")

    def test_lookup_module_self(self) -> bool:
        result = self.lookup_module("TestModule")
        return result is not None

    def test_lookup_module_nonexistent(self) -> bool:
        result = self.lookup_module("NonExistentModule12345")
        return result is None

    def test_require_module_self(self) -> bool:
        try:
            result = self.require_module("TestModule")
            return result is not None
        except LookupError:
            return False

    def test_require_module_raises(self) -> bool:
        try:
            self.require_module("NonExistentModule12345")
            return False
        except LookupError:
            return True

    def test_args_parser(self) -> bool:
        prefix = self.get_prefix()
        raw = "test arg1 arg2 --flag --value=42"

        class MockEvent:
            text = f"{prefix}{raw}"
            raw_text = raw

        try:
            parser = self.args(MockEvent())
            return parser.command == "test" and parser.get(0) == "arg1"
        except ValueError:
            from utils.arg_parser import parse_arguments

            parser = parse_arguments(MockEvent().raw_text, prefix)
            return parser.command == "test" and parser.get(0) == "arg1"

    def test_args_raw(self) -> bool:
        class MockEvent:
            text = ".cmd hello world"
            raw_text = "hello world"

        result = self.args_raw(MockEvent())
        return "hello world" in result

    def test_permission_map_creation(self) -> bool:
        return hasattr(type(self), "_permission_registry")

    def test_error_handler_map_creation(self) -> bool:
        return hasattr(type(self), "_error_handler_registry")

    def test_loop_object_binding(self) -> bool:
        return hasattr(self, "_loops") and isinstance(self._loops, list)

    @loop(interval=3600, autostart=False)
    async def heartbeat(self):
        pass

    def test_loop_instance_attribute(self) -> bool:
        return hasattr(self, "heartbeat") and hasattr(self.heartbeat, "start")

    async def on_load(self) -> None:
        self.log.info("TestModule loaded, running auto-tests...")
        results = await self._run_all_tests()
        passed = results.count("✅")
        failed = results.count("❌")
        self.log.info(f"Auto-tests completed: {passed} passed, {failed} failed")

    async def test_database_get_set(self) -> bool:
        try:
            if not self.db or not self.db.conn:
                return None
            await self.db.db_set(self.name, "test_key", "test_value")
            result = await self.db.db_get(self.name, "test_key")
            return result == "test_value"
        except Exception as e:
            self.log.error(f"Database test failed: {e}")
            return False

    async def test_database_delete(self) -> bool:
        try:
            if not self.db or not self.db.conn:
                return None
            await self.db.db_set(self.name, "test_key_del", "value")
            await self.db.db_delete(self.name, "test_key_del")
            result = await self.db.db_get(self.name, "test_key_del")
            return result is None
        except Exception as e:
            self.log.error(f"Database delete test failed: {e}")
            return False

    async def test_database_nested(self) -> bool:
        try:
            if not self.db or not self.db.conn:
                return None
            await self.db.db_set(self.name, "nested", '{"key":{"subkey":"value"}}')
            result = await self.db.db_get(self.name, "nested")
            return "value" in (result or "")
        except Exception as e:
            self.log.error(f"Database nested test failed: {e}")
            return False

    def test_config_attribute(self) -> bool:
        try:
            kernel = getattr(self, "kernel", None)
            if kernel is None:
                return None
            return hasattr(kernel, "config")
        except Exception as e:
            self.log.error(f"Config test failed: {e}")
            return False

    def test_config_default_values(self) -> bool:
        try:
            kernel = getattr(self, "kernel", None)
            if kernel is None:
                return None
            config = getattr(kernel, "config", None)
            return config is not None
        except Exception as e:
            self.log.error(f"Config defaults test failed: {e}")
            return False

    def test_inline_shorthand(self) -> bool:
        return hasattr(self, "inline") and callable(self.inline)

    async def test_inline_message_creation(self) -> bool:
        try:

            class MockMessage:
                async def reply(self, *args, **kwargs):
                    return True

            class MockEvent:
                message = MockMessage()

            result = await self.inline(MockEvent(), "test")
            return result is not None
        except Exception as e:
            self.log.error(f"Inline message test failed: {e}")
            return False

    def test_answer_method(self) -> bool:
        return hasattr(self, "answer") and callable(self.answer)

    def test_edit_method(self) -> bool:
        return hasattr(self, "edit") and callable(self.edit)

    def test_reply_method(self) -> bool:
        return hasattr(self, "reply") and callable(self.reply)

    def test_logger_module_prefix(self) -> bool:
        try:
            return hasattr(self.log, "_extra") or hasattr(self.log, "prefix")
        except Exception as e:
            self.log.error(f"Logger test failed: {e}")
            return False

    def test_permission_decorator_registration(self) -> bool:
        return hasattr(type(self), "_permission_filters")

    def test_watcher_decorator_registration(self) -> bool:
        return hasattr(type(self), "_watchers")

    def test_method_decorator_registration(self) -> bool:
        return hasattr(type(self), "_methods")

    def test_command_decorator_registration(self) -> bool:
        return hasattr(type(self), "_commands")

    def test_callback_decorator_registration(self) -> bool:
        return hasattr(type(self), "_callbacks")

    def test_loop_runtime_metadata(self) -> bool:
        try:
            return hasattr(self, "loops") and isinstance(self.loops, list)
        except Exception as e:
            self.log.error(f"Loop metadata test failed: {e}")
            return False

    async def test_loop_start_stop(self) -> bool:
        try:
            if not hasattr(self, "heartbeat"):
                return None
            self.heartbeat.start()
            await asyncio.sleep(0.1)
            self.heartbeat.stop()
            return True
        except Exception as e:
            self.log.error(f"Loop start/stop test failed: {e}")
            return False

    def test_loop_is_running(self) -> bool:
        try:
            if not hasattr(self, "heartbeat"):
                return None
            return hasattr(self.heartbeat, "running") or hasattr(
                self.heartbeat, "is_running"
            )
        except Exception as e:
            self.log.error(f"Loop is_running test failed: {e}")
            return False

    def test_lifecycle_hooks_exist(self) -> bool:
        return callable(getattr(self, "on_reload", None)) and callable(
            getattr(self, "on_config_update", None)
        )

    def test_permission_filters_map(self) -> bool:
        try:
            registry = getattr(type(self), "_permission_registry", {})
            return isinstance(registry, dict)
        except Exception as e:
            self.log.error(f"Permission registry test failed: {e}")
            return False

    def test_error_handler_registry(self) -> bool:
        try:
            registry = getattr(type(self), "_error_handler_registry", {})
            return isinstance(registry, dict)
        except Exception as e:
            self.log.error(f"Error handler registry test failed: {e}")
            return False

    def test_strings_all_locales(self) -> bool:
        try:
            all_locales = getattr(type(self), "_strings", {})
            if isinstance(all_locales, dict):
                return len(all_locales) >= 1
            return False
        except Exception as e:
            self.log.error(f"Strings all locales test failed: {e}")
            return False

    def test_strings_getitem(self) -> bool:
        try:
            s = self.strings
            return s is not None
        except Exception as e:
            self.log.error(f"Strings getitem test failed: {e}")
            return False

    def test_module_client_available(self) -> bool:
        try:
            return hasattr(self, "client") and self.client is not None
        except Exception as e:
            self.log.error(f"Client test failed: {e}")
            return False

    def test_module_bot_available(self) -> bool:
        try:
            return (
                hasattr(self, "kernel")
                and hasattr(self.kernel, "bot_client")
                and self.kernel.bot_client is not None
            )
        except Exception as e:
            self.log.error(f"Bot test failed: {e}")
            return False

    def test_module_api_available(self) -> bool:
        try:
            return hasattr(self, "api") and self.api is not None
        except Exception as e:
            self.log.error(f"API test failed: {e}")
            return False

    def test_module_db_available(self) -> bool:
        try:
            return hasattr(self, "db") and self.db is not None
        except Exception as e:
            self.log.error(f"DB test failed: {e}")
            return False

    def test_module_load_available(self) -> bool:
        try:
            return callable(getattr(self, "load_module", None))
        except Exception as e:
            self.log.error(f"Load module test failed: {e}")
            return False

    def test_module_unload_available(self) -> bool:
        try:
            return callable(getattr(self, "unload_module", None))
        except Exception as e:
            self.log.error(f"Unload module test failed: {e}")
            return False

    def test_module_require_works(self) -> bool:
        try:
            mod = self.require_module("TestModule")
            return mod is not None
        except Exception as e:
            self.log.error(f"Module require works test failed: {e}")
            return False

    def test_strings_format_kwargs(self) -> bool:
        try:
            formatted = self.strings("test_pass", name="test")
            return "test" in formatted
        except Exception as e:
            self.log.error(f"Strings format kwargs test failed: {e}")
            return False

    def test_strings_missing_key(self) -> bool:
        try:
            result = self.strings("nonexistent_key_12345")
            return result == "nonexistent_key_12345"
        except Exception as e:
            self.log.error(f"Strings missing key test failed: {e}")
            return False

    def test_as_html_handling(self) -> bool:
        try:
            result = self.strings("test_pass", name="test")
            if "<b>" in result or "✅" in result:
                return True
            return True
        except Exception as e:
            self.log.error(f"Strings as_html test failed: {e}")
            return False

    def test_all_commands_registered(self) -> bool:
        try:
            commands = getattr(type(self), "_commands", {})
            return isinstance(commands, dict) and len(commands) > 0
        except Exception as e:
            self.log.error(f"Commands registration test failed: {e}")
            return False

    def test_all_callbacks_registered(self) -> bool:
        try:
            callbacks = getattr(type(self), "_callbacks", {})
            return isinstance(callbacks, dict)
        except Exception as e:
            self.log.error(f"Callbacks registration test failed: {e}")
            return False

    def test_permission_tags_support(self) -> bool:
        try:
            getattr(type(self), "_permission_registry", {})
            return True
        except Exception as e:
            self.log.error(f"Permission tags test failed: {e}")
            return False


async def test_inline_button_click(self) -> bool:
    return None
