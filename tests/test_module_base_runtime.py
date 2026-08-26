#!/usr/bin/env python3

from __future__ import annotations

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


class DummyRegister:
    def __init__(self) -> None:
        self.commands: dict[str, object] = {}
        self.bot_commands: dict[str, object] = {}

    def command(self, pattern: str, **_kwargs):
        def decorator(func):
            self.commands[pattern] = func
            return func

        return decorator

    def bot_command(self, pattern: str, **_kwargs):
        def decorator(func):
            self.bot_commands[pattern] = func
            return func

        return decorator

    def watcher(self, *_args, **_kwargs):
        def decorator(func):
            return func

        return decorator

    def event(self, *_args, **_kwargs):
        def decorator(func):
            return func

        return decorator

    def loop(self, *_args, **_kwargs):
        def decorator(func):
            return func

        return decorator


def make_kernel(*, prefix: str = ".", lang: str = "ru"):
    kernel = MagicMock()
    kernel.logger = MagicMock()
    kernel.db_manager = MagicMock()
    kernel.cache = MagicMock()
    kernel.custom_prefix = prefix
    kernel.config = {"language": lang}
    kernel.loaded_modules = {}
    kernel.system_modules = {}
    kernel._class_module_instances = {}
    kernel._hikka_compat_allmodules_proxy = None
    return kernel


def make_event(*, text: str, is_pm: bool) -> SimpleNamespace:
    chat = SimpleNamespace(megagroup=not is_pm, broadcast=False, gigagroup=False)
    message = SimpleNamespace(
        out=True,
        media=None,
        fwd_from=None,
        reply_to=None,
        text=text,
    )
    return SimpleNamespace(
        text=text,
        raw_text=text,
        chat=chat,
        message=message,
        sender_id=1,
        chat_id=100,
    )


