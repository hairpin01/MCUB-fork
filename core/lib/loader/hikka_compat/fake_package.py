import asyncio
import importlib
import importlib.util
import re
import sys
import traceback
import types
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    pass

from .validators import validators
from .config import ConfigValue, ModuleConfig, LibraryConfig
from .runtime import (
    Module,
    Library,
    DbProxy,
    InlineProxy,
    _AllModulesStub,
    _CallableStringsDict,
    _StringsShim,
    _translator_stub,
)
from .decorators import (
    tds,
    tag,
    command,
    inline_handler,
    callback_handler,
    watcher,
    on,
    loop,
    InfiniteLoop,
    Placeholder,
)
from .utils import _Utils
from . import security
from . import translat as translations
from .types import (
    JSONSerializable,
    HerokuReplyMarkup,
    ListLike,
    Command,
    StringLoader,
    LoadError,
    CoreOverwriteError,
    CoreUnloadError,
    SelfUnload,
    SelfSuspend,
    StopLoop,
    CacheRecordEntity,
    CacheRecordPerms,
    CacheRecordFullChannel,
    CacheRecordFullUser,
    get_commands,
    get_inline_handlers,
    get_callback_handlers,
    get_watchers,
)


_FAKE_PKG_NAME = "__hikka_mcub_compat__"


_MODULE_ALIASES: dict[str, str] = {
    "heroku": "telethon",
    "herokutl": "telethon",
    "hikkatl": "telethon",
    "hikka": "telethon",
    "ftg": "telethon",
    "tgcalls": "telethon",
}


_HIKKA_INDICATORS = (
    "loader.tds",
    "loader.Module",
    "@loader.tds",
    "loader.ModuleConfig",
    "loader.command",
    "@loader.watcher",
    "loader.Library",
    "loader.LibraryConfig",
)


_GEEKG_INDICATORS = (
    "GeekInlineQuery",
    "self.inline._bot",
)


_NATIVE_MCUB_INDICATORS = (
    "def register(kernel",
    "from core.lib.loader import",
)


def _detect_module_type(source_code: str) -> str:
    native_score = sum(ind in source_code for ind in _NATIVE_MCUB_INDICATORS)
    hikka_score = sum(ind in source_code for ind in _HIKKA_INDICATORS)
    geek_score = sum(ind in source_code for ind in _GEEKG_INDICATORS)

    if native_score >= 1:
        return "native"
    if geek_score >= 1:
        return "geek"
    if hikka_score >= 1:
        return "hikka"
    return "native"


class ScamDetectionError(Exception):
    def __init__(self, message: str = "Scam detection triggered"):
        super().__init__(message)


class FloodWaitError(Exception):
    def __init__(self, seconds: int = 0):
        self.seconds = seconds
        super().__init__(f"Flood wait: {seconds}s")


_SUBMODULE_EXTRA_ATTRS: dict[str, dict] = {
    "herokutl.errors.common": {"ScamDetectionError": ScamDetectionError},
    "hikkatl.errors.common": {"ScamDetectionError": ScamDetectionError},
}


def _patch_aliased_submodule(alias_full: str) -> None:
    extras = _SUBMODULE_EXTRA_ATTRS.get(alias_full)
    if not extras:
        return
    mod = sys.modules.get(alias_full)
    if mod is None:
        return
    for attr_name, attr_val in extras.items():
        if not hasattr(mod, attr_name):
            try:
                setattr(mod, attr_name, attr_val)
            except (AttributeError, TypeError):
                proxy = types.ModuleType(alias_full)
                proxy.__dict__.update(mod.__dict__)
                proxy.__dict__[attr_name] = attr_val
                sys.modules[alias_full] = proxy


def _inject_module_alias(missing_top: str, missing_full: str) -> bool:
    real_top = _MODULE_ALIASES.get(missing_top)
    if real_top is None:
        return False

    try:
        real_mod = importlib.import_module(real_top)
    except ImportError:
        return False

    if missing_top not in sys.modules:
        sys.modules[missing_top] = real_mod

    real_prefix = real_top + "."
    for name, mod in list(sys.modules.items()):
        if name.startswith(real_prefix):
            alias_sub = missing_top + name[len(real_top) :]
            if alias_sub not in sys.modules:
                sys.modules[alias_sub] = mod
            _patch_aliased_submodule(alias_sub)

    alias_pkg = sys.modules[missing_top]
    if not getattr(alias_pkg, "__alias_patched__", False):

        def _alias_getattr(
            attr: str, _real=real_mod, _alias_top=missing_top, _real_top=real_top
        ):
            try:
                return getattr(_real, attr)
            except AttributeError:
                pass
            full_real = f"{_real_top}.{attr}"
            try:
                sub = importlib.import_module(full_real)
                sys.modules[f"{_alias_top}.{attr}"] = sub
                return sub
            except ImportError:
                fake_sub = types.ModuleType(f"{_alias_top}.{attr}")
                sys.modules[f"{_alias_top}.{attr}"] = fake_sub
                return fake_sub

        try:
            alias_pkg.__getattr__ = _alias_getattr
            alias_pkg.__alias_patched__ = True
        except (AttributeError, TypeError):
            pass

    if missing_full and missing_full != missing_top and missing_full not in sys.modules:
        real_full = real_top + missing_full[len(missing_top) :]
        try:
            sub = importlib.import_module(real_full)
            sys.modules[missing_full] = sub
            _patch_aliased_submodule(missing_full)
            parts = missing_full.split(".")
            for i in range(2, len(parts)):
                alias_partial = ".".join(parts[:i])
                real_partial = real_top + "." + ".".join(parts[1:i])
                if alias_partial not in sys.modules:
                    try:
                        sys.modules[alias_partial] = importlib.import_module(
                            real_partial
                        )
                        _patch_aliased_submodule(alias_partial)
                    except ImportError:
                        pass
        except ImportError:
            pass

    return True


class _HikkaCompatLoader:
    def __init__(self, mod: types.ModuleType) -> None:
        self._mod = mod

    def create_module(self, spec):
        return self._mod

    def exec_module(self, module) -> None:
        pass


class _HikkaCompatFinder:
    @classmethod
    def find_spec(cls, fullname: str, path, target=None):
        if fullname != _FAKE_PKG_NAME and not fullname.startswith(_FAKE_PKG_NAME + "."):
            return None

        mod = sys.modules.get(fullname)
        if mod is None:
            return None

        spec = importlib.util.spec_from_loader(
            fullname,
            loader=_HikkaCompatLoader(mod),
            origin="<hikka_compat>",
        )
        spec.submodule_search_locations = []
        return spec