class TestModuleBaseRuntime:
    def test_rich_button_registers_through_module_callback_map(self):
        from core.lib.loader.module_base import ModuleBase

        class RichButtonsMod(ModuleBase):
            name = "RichButtonsMod"
            strings = {"en": {"name": "Rich buttons"}}

            async def on_run(self, event, *args, **kwargs):
                return None

        kernel = make_kernel()
        kernel.inline_callback_map = {}
        kernel._inline_cb_lock = threading.Lock()
        module = RichButtonsMod(kernel, MagicMock(), DummyRegister())

        button = module.Button.rich.inline(
            "Run",
            handler=module.on_run,
            args=(1, 2, 3),
            kwargs={"foo": "bar"},
            ttl=60,
            allow_user="all",
            style="success",
        )

        entry = kernel.inline_callback_map[button.token]
        assert button.text == "Run"
        assert button.style == "success"
        assert 1 <= len(button.token.encode("utf-8")) <= 64
        assert entry["args"] == (1, 2, 3)
        assert entry["kwargs"] == {"foo": "bar"}
        assert entry["module_name"] == module.name
        assert entry["allow_all"] is True
        assert entry["expires_at"] > 0
        assert button.token in module._callback_tokens

        module._cleanup_callback_tokens()
        assert button.token not in kernel.inline_callback_map

    def test_rich_button_validates_handler_arguments_and_style(self):
        from core.lib.loader.module_base import ModuleBase

        module = ModuleBase.__new__(ModuleBase)
        factory = ModuleBase.RichButtonFactory(module)

        with pytest.raises(TypeError, match="handler"):
            factory.inline("Run", handler=None)
        with pytest.raises(TypeError, match="args"):
            factory.inline("Run", handler=lambda *_: None, args="bad")
        with pytest.raises(TypeError, match="kwargs"):
            factory.inline("Run", handler=lambda *_: None, kwargs=[("x", 1)])
        with pytest.raises(ValueError, match="style"):
            factory.inline("Run", handler=lambda *_: None, style="invalid")

    def test_rich_button_html_tag_registers_once_and_escapes(self):
        from core.lib.loader.module_base import ModuleBase
        from core.lib.rich_buttons import RichCallbackButton, render_rich_button

        class RichButtonsMod(ModuleBase):
            name = "RichHtmlButtonsMod"
            strings = {"en": {"name": "Rich buttons"}}

            async def on_run(self, event, *args, **kwargs):
                return None

        kernel = make_kernel()
        kernel.inline_callback_map = {}
        kernel._inline_cb_lock = threading.Lock()
        module = RichButtonsMod(kernel, MagicMock(), DummyRegister())

        tag = module.Button.rich.inline(
            "Run <now>",
            handler=module.on_run,
            args=(1, 2, 3),
            kwargs={"foo": "bar"},
            style="success",
            html_tag=True,
        )

        assert len(kernel.inline_callback_map) == 1
        token, entry = next(iter(kernel.inline_callback_map.items()))
        assert tag == (
            '<tg-button type="callback_data" '
            f'data="{token}" style="success">Run &lt;now&gt;</tg-button>'
        )
        assert entry["args"] == (1, 2, 3)
        assert entry["kwargs"] == {"foo": "bar"}
        assert render_rich_button(RichCallbackButton("A <b>", 'token"x', "link")) == (
            '<tg-button type="callback_data" data="token&quot;x" '
            'style="link">A &lt;b&gt;</tg-button>'
        )
        with pytest.raises(TypeError, match="html_tag"):
            module.Button.rich.inline("Run", module.on_run, html_tag="yes")

    def test_two_manual_rich_tags_share_one_row_without_duplicate_registration(self):
        from telethon.extensions.richparser import BlockButtonRow, parse_rich_html

        from core.lib.loader.module_base import ModuleBase

        class RichButtonsMod(ModuleBase):
            name = "RichManualRowMod"
            strings = {"en": {"name": "Rich buttons"}}

            async def on_run(self, event):
                return None

        kernel = make_kernel()
        kernel.inline_callback_map = {}
        kernel._inline_cb_lock = threading.Lock()
        module = RichButtonsMod(kernel, MagicMock(), DummyRegister())
        html = (
            "<tg-button-row>"
            f'{module.Button.rich.inline("One", module.on_run, html_tag=True)}'
            f'{module.Button.rich.inline("Two", module.on_run, html_tag=True)}'
            "</tg-button-row>"
        )

        assert len(kernel.inline_callback_map) == 2
        rows = [
            block
            for block in parse_rich_html(html)
            if isinstance(block, BlockButtonRow)
        ]
        assert len(rows) == 1
        assert len(rows[0].buttons) == 2

    def test_rich_page_button_helpers_and_input_reuse_normal_registration(self):
        from core.lib.loader.module_base import ModuleBase
        from core.lib.rich_buttons import RichPageButton, render_rich_page_button

        class Register:
            def __init__(self):
                self.calls = []

            def inline_temp(self, handler, **kwargs):
                self.calls.append((handler, kwargs))
                return "input-token"

        kernel = make_kernel()
        kernel.register = Register()
        module = ModuleBase.__new__(ModuleBase)
        module.kernel = kernel
        module.name = "RichHelpers"
        module._get_user_module = lambda: None
        factory = ModuleBase.RichButtonFactory(module)

        assert factory.url("Docs", "https://example.com") == RichPageButton(
            "Docs", "url", {"url": "https://example.com"}
        )
        assert (
            factory.switch("Search", "q", same_peer=False).type == "switch_inline_query"
        )
        assert factory.copy("Copy", "x").attrs == {"text": "x"}
        assert factory.text("Display").type == "disabled"
        assert factory.game().type == "game"
        assert factory.unknown().type == "disabled"
        assert render_rich_page_button(factory.copy("<", '"')) == (
            '<tg-button type="copy_text" text="&quot;">&lt;</tg-button>'
        )

        async def on_input(event, value, data):
            return None

        input_spec = factory.input("Ask", on_input, placeholder="type", data="marker")
        assert input_spec.type == "switch_inline_query_current_chat"
        assert input_spec.attrs == {"query": "input-token type"}
        assert len(kernel.register.calls) == 1
        with pytest.raises(NotImplementedError, match="normal buttons"):
            factory.request_phone("Phone")
        with pytest.raises(NotImplementedError, match="icons"):
            factory.with_icon(factory.game(), 1)
        with pytest.raises(ValueError, match="https"):
            factory.url("Bad", "ftp://example.com")

    def test_strings_remain_callable(self):
        from core.lib.loader.module_base import ModuleBase

        class StringsMod(ModuleBase):
            name = "StringsMod"
            strings = {
                "ru": {"hello": "Пpивeт {name}"},
                "en": {"hello": "Hello {name}"},
            }

        instance = StringsMod(make_kernel(lang="en"), MagicMock(), DummyRegister())

        assert instance.strings("hello", name="MCUB") == "Hello MCUB"
        assert instance.strings["hello"] == "Hello {name}"

    def test_runtime_helpers_and_lookup(self):
        from core.lib.loader.module_base import ModuleBase
        from utils import get_lang, get_prefix

        class HelperMod(ModuleBase):
            name = "HelperMod"
            strings = {"ru": {"ok": "ok"}, "en": {"ok": "ok"}}

        kernel = make_kernel(prefix="!", lang="en")
        dep_instance = SimpleNamespace(name="DepMod")
        dep_module = SimpleNamespace(
            __name__="dep_module", _class_instance=dep_instance
        )
        kernel.loaded_modules = {"DepMod": dep_module}
        constructed_only = SimpleNamespace(name="ConstructedOnly")
        kernel._class_module_instances = {"ConstructedOnly": constructed_only}

        instance = HelperMod(kernel, MagicMock(), DummyRegister())
        event = make_event(text="!demo 42 --flag", is_pm=True)

        parser = instance.args(event)

        assert instance.get_prefix() == "!"
        assert instance.get_lang() == "en"
        assert get_prefix(instance) == "!"
        assert get_lang(instance) == "en"
        assert parser.command == "demo"
        assert parser.get(0) == 42
        assert parser.get_flag("flag") is True
        assert instance.lookup_module("DepMod") is dep_instance
        assert instance.lookup_module("DepMod", all_loaded=True) is dep_instance
        assert instance.lookup_module("ConstructedOnly") is constructed_only
        assert instance.lookup_module("ConstructedOnly", all_loaded=True) is None
        assert instance.require_module("DepMod") is dep_instance
        assert instance.require_module("DepMod", all_loaded=True) is dep_instance

        with pytest.raises(LookupError):
            instance.require_module("MissingMod")

    @pytest.mark.asyncio
    async def test_permission_decorator_filters_commands(self):
        from core.lib.loader.module_base import ModuleBase, command, permission

        class PermissionMod(ModuleBase):
            name = "PermissionMod"
            strings = {"ru": {"ok": "ok"}}

            def __init__(self, *args, **kwargs):
                self.calls = 0
                super().__init__(*args, **kwargs)

            @command("secret")
            @permission(only_pm=True)
            async def secret(self, event):
                self.calls += 1

        register = DummyRegister()
        instance = PermissionMod(make_kernel(), MagicMock(), register)

        await register.commands["secret"](make_event(text=".secret", is_pm=False))
        await register.commands["secret"](make_event(text=".secret", is_pm=True))

        assert instance.calls == 1

    def test_loop_objects_bind_back_to_instance(self):
        from core.lib.loader.module_base import ModuleBase, loop
        from core.lib.loader.register import InfiniteLoop, Register

        class LoopMod(ModuleBase):
            name = "LoopMod"
            strings = {"ru": {"ok": "ok"}}

            @loop(interval=60, autostart=False)
            async def ticker(self):
                return None

        instance = LoopMod(make_kernel(), MagicMock(), Register(make_kernel()))

        assert isinstance(instance.ticker, InfiniteLoop)

    @pytest.mark.asyncio
    async def test_run_post_load_calls_on_reload(self):
        from core.lib.loader.loader import ModuleLoader

        kernel = make_kernel()
        loader = ModuleLoader(kernel)

        class Instance:
            def __init__(self):
                self._loops = []
                self._loaded = False
                self.reload_calls = 0

            async def on_load(self):
                return None

            async def on_reload(self):
                self.reload_calls += 1

            async def on_install(self):
                return None

        instance = Instance()
        module = SimpleNamespace(
            register=SimpleNamespace(__loops__=[]), _class_instance=instance
        )

        await loader.run_post_load(module, "LoopMod", is_install=False, is_reload=True)

        assert instance.reload_calls == 1

    def test_cleanup_callback_tokens_empty_proxy_does_not_touch_protected_map(self):
        from core.lib.loader.kernel_proxy import ModuleKernelProxy
        from core.lib.loader.module_base import ModuleBase

        class CallbackMod(ModuleBase):
            name = "CallbackMod"
            strings = {"ru": {"ok": "ok"}}

        real_kernel = make_kernel()
        real_kernel.register = DummyRegister()
        real_kernel.inline_callback_map = {"token": {"unit": "keep"}}
        real_kernel._inline_cb_lock = threading.Lock()

        instance = CallbackMod(
            ModuleKernelProxy(real_kernel, "eval_yuweid"),
            MagicMock(),
            DummyRegister(),
        )
        instance._callback_tokens = []

        instance._cleanup_callback_tokens()

        assert real_kernel.inline_callback_map == {"token": {"unit": "keep"}}

    def test_cleanup_callback_tokens_uses_proxy_safe_removal(self):
        from core.lib.loader.kernel_proxy import ModuleKernelProxy
        from core.lib.loader.module_base import ModuleBase

        class CallbackMod(ModuleBase):
            name = "CallbackMod"
            strings = {"ru": {"ok": "ok"}}

        real_kernel = make_kernel()
        real_kernel.register = DummyRegister()
        real_kernel.inline_callback_map = {
            "remove": {"unit": "old"},
            "keep": {"unit": "live"},
        }
        real_kernel._inline_cb_lock = threading.Lock()

        instance = CallbackMod(
            ModuleKernelProxy(real_kernel, "eval_yuweid"),
            MagicMock(),
            DummyRegister(),
        )
        instance._callback_tokens = ["remove", "missing"]

        instance._cleanup_callback_tokens()

        assert real_kernel.inline_callback_map == {"keep": {"unit": "live"}}
        assert instance._callback_tokens == []

    def test_kernel_proxy_exposes_readonly_live_config_view(self):
        from core.lib.loader.kernel_proxy import ModuleKernelProxy

        real_kernel = make_kernel()
        real_kernel._live_module_configs = {"dnd-MCUB-repo": {"enabled": True}}
        proxy = ModuleKernelProxy(real_kernel, "dnd-MCUB-repo")

        assert getattr(proxy, "_live_module_configs", {}).get("dnd-MCUB-repo") == {
            "enabled": True
        }
        assert proxy.get_live_module_config("dnd-MCUB-repo") == {"enabled": True}

        with pytest.raises(TypeError):
            proxy._live_module_configs["other"] = {}

        assert "other" not in real_kernel._live_module_configs

    def test_kernel_proxy_keeps_public_module_state_local(self):
        from core.lib.loader.kernel_proxy import ModuleKernelProxy
        from core.lib.utils.exceptions import CallInsecure

        real_kernel = make_kernel()
        proxy = ModuleKernelProxy(real_kernel, "silent-tags-MCUB-repo")

        proxy.silent_tags_ratelimit = []
        proxy.silent_tags_ratelimit += [123]

        assert proxy.silent_tags_ratelimit == [123]
        assert "silent_tags_ratelimit" not in real_kernel.__dict__

        with pytest.raises(CallInsecure):
            proxy._live_module_configs = {}

        with pytest.raises(CallInsecure):
            proxy.loaded_modules = {}

    def test_kernel_proxy_blocks_core_registry_reads(self):
        from core.lib.loader.kernel_proxy import ModuleKernelProxy
        from core.lib.utils.exceptions import CallInsecure

        real_kernel = make_kernel()
        real_kernel.register = DummyRegister()
        proxy = ModuleKernelProxy(real_kernel, "guarded-MCUB-repo")

        for name in (
            "loaded_modules",
            "command_handlers",
            "inline_callback_map",
            "loader",
        ):
            with pytest.raises(CallInsecure) as exc_info:
                getattr(proxy, name)
            assert exc_info.value.name == name
            assert exc_info.value.module_name == "guarded-MCUB-repo"

        with pytest.raises(CallInsecure) as exc_info:
            proxy.register.kernel
        assert exc_info.value.name == "kernel"
        assert exc_info.value.module_name == "guarded-MCUB-repo"