def _ensure_fake_package() -> str:
    if not any(isinstance(f, _HikkaCompatFinder) for f in sys.meta_path):
        sys.meta_path.insert(0, _HikkaCompatFinder())

    if _FAKE_PKG_NAME in sys.modules:
        loader_mod = sys.modules.get(f"{_FAKE_PKG_NAME}.loader")
        if loader_mod is not None:
            loader_mod.command = command
            loader_mod.watcher = watcher
            loader_mod.on = on
            loader_mod.inline_handler = inline_handler
            loader_mod.callback_handler = callback_handler
        return _FAKE_PKG_NAME

    parent = types.ModuleType(_FAKE_PKG_NAME)
    parent.__path__ = []
    parent.__package__ = _FAKE_PKG_NAME
    parent.__spec__ = importlib.util.spec_from_loader(_FAKE_PKG_NAME, loader=None)

    loader_mod = types.ModuleType(f"{_FAKE_PKG_NAME}.loader")
    loader_mod.Module = Module
    loader_mod.Library = Library
    loader_mod.ModuleConfig = ModuleConfig
    loader_mod.LibraryConfig = LibraryConfig
    loader_mod.ConfigValue = ConfigValue
    loader_mod.validators = validators
    loader_mod.tds = tds
    loader_mod.tag = tag
    loader_mod.command = command
    loader_mod.loop = loop
    loader_mod.InfiniteLoop = InfiniteLoop
    loader_mod.Placeholder = Placeholder

    from . import security

    loader_mod.owner = security.owner
    loader_mod.group_owner = security.group_owner
    loader_mod.group_admin = security.group_admin
    loader_mod.group_admin_add_admins = security.group_admin_add_admins
    loader_mod.group_admin_change_info = security.group_admin_change_info
    loader_mod.group_admin_ban_users = security.group_admin_ban_users
    loader_mod.group_admin_delete_messages = security.group_admin_delete_messages
    loader_mod.group_admin_pin_messages = security.group_admin_pin_messages
    loader_mod.group_admin_invite_users = security.group_admin_invite_users
    loader_mod.group_member = security.group_member
    loader_mod.pm = security.pm
    loader_mod.unrestricted = security.unrestricted
    loader_mod.inline_everyone = security.inline_everyone
    loader_mod.sudo = security.sudo
    loader_mod.support = security.support

    loader_mod.OWNER = security.OWNER
    loader_mod.SUDO = security.SUDO
    loader_mod.SUPPORT = security.SUPPORT
    loader_mod.GROUP_OWNER = security.GROUP_OWNER
    loader_mod.GROUP_ADMIN = security.GROUP_ADMIN
    loader_mod.GROUP_MEMBER = security.GROUP_MEMBER
    loader_mod.PM = security.PM
    loader_mod.EVERYONE = security.EVERYONE
    loader_mod.ALL = security.ALL
    loader_mod.GROUP_ADMIN_ANY = security.GROUP_ADMIN_ANY
    loader_mod.DEFAULT_PERMISSIONS = security.DEFAULT_PERMISSIONS
    loader_mod.PUBLIC_PERMISSIONS = security.PUBLIC_PERMISSIONS
    loader_mod.BITMAP = security.BITMAP
    loader_mod.watcher = watcher
    loader_mod.on = on
    loader_mod.inline_handler = inline_handler
    loader_mod.callback_handler = callback_handler
    loader_mod.LoadError = LoadError
    loader_mod.CoreOverwriteError = CoreOverwriteError
    loader_mod.CoreUnloadError = CoreUnloadError
    loader_mod.SelfUnload = SelfUnload
    loader_mod.SelfSuspend = SelfSuspend
    loader_mod.StopLoop = StopLoop
    loader_mod.StringLoader = StringLoader
    loader_mod.VALID_PIP_PACKAGES = re.compile(
        r"# ?scope: ?pip ?((?:[A-Za-z0-9\-_>=<!\[\].]+(?:\s+|$))+)",
        re.MULTILINE,
    )
    loader_mod.VALID_APT_PACKAGES = re.compile(
        r"# ?scope: ?apt ?((?:[A-Za-z0-9\-_]+(?:\s+|$))+)",
        re.MULTILINE,
    )
    import site

    loader_mod.USER_INSTALL = not getattr(site, "ENABLE_USER_SITE", True)

    utils_mod = types.ModuleType(f"{_FAKE_PKG_NAME}.utils")
    utils_mod.answer = _Utils.answer
    utils_mod.get_args = _Utils.get_args
    utils_mod.get_args_raw = _Utils.get_args_raw
    utils_mod.get_args_split_by = _Utils.get_args_split_by
    utils_mod.get_args_html = _Utils.get_args_html
    utils_mod.get_chat_id = _Utils.get_chat_id
    utils_mod.escape_html = _Utils.escape_html
    utils_mod.remove_html = _Utils.remove_html
    utils_mod.get_link = _Utils.get_link
    utils_mod.mention = _Utils.mention
    utils_mod.get_user = _Utils.get_user
    utils_mod.get_target = _Utils.get_target
    utils_mod.run_sync = _Utils.run_sync
    utils_mod.BASEDIR = ""
    utils_mod.USERS_DIR = ""
    utils_mod.DOWNLOADS_DIR = ""

    security._security_mod.__name__ = f"{_FAKE_PKG_NAME}.security"
    translations._translations_mod.__name__ = f"{_FAKE_PKG_NAME}.translations"

    from . import inline_types as _inline_types
    from . import inline_utils as _inline_utils

    inline_types_mod = types.ModuleType(f"{_FAKE_PKG_NAME}.inline.types")
    for _attr_name in dir(_inline_types):
        if not _attr_name.startswith("_"):
            setattr(inline_types_mod, _attr_name, getattr(_inline_types, _attr_name))

    inline_mod = types.ModuleType(f"{_FAKE_PKG_NAME}.inline")
    inline_mod.types = inline_types_mod
    for _attr_name in dir(_inline_types):
        if not _attr_name.startswith("_"):
            setattr(inline_mod, _attr_name, getattr(_inline_types, _attr_name))

    inline_utils_mod = types.ModuleType(f"{_FAKE_PKG_NAME}.inline.utils")
    for _attr_name in dir(_inline_utils):
        if not _attr_name.startswith("_"):
            setattr(inline_utils_mod, _attr_name, getattr(_inline_utils, _attr_name))

    inline_mod.utils = inline_utils_mod

    strings_mod = types.ModuleType(f"{_FAKE_PKG_NAME}.strings")
    strings_mod.Strings = translations._StringsShim

    parent.loader = loader_mod
    parent.utils = utils_mod
    parent.security = security._security_mod
    parent.translations = translations._translations_mod
    parent.inline = inline_mod
    parent.strings = strings_mod

    sys.modules[_FAKE_PKG_NAME] = parent
    sys.modules[f"{_FAKE_PKG_NAME}.loader"] = loader_mod
    sys.modules[f"{_FAKE_PKG_NAME}.utils"] = utils_mod
    sys.modules[f"{_FAKE_PKG_NAME}.security"] = security._security_mod
    sys.modules[f"{_FAKE_PKG_NAME}.translations"] = translations._translations_mod
    sys.modules[f"{_FAKE_PKG_NAME}.inline"] = inline_mod
    sys.modules[f"{_FAKE_PKG_NAME}.inline.types"] = inline_types_mod
    sys.modules[f"{_FAKE_PKG_NAME}.inline.utils"] = inline_utils_mod
    sys.modules[f"{_FAKE_PKG_NAME}.strings"] = strings_mod

    return _FAKE_PKG_NAME


def is_hikka_module(source_code: str) -> bool:
    return _detect_module_type(source_code) == "hikka"


def _create_system_stub(pkg_name: str) -> None:
    """Create a stub module for system packages that can't be pip-installed."""
    if pkg_name in sys.modules:
        return

    stub = types.ModuleType(pkg_name)
    stub.__path__ = []
    stub.__file__ = f"<system stub: {pkg_name}>"

    if pkg_name == "git":

        class GitRepo:
            def __init__(self, path=None):
                self.working_dir = path

            def clone(self, url, to_path=None):
                return GitRepo(to_path)

        stub.Repo = GitRepo

    elif pkg_name in ("ffmpeg", "flac", "curl"):
        stub.command = None

    elif pkg_name == "requests":

        class FakeResponse:
            def __init__(self):
                self.status_code = 200
                self.text = ""
                self.content = b""

            def json(self):
                import json as _json

                return _json.loads(self.text)

        class FakeRequests:
            def get(self, url, **kwargs):
                return FakeResponse()

            def post(self, url, **kwargs):
                return FakeResponse()

        stub.get = lambda url, **kw: FakeResponse()
        stub.post = lambda url, **kw: FakeResponse()

    sys.modules[pkg_name] = stub


def _find_module_class(mod_obj: types.ModuleType) -> Optional[type]:
    candidates: list[type] = []
    for name in dir(mod_obj):
        obj = getattr(mod_obj, name, None)
        try:
            if isinstance(obj, type) and issubclass(obj, Module) and obj is not Module:
                candidates.append(obj)
        except TypeError:
            continue

    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    for cls in candidates:
        if not any(issubclass(other, cls) for other in candidates if other is not cls):
            return cls

    return candidates[0]


async def load_hikka_module(
    kernel,
    file_path: str,
    module_name: str,
) -> tuple[bool, str, dict]:
    from . import geek as _geek_compat

    pkg_name = _ensure_fake_package()
    child_pkg = f"{pkg_name}.{module_name}"

    try:
        source = Path(file_path).read_text(encoding="utf-8")
    except OSError as e:
        return False, f"Cannot read {file_path}: {e}", {}

    module_type = _detect_module_type(source)
    if module_type == "geek":
        kernel.logger.info(
            f"[hikka_compat] Detected GeekTG module '{module_name}', applying compatibility transform"
        )
        source = _geek_compat.compat(source)

    try:
        code = compile(source, file_path, "exec")
    except SyntaxError as e:
        return False, f"SyntaxError in {module_name}: {e}", {}

    mod_obj = types.ModuleType(child_pkg)
    mod_obj.__file__ = file_path
    mod_obj.__package__ = child_pkg
    mod_obj.__spec__ = importlib.util.spec_from_loader(child_pkg, loader=None)
    mod_obj.__path__ = []

    sys.modules[child_pkg] = mod_obj

    _MAX_DEP_RETRIES = 10

    for _attempt in range(_MAX_DEP_RETRIES):
        try:
            exec(code, mod_obj.__dict__)  # noqa: S102
            break
        except ModuleNotFoundError as e:
            missing_pkg = e.name.split(".")[0] if e.name else None
            missing_full = e.name or missing_pkg or ""

            if not missing_pkg:
                del sys.modules[child_pkg]
                tb = traceback.format_exc()
                return False, f"Runtime error loading {module_name}:\n{tb}", {}

            if _inject_module_alias(missing_pkg, missing_full):
                kernel.logger.info(
                    f"[hikka_compat] Resolved '{missing_full}' via alias table"
                )
                continue

            if missing_pkg == _FAKE_PKG_NAME or missing_full.startswith(_FAKE_PKG_NAME):
                kernel.logger.warning(
                    f"[hikka_compat] Fake package '{_FAKE_PKG_NAME}' vanished from "
                    f"sys.modules — re-injecting and retrying"
                )
                _ensure_fake_package()
                continue

            _SYSTEM_PACKAGES = {
                "git",
                "ffmpeg",
                "flac",
                "curl",
                "wget",
                "unzip",
                "tar",
                "gcc",
                "g++",
                "make",
                "cmake",
                "pkg-config",
                "libssl-dev",
                "python3-dev",
                "python-dev",
                "libffi-dev",
                "libjpeg-dev",
                "zlib1g-dev",
                "libxml2-dev",
                "libxslt-dev",
                "libcurl4-openssl-dev",
                "heroku",
                "tgcalls",
                "aexec",
                "pytgcalls",
            }
            if missing_pkg.lower() in _SYSTEM_PACKAGES:
                kernel.logger.warning(
                    f"[hikka_compat] Skipping system package '{missing_pkg}' - "
                    f"install it manually via apt/brew"
                )
                _create_system_stub(missing_pkg)
                continue

            import subprocess as _sp

            kernel.logger.info(
                f"[hikka_compat] Auto-installing missing dependency: {missing_pkg}"
            )
            strategies = [
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    missing_pkg,
                    "--break-system-packages",
                ],
                [sys.executable, "-m", "pip", "install", missing_pkg],
                [sys.executable, "-m", "pip", "install", missing_pkg, "--user"],
            ]
            installed = False
            for cmd in strategies:
                res = _sp.run(cmd, capture_output=True, text=True)
                if res.returncode == 0:
                    installed = True
                    break

            if not installed:
                kernel.logger.warning(
                    f"[hikka_compat] Could not install '{missing_pkg}' - "
                    f"trying to continue anyway"
                )
                continue

            mod_obj.__dict__.clear()
            mod_obj.__file__ = file_path
            mod_obj.__package__ = child_pkg
            mod_obj.__spec__ = importlib.util.spec_from_loader(child_pkg, loader=None)
            mod_obj.__path__ = []
        except Exception:
            del sys.modules[child_pkg]
            tb = traceback.format_exc()
            return False, f"Runtime error loading {module_name}:\n{tb}", {}
    else:
        del sys.modules[child_pkg]
        return False, f"Too many missing dependencies while loading {module_name}", {}

    cls = _find_module_class(mod_obj)
    if cls is None:
        del sys.modules[child_pkg]
        return False, f"No loader.Module subclass found in {module_name}", {}

    _raw_strings = cls.__dict__.get("strings", {})
    if isinstance(_raw_strings, dict) and not callable(_raw_strings):
        cls.strings = _CallableStringsDict(_raw_strings)

    if not hasattr(cls, "__origin__"):
        cls.__origin__ = f"<hikka_compat {file_path}>"
        cls.__force_internal__ = False

    try:
        instance = cls()
    except Exception as e:
        del sys.modules[child_pkg]
        return False, f"Error instantiating {cls.__name__}: {e}", {}

    instance._mcub_bind(kernel)

    if hasattr(instance, "config") and isinstance(instance.config, ModuleConfig):
        try:
            saved = await kernel.get_module_config(module_name)
            if saved:
                instance.config.load_from_dict(saved)
        except Exception:
            pass

    registered_cmds: list[str] = []
    conflicts: list[dict] = []
    event_handles: list = []

    if not kernel.current_loading_module:
        kernel.set_loading_module(module_name, "hikka")

    for attr_name in dir(cls):
        method = getattr(instance, attr_name, None)
        if not callable(method):
            continue

        if attr_name.endswith("cmd"):
            cmd_name = attr_name[:-3]
            if not cmd_name:
                continue
        elif getattr(method, "__hikka_command__", False):
            cmd_name = attr_name
        elif getattr(method, "__hikka_on_event__", None) is not None:
            event_type = method.__hikka_on_event__
            try:

                @kernel.client.on(event_type)
                async def _on_wrapper(event, _m=method):
                    try:
                        await _m(event)
                    except Exception as _e:
                        kernel.logger.error(
                            f"[hikka_compat] @on handler error in {module_name}: {_e}"
                        )

                event_handles.append(_on_wrapper)
            except Exception as e:
                kernel.logger.warning(
                    f"[hikka_compat] Could not register @on handler '{attr_name}' "
                    f"from {module_name}: {e}"
                )
            continue
        else:
            continue

        try:
            kernel.register_command(cmd_name, method)
            registered_cmds.append(cmd_name)
        except Exception as e:
            err_str = str(e)
            conflict_module = None
            if "already registered" in err_str.lower():
                import re

                m = re.search(r"already registered by ['\"]?([^'\"]+)['\"]?", err_str)
                if m:
                    conflict_module = m.group(1)
                if not conflict_module or conflict_module == "None":
                    conflict_module = kernel.command_owners.get(cmd_name)
                if not conflict_module:
                    conflict_module = kernel.current_loading_module
            conflicts.append(
                {
                    "command": cmd_name,
                    "owner": conflict_module or "unknown",
                    "error": err_str,
                }
            )
            kernel.logger.warning(
                f"[hikka_compat] Could not register command '{cmd_name}' "
                f"from {module_name}: {e}"
            )

    kernel.clear_loading_module()

    watcher_handles: list = []

    watcher_method = getattr(instance, "watcher", None)
    if callable(watcher_method):
        from telethon import events as _tl_events

        owner_id = getattr(kernel, "ADMIN_ID", None)

        async def _watcher_handler(event, _wm=watcher_method, _mn=module_name):
            try:
                await _wm(event)
            except Exception as _e:
                kernel.logger.error(f"[hikka_compat] watcher error in {_mn}: {_e}")

        @kernel.client.on(_tl_events.NewMessage(outgoing=True))
        async def _watcher_out(event):
            await _watcher_handler(event)

        @kernel.client.on(_tl_events.NewMessage(incoming=True, from_users=owner_id))
        async def _watcher_in(event):
            await _watcher_handler(event)

        watcher_handles.extend([_watcher_out, _watcher_in])
        instance._watcher_handles = watcher_handles

    instance._hikka_compat = True
    instance._registered_cmds = registered_cmds
    instance._event_handles = event_handles
    kernel.loaded_modules[module_name] = instance

    try:
        await instance.on_load()
    except Exception as e:
        kernel.logger.warning(f"[hikka_compat] on_load() error in {module_name}: {e}")

    if hasattr(instance, "client_ready") and callable(instance.client_ready):
        try:
            await instance.client_ready(kernel.client, instance.db)
        except Exception as e:
            kernel.logger.warning(
                f"[hikka_compat] client_ready() error in {module_name}: {e}"
            )

    kernel.logger.info(
        f"[hikka_compat] Loaded '{module_name}' "
        f"({cls.__name__}) — commands: {registered_cmds}"
    )
    return True, "", {"registered": registered_cmds, "conflicts": conflicts}


async def unload_hikka_module(kernel, module_name: str) -> bool:
    instance = kernel.loaded_modules.get(module_name)
    if instance is None or not getattr(instance, "_hikka_compat", False):
        return False

    try:
        await instance.on_unload()
    except Exception as e:
        kernel.logger.warning(f"[hikka_compat] on_unload() error in {module_name}: {e}")

    for cmd in getattr(instance, "_registered_cmds", []):
        kernel.command_handlers.pop(cmd, None)
        kernel.command_owners.pop(cmd, None)

    for handle in getattr(instance, "_watcher_handles", []):
        try:
            kernel.client.remove_event_handler(handle)
        except Exception:
            pass

    for handle in getattr(instance, "_event_handles", []):
        try:
            kernel.client.remove_event_handler(handle)
        except Exception:
            pass

    kernel.loaded_modules.pop(module_name, None)

    child_pkg = f"{_FAKE_PKG_NAME}.{module_name}"
    sys.modules.pop(child_pkg, None)

    kernel.logger.info(f"[hikka_compat] Unloaded '{module_name}'")
    return True
