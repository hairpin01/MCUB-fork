import asyncio
import ast
import contextlib
import hashlib
import importlib
import importlib.util
import json
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
    _instance_owner_names,
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
    raw_handler,
    debug_method,
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


def _parse_saved_config(raw: Any) -> dict:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    if isinstance(raw, str):
        with contextlib.suppress(json.JSONDecodeError, TypeError, ValueError):
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        with contextlib.suppress(SyntaxError, ValueError):
            parsed = ast.literal_eval(raw)
            if isinstance(parsed, dict):
                return parsed
    return {}


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
    "hikka_only",
    "from .. import",
)


_GEEKG_INDICATORS = (
    "GeekInlineQuery",
    "self.inline._bot",
)


_NATIVE_MCUB_INDICATORS = (
    "def register(kernel",
    "from core.lib.loader import",
    "mcub_only",
)


def _detect_module_type(source_code: str) -> str:
    native_score = sum(ind in source_code for ind in _NATIVE_MCUB_INDICATORS)
    hikka_score = sum(ind in source_code for ind in _HIKKA_INDICATORS)
    geek_score = sum(ind in source_code for ind in _GEEKG_INDICATORS)

    if hikka_score >= 1:
        return "hikka"
    if geek_score >= 1:
        return "geek"
    if native_score >= 1:
        return "native"
    return "hikka"


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


async def _maybe_await(value):
    if asyncio.iscoroutine(value):
        return await value
    return value


def _create_main_stub(parent_pkg_name: str) -> types.ModuleType:
    main_mod = types.ModuleType(f"{parent_pkg_name}.main")
    main_mod.__file__ = "<hikka_compat main>"
    main_mod.__package__ = parent_pkg_name
    main_mod.__version__ = (1, 0, 0)
    main_mod.BASE_DIR = str(Path.cwd())
    main_mod.LATIN_MOCK = "abcdefghijklmnopqrstuvwxyz"

    class _DummyWeb:
        async def stop(self):
            return None

        async def get_url(self, proxy_pass=False):
            return None

    class _DummyHerokuState:
        def __init__(self):
            self.ready = asyncio.Event()
            self.web = _DummyWeb()
            self.arguments = types.SimpleNamespace(port=0, proxy_pass=False)
            self.api_token = types.SimpleNamespace(ID=0, HASH="")
            self.proxy = None
            self.conn = None

        async def save_client_session(self, *args, **kwargs):
            return None

    main_mod.heroku = _DummyHerokuState()

    def _get_config_key(_key, default=None):
        return default

    def _get_app_name():
        return "MCUB"

    main_mod.get_config_key = _get_config_key
    main_mod.get_app_name = _get_app_name
    return main_mod


def _create_version_stub(parent_pkg_name: str) -> types.ModuleType:
    version_mod = types.ModuleType(f"{parent_pkg_name}.version")
    version_mod.__file__ = "<hikka_compat version>"
    version_mod.__package__ = parent_pkg_name
    version_mod.__version__ = (1, 0, 0)
    version_mod.branch = "main"
    return version_mod


def _create_types_stub(parent_pkg_name: str) -> types.ModuleType:
    types_mod = types.ModuleType(f"{parent_pkg_name}.types")
    types_mod.__file__ = "<hikka_compat types>"
    types_mod.__package__ = parent_pkg_name
    exported = {
        "JSONSerializable": JSONSerializable,
        "HerokuReplyMarkup": HerokuReplyMarkup,
        "ListLike": ListLike,
        "Command": Command,
        "StringLoader": StringLoader,
        "LoadError": LoadError,
        "CoreOverwriteError": CoreOverwriteError,
        "CoreUnloadError": CoreUnloadError,
        "SelfUnload": SelfUnload,
        "SelfSuspend": SelfSuspend,
        "StopLoop": StopLoop,
        "Module": Module,
        "Library": Library,
        "InlineProxy": InlineProxy,
        "DbProxy": DbProxy,
        "get_commands": get_commands,
        "get_inline_handlers": get_inline_handlers,
        "get_callback_handlers": get_callback_handlers,
        "get_watchers": get_watchers,
    }
    for k, v in exported.items():
        setattr(types_mod, k, v)
    try:
        from . import inline_types as _inline_types

        for _name in (
            "InlineMessage",
            "BotMessage",
            "BotInlineMessage",
            "InlineCall",
            "BotInlineCall",
            "InlineQuery",
            "InlineUnit",
            "InlineResults",
        ):
            if hasattr(_inline_types, _name):
                setattr(types_mod, _name, getattr(_inline_types, _name))
    except Exception:
        pass
    return types_mod


def _create_log_stub(parent_pkg_name: str) -> types.ModuleType:
    log_mod = types.ModuleType(f"{parent_pkg_name}.log")
    log_mod.__file__ = "<hikka_compat log>"
    log_mod.__package__ = parent_pkg_name

    class HerokuException(Exception):
        @classmethod
        def from_exc_info(cls, *args, **kwargs):
            return cls("HerokuException")

    log_mod.HerokuException = HerokuException
    return log_mod


def _create_internal_stub(parent_pkg_name: str) -> types.ModuleType:
    internal_mod = types.ModuleType(f"{parent_pkg_name}._internal")
    internal_mod.__file__ = "<hikka_compat _internal>"
    internal_mod.__package__ = parent_pkg_name

    async def fw_protect(*args, **kwargs):
        return None

    async def restart(*args, **kwargs):
        return None

    internal_mod.fw_protect = fw_protect
    internal_mod.restart = restart
    return internal_mod


def _create_local_storage_stub(parent_pkg_name: str) -> types.ModuleType:
    local_storage_mod = types.ModuleType(f"{parent_pkg_name}._local_storage")
    local_storage_mod.__file__ = "<hikka_compat _local_storage>"
    local_storage_mod.__package__ = parent_pkg_name

    class RemoteStorage:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        async def fetch(self, *args, **kwargs):
            return None

        async def preload(self, *args, **kwargs):
            return None

    local_storage_mod.RemoteStorage = RemoteStorage
    return local_storage_mod


def _create_tl_cache_stub(parent_pkg_name: str) -> types.ModuleType:
    tl_cache_mod = types.ModuleType(f"{parent_pkg_name}.tl_cache")
    tl_cache_mod.__file__ = "<hikka_compat tl_cache>"
    tl_cache_mod.__package__ = parent_pkg_name

    class CustomTelegramClient:
        pass

    tl_cache_mod.CustomTelegramClient = CustomTelegramClient
    return tl_cache_mod


def _create_web_stub(parent_pkg_name: str) -> tuple[types.ModuleType, types.ModuleType]:
    web_mod = types.ModuleType(f"{parent_pkg_name}.web")
    web_mod.__file__ = "<hikka_compat web>"
    web_mod.__package__ = parent_pkg_name
    web_mod.__path__ = []

    core_mod = types.ModuleType(f"{parent_pkg_name}.web.core")
    core_mod.__file__ = "<hikka_compat web.core>"
    core_mod.__package__ = f"{parent_pkg_name}.web"

    class Web:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        async def add_loader(self, *args, **kwargs):
            return None

        async def start_if_ready(self, *args, **kwargs):
            return None

        async def stop(self):
            return None

        async def get_url(self, proxy_pass=False):
            return None

    core_mod.Web = Web
    web_mod.core = core_mod
    return web_mod, core_mod


def _ensure_herokutl_stub() -> None:
    if "herokutl" in sys.modules:
        return

    herokutl_mod = types.ModuleType("herokutl")
    herokutl_mod.__file__ = "<hikka_compat herokutl>"
    herokutl_mod.__path__ = []
    herokutl_mod.__version__ = "0.0.0"

    errors_mod = types.ModuleType("herokutl.errors")
    errors_mod.__path__ = []

    class WebpageMediaEmptyError(Exception):
        pass

    class MediaCaptionTooLongError(Exception):
        pass

    class MessageIdInvalidError(Exception):
        pass

    class YouBlockedUserError(Exception):
        pass

    class PasswordHashInvalidError(Exception):
        pass

    class PhoneCodeExpiredError(Exception):
        pass

    class PhoneCodeInvalidError(Exception):
        pass

    class PhoneNumberInvalidError(Exception):
        pass

    class SessionPasswordNeededError(Exception):
        pass

    errors_mod.WebpageMediaEmptyError = WebpageMediaEmptyError
    errors_mod.MediaCaptionTooLongError = MediaCaptionTooLongError
    errors_mod.MessageIdInvalidError = MessageIdInvalidError
    errors_mod.YouBlockedUserError = YouBlockedUserError
    errors_mod.PasswordHashInvalidError = PasswordHashInvalidError
    errors_mod.PhoneCodeExpiredError = PhoneCodeExpiredError
    errors_mod.PhoneCodeInvalidError = PhoneCodeInvalidError
    errors_mod.PhoneNumberInvalidError = PhoneNumberInvalidError
    errors_mod.SessionPasswordNeededError = SessionPasswordNeededError
    errors_mod.FloodWaitError = FloodWaitError
    errors_mod.__package__ = "herokutl"

    errors_common_mod = types.ModuleType("herokutl.errors.common")
    errors_common_mod.ScamDetectionError = ScamDetectionError

    errors_rpc_mod = types.ModuleType("herokutl.errors.rpcerrorlist")
    errors_rpc_mod.MediaCaptionTooLongError = MediaCaptionTooLongError
    errors_rpc_mod.MessageIdInvalidError = MessageIdInvalidError
    errors_rpc_mod.YouBlockedUserError = YouBlockedUserError

    extensions_mod = types.ModuleType("herokutl.extensions")
    extensions_mod.__path__ = []
    html_mod = types.ModuleType("herokutl.extensions.html")
    html_mod.CUSTOM_EMOJIS = {}
    html_mod.parse = lambda text: (text, [])
    extensions_mod.html = html_mod

    hints_mod = types.ModuleType("herokutl.hints")
    hints_mod.Entity = Any
    hints_mod.EntityLike = Any

    types_mod = types.ModuleType("herokutl.types")

    class InputMediaWebPage:
        def __init__(self, url: Optional[str] = None, **kwargs):
            self.url = url
            self.kwargs = kwargs

    try:
        from telethon.tl.types import Message as _TelethonMessage

        types_mod.Message = _TelethonMessage
    except Exception:
        pass

    types_mod.InputMediaWebPage = InputMediaWebPage

    utils_mod = types.ModuleType("herokutl.utils")

    def get_display_name(entity: Any) -> str:
        if entity is None:
            return ""
        for attr in ("first_name", "username", "name", "title"):
            value = getattr(entity, attr, None)
            if value:
                return str(value)
        return str(getattr(entity, "id", ""))

    utils_mod.get_display_name = get_display_name
    utils_mod.sanitize_parse_mode = lambda mode: mode
    utils_mod.parse_phone = lambda phone: str(phone).strip().replace(" ", "")
    utils_mod.is_list_like = lambda value: isinstance(value, (list, tuple, set))

    sessions_mod = types.ModuleType("herokutl.sessions")

    class MemorySession:
        pass

    class StringSession:
        def __init__(self, session: str = ""):
            self.session = session

    sessions_mod.MemorySession = MemorySession
    sessions_mod.StringSession = StringSession

    tl_mod = types.ModuleType("herokutl.tl")
    tl_mod.__path__ = []

    tl_types = types.ModuleType("herokutl.tl.types")

    class _Base:
        def __init__(self, *args, **kwargs):
            self.__dict__.update(kwargs)

    class TLObject(_Base):
        pass

    class TLRequest(TLObject):
        CONSTRUCTOR_ID = 0

    def _request_type(name: str, constructor_id: int):
        return type(name, (TLRequest,), {"CONSTRUCTOR_ID": constructor_id})

    for _name in (
        "Message",
        "Channel",
        "User",
        "TextWithEntities",
        "DialogFilter",
        "PeerUser",
        "PeerChat",
        "PeerChannel",
        "ForumTopic",
        "ForumTopicDeleted",
        "InputPeerNotifySettings",
        "UpdateNewChannelMessage",
        "DialogFilterDefault",
        "ChatParticipantAdmin",
        "ChatParticipantCreator",
    ):
        tl_types.__dict__[_name] = type(_name, (_Base,), {})

    tl_custom_mod = types.ModuleType("herokutl.tl.custom")
    tl_custom_mod.__path__ = []
    tl_custom_message_mod = types.ModuleType("herokutl.tl.custom.message")
    tl_custom_message_mod.Message = tl_types.Message
    tl_custom_mod.message = tl_custom_message_mod
    tl_custom_mod.Message = tl_types.Message

    custom_mod = types.ModuleType("herokutl.custom")
    custom_mod.Message = tl_types.Message

    tl_functions = types.ModuleType("herokutl.tl.functions")
    tl_functions.__path__ = []
    tl_func_channels = types.ModuleType("herokutl.tl.functions.channels")
    tl_func_contacts = types.ModuleType("herokutl.tl.functions.contacts")
    tl_func_messages = types.ModuleType("herokutl.tl.functions.messages")
    tl_func_account = types.ModuleType("herokutl.tl.functions.account")
    tl_tlobject_mod = types.ModuleType("herokutl.tl.tlobject")
    tl_tlobject_mod.TLObject = TLObject
    tl_tlobject_mod.TLRequest = TLRequest

    for _name in (
        "ToggleForumRequest",
        "JoinChannelRequest",
        "CreateChannelRequest",
        "EditPhotoRequest",
    ):
        tl_func_channels.__dict__[_name] = _request_type(
            _name,
            abs(hash(f"channels.{_name}")) % (2**31),
        )

    for _name in (
        "CreateForumTopicRequest",
        "EditForumTopicRequest",
        "GetDialogFiltersRequest",
        "GetForumTopicsByIDRequest",
        "GetForumTopicsRequest",
        "SetHistoryTTLRequest",
        "UpdateDialogFilterRequest",
        "GetFullChatRequest",
        "ImportChatInviteRequest",
        "SendReactionRequest",
    ):
        tl_func_messages.__dict__[_name] = _request_type(
            _name,
            abs(hash(f"messages.{_name}")) % (2**31),
        )

    tl_func_contacts.UnblockRequest = _request_type(
        "UnblockRequest",
        abs(hash("contacts.UnblockRequest")) % (2**31),
    )

    tl_func_account.UpdateNotifySettingsRequest = _request_type(
        "UpdateNotifySettingsRequest",
        abs(hash("account.UpdateNotifySettingsRequest")) % (2**31),
    )

    tl_functions.channels = tl_func_channels
    tl_functions.contacts = tl_func_contacts
    tl_functions.messages = tl_func_messages
    tl_functions.account = tl_func_account
    for _group_name in (
        "auth",
        "users",
        "updates",
        "photos",
        "upload",
        "help",
        "bots",
        "payments",
        "stickers",
        "phone",
        "langpack",
        "folders",
        "stats",
    ):
        _group_mod = types.ModuleType(f"herokutl.tl.functions.{_group_name}")
        setattr(tl_functions, _group_name, _group_mod)

    herokutl_mod.errors = errors_mod
    herokutl_mod.extensions = extensions_mod
    herokutl_mod.hints = hints_mod
    herokutl_mod.types = types_mod
    herokutl_mod.utils = utils_mod
    herokutl_mod.sessions = sessions_mod
    herokutl_mod.tl = tl_mod
    herokutl_mod.custom = custom_mod
    tl_mod.types = tl_types
    tl_mod.functions = tl_functions
    tl_mod.custom = tl_custom_mod

    sys.modules["herokutl"] = herokutl_mod
    sys.modules["herokutl.errors"] = errors_mod
    sys.modules["herokutl.errors.common"] = errors_common_mod
    sys.modules["herokutl.errors.rpcerrorlist"] = errors_rpc_mod
    sys.modules["herokutl.extensions"] = extensions_mod
    sys.modules["herokutl.extensions.html"] = html_mod
    sys.modules["herokutl.hints"] = hints_mod
    sys.modules["herokutl.types"] = types_mod
    sys.modules["herokutl.utils"] = utils_mod
    sys.modules["herokutl.sessions"] = sessions_mod
    sys.modules["herokutl.tl"] = tl_mod
    sys.modules["herokutl.tl.types"] = tl_types
    sys.modules["herokutl.tl.functions"] = tl_functions
    sys.modules["herokutl.tl.functions.channels"] = tl_func_channels
    sys.modules["herokutl.tl.functions.contacts"] = tl_func_contacts
    sys.modules["herokutl.tl.functions.messages"] = tl_func_messages
    sys.modules["herokutl.tl.functions.account"] = tl_func_account
    sys.modules["herokutl.tl.custom"] = tl_custom_mod
    sys.modules["herokutl.tl.custom.message"] = tl_custom_message_mod
    sys.modules["herokutl.tl.tlobject"] = tl_tlobject_mod
    sys.modules["herokutl.custom"] = custom_mod


def _create_compat_stub(
    parent_pkg_name: str,
) -> tuple[types.ModuleType, types.ModuleType]:
    compat_mod = types.ModuleType(f"{parent_pkg_name}.compat")
    compat_mod.__file__ = "<hikka_compat compat>"
    compat_mod.__package__ = parent_pkg_name
    compat_mod.__path__ = []

    geek_mod = types.ModuleType(f"{parent_pkg_name}.compat.geek")
    geek_mod.__file__ = "<hikka_compat geek>"
    geek_mod.__package__ = f"{parent_pkg_name}.compat"
    geek_mod.compat = lambda source: source
    compat_mod.geek = geek_mod
    return compat_mod, geek_mod


def _install_extended_submodules(
    parent_pkg_name: str,
    parent_mod: types.ModuleType,
) -> None:
    main_mod = _create_main_stub(parent_pkg_name)
    version_mod = _create_version_stub(parent_pkg_name)
    types_mod = _create_types_stub(parent_pkg_name)
    log_mod = _create_log_stub(parent_pkg_name)
    internal_mod = _create_internal_stub(parent_pkg_name)
    local_storage_mod = _create_local_storage_stub(parent_pkg_name)
    compat_mod, geek_mod = _create_compat_stub(parent_pkg_name)
    tl_cache_mod = _create_tl_cache_stub(parent_pkg_name)
    web_mod, web_core_mod = _create_web_stub(parent_pkg_name)

    parent_mod.main = main_mod
    parent_mod.version = version_mod
    parent_mod.types = types_mod
    parent_mod.log = log_mod
    parent_mod._internal = internal_mod
    parent_mod._local_storage = local_storage_mod
    parent_mod.compat = compat_mod
    parent_mod.tl_cache = tl_cache_mod
    parent_mod.web = web_mod

    sys.modules[f"{parent_pkg_name}.main"] = main_mod
    sys.modules[f"{parent_pkg_name}.version"] = version_mod
    sys.modules[f"{parent_pkg_name}.types"] = types_mod
    sys.modules[f"{parent_pkg_name}.log"] = log_mod
    sys.modules[f"{parent_pkg_name}._internal"] = internal_mod
    sys.modules[f"{parent_pkg_name}._local_storage"] = local_storage_mod
    sys.modules[f"{parent_pkg_name}.compat"] = compat_mod
    sys.modules[f"{parent_pkg_name}.compat.geek"] = geek_mod
    sys.modules[f"{parent_pkg_name}.tl_cache"] = tl_cache_mod
    sys.modules[f"{parent_pkg_name}.web"] = web_mod
    sys.modules[f"{parent_pkg_name}.web.core"] = web_core_mod


def _ensure_fake_package() -> str:
    _ensure_herokutl_stub()
    if not any(isinstance(f, _HikkaCompatFinder) for f in sys.meta_path):
        sys.meta_path.insert(0, _HikkaCompatFinder())

    if _FAKE_PKG_NAME in sys.modules:
        parent_mod = sys.modules[_FAKE_PKG_NAME]
        loader_mod = sys.modules.get(f"{_FAKE_PKG_NAME}.loader")
        if loader_mod is not None:
            loader_mod.command = command
            loader_mod.watcher = watcher
            loader_mod.on = on
            loader_mod.tag = tag
            loader_mod.loop = loop
            loader_mod.raw_handler = raw_handler
            loader_mod.debug_method = debug_method
            loader_mod.inline_handler = inline_handler
            loader_mod.callback_handler = callback_handler
            if not hasattr(loader_mod, "get_module_hash"):
                loader_mod.get_module_hash = lambda mod: hashlib.sha1(
                    (
                        getattr(mod, "__origin__", "")
                        or f"{mod.__class__.__module__}:{mod.__class__.__name__}"
                    ).encode("utf-8", errors="replace")
                ).hexdigest()[:12]
            if not hasattr(loader_mod, "set_session_access_hashes"):
                loader_mod.set_session_access_hashes = lambda values: True
        _install_extended_submodules(_FAKE_PKG_NAME, parent_mod)
        return _FAKE_PKG_NAME

    parent = types.ModuleType(_FAKE_PKG_NAME)
    parent.__path__ = []
    parent.__package__ = _FAKE_PKG_NAME
    parent.__spec__ = importlib.util.spec_from_loader(_FAKE_PKG_NAME, loader=None)

    class _ProxyWrapper:
        def __init__(self, target, *args, **kwargs):
            self._origin = args[0] if args else kwargs.get("origin")
            self._target = target
            self._module_object = None
            self._inline_object = None
            self._user_id = None

        def __getattr__(self, name: str):
            return getattr(self._target, name)

        def __call__(self, *args, **kwargs):
            return self._target(*args, **kwargs)

        def _set_module_info(self, module_object, inline_object, user_id: int):
            self._module_object = module_object
            self._inline_object = inline_object
            self._user_id = user_id
            return self

    class _SafeAllModulesProxy(_ProxyWrapper):
        def __init__(
            self,
            real_allmodules,
            safe_client=None,
            safe_allclients=None,
            safe_db=None,
            safe_inline=None,
        ):
            super().__init__(real_allmodules)
            self.client = safe_client or real_allmodules.client
            self.allclients = safe_allclients or real_allmodules.allclients
            self.db = safe_db or real_allmodules.db
            self.inline = safe_inline or real_allmodules.inline

        def _get_real_allmodules(self):
            return self._target

    def _get_module_hash(mod) -> str:
        base = (
            getattr(mod, "__origin__", "")
            or f"{mod.__class__.__module__}:{mod.__class__.__name__}"
        )
        return hashlib.sha1(base.encode("utf-8", errors="replace")).hexdigest()[:12]

    _session_access_hashes: set[str] = set()

    def _set_session_access_hashes(values):
        _session_access_hashes.clear()
        _session_access_hashes.update(map(str, values or []))
        return True

    try:
        from core.lib.loader.module_config import (
            ModuleConfig as _MCUBModuleConfig,
            ConfigValue as _MCUBConfigValue,
            Validator as _MCUBValidator,
        )

        class _HikkaCompatibleConfigValue:
            def __init__(
                self,
                option: str,
                default=None,
                doc: Any = None,
                description: Any = None,
                validator: Any = None,
                on_change: Any = None,
            ):
                self.option = option
                self.default = default
                self._doc_raw = doc if doc is not None else description
                self.validator = validator or _MCUBValidator()
                self.on_change = on_change
                self._value = None
                self.hidden = getattr(validator, "hidden", False)
                self._config_value = _MCUBConfigValue(
                    key=option,
                    default=default,
                    validator=self.validator,
                    description=doc or description or "",
                    on_change=on_change,
                )

            @property
            def value(self):
                return self._config_value.get_value()

            @value.setter
            def value(self, val):
                self._config_value.set_value(val)

            @property
            def doc(self):
                return self._config_value.description

            @property
            def description(self):
                return self.doc

            @property
            def is_secret(self):
                return getattr(self.validator, "secret", False)

            def set_no_raise(self, value, *, mark=True):
                self._config_value.set_value(value)

        class _HikkaCompatibleModuleConfig(dict):
            _is_hikka_compat = True

            def __init__(self, *entries, db=None, module_name=None):
                self._config = {}
                self._values = self._config
                self._db = db
                self._module_name = module_name

                if entries and all(
                    isinstance(entry, (_HikkaCompatibleConfigValue, ConfigValue))
                    for entry in entries
                ):
                    for entry in entries:
                        if isinstance(entry, ConfigValue) and not isinstance(
                            entry, _HikkaCompatibleConfigValue
                        ):
                            entry = self._convert_config_value(entry)
                        self._config[entry.option] = entry
                else:
                    keys, defaults, docs = [], [], []
                    for index, entry in enumerate(entries):
                        if index % 3 == 0:
                            keys.append(entry)
                        elif index % 3 == 1:
                            defaults.append(entry)
                        else:
                            docs.append(entry)

                    for key, default, doc in zip(keys, defaults, docs):
                        cv = _HikkaCompatibleConfigValue(
                            option=key,
                            default=default,
                            doc=doc,
                        )
                        self._config[key] = cv

                super().__init__(
                    {option: config.value for option, config in self._config.items()}
                )

            def _convert_config_value(
                self, cv: ConfigValue
            ) -> _HikkaCompatibleConfigValue:
                return _HikkaCompatibleConfigValue(
                    option=cv.option,
                    default=cv.default,
                    doc=cv._doc_raw,
                    description=cv._doc_raw,
                    validator=cv.validator,
                    on_change=cv.on_change,
                )

            def __getitem__(self, key: str) -> Any:
                if key not in self._config:
                    return None
                return self._config[key].value

            def __setitem__(self, key: str, value: Any) -> None:
                if key not in self._config:
                    raise KeyError(key)
                self._config[key].value = value
                super().__setitem__(key, self._config[key].value)
                if self._db and self._module_name:
                    self._save_config()

            def __contains__(self, key: object) -> bool:
                return key in self._config

            def __iter__(self):
                return iter(self._config)

            def __len__(self) -> int:
                return len(self._config)

            def get(self, key: str, default: Any = None) -> Any:
                if key not in self._config:
                    return default
                value = self._config[key].value
                return default if value is None else value

            def keys(self):
                return self._config.keys()

            def values(self):
                return [config.value for config in self._config.values()]

            def items(self):
                return [(key, config.value) for key, config in self._config.items()]

            def getdoc(self, key: str, message=None) -> Any:
                if key not in self._config:
                    return ""
                result = self._config[key].doc
                if callable(result):
                    try:
                        result = result(message)
                    except TypeError:
                        result = result()
                return result or ""

            def getdef(self, key: str) -> Any:
                return self._config[key].default if key in self._config else None

            def set_no_raise(self, key: str, value: Any, *, mark: bool = True) -> None:
                if key not in self._config:
                    return
                self._config[key].set_no_raise(value, mark=mark)
                super().__setitem__(key, self._config[key].value)
                if self._db and self._module_name:
                    self._save_config()

            def _save_config(self):
                if not self._db or not self._module_name:
                    return
                try:
                    import asyncio

                    data = {
                        key: cv._config_value.to_storage()
                        for key, cv in self._config.items()
                    }

                    async def _save():
                        await self._db.set(self._module_name, "__config__", data)

                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.ensure_future(_save())
                        else:
                            loop.run_until_complete(_save())
                    except Exception:
                        pass
                except Exception:
                    pass

            def reload(self) -> None:
                for key, config in self._config.items():
                    super().__setitem__(key, config.value)

            def to_dict(self) -> dict:
                result = {key: config.value for key, config in self._config.items()}
                result["__mcub_config__"] = True
                return result

            def load_from_dict(self, data: dict) -> None:
                for key, value in data.items():
                    if key not in self._config:
                        continue
                    self.set_no_raise(key, value, mark=False)

            @property
            def schema(self) -> list[dict]:
                return [
                    {
                        "key": config.option,
                        "default": config.default,
                        "description": config.doc,
                        "secret": config.is_secret,
                        "type": getattr(
                            config.validator, "internal_id", "string"
                        ).lower(),
                    }
                    for config in self._config.values()
                ]

        loader_mod = types.ModuleType(f"{_FAKE_PKG_NAME}.loader")
        loader_mod.Module = Module
        loader_mod.Library = Library
        loader_mod.ModuleConfig = _HikkaCompatibleModuleConfig
        loader_mod.LibraryConfig = _HikkaCompatibleModuleConfig
        loader_mod.ConfigValue = _HikkaCompatibleConfigValue

        from core.lib.loader import validators as _mcub_validators

        loader_mod.validators = _mcub_validators
    except Exception:
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
    loader_mod.raw_handler = raw_handler
    loader_mod.debug_method = debug_method
    loader_mod.InfiniteLoop = InfiniteLoop
    loader_mod.Placeholder = Placeholder
    loader_mod.Modules = _AllModulesStub
    loader_mod.SafeAllModulesProxy = _SafeAllModulesProxy
    loader_mod.SafeClientProxy = _ProxyWrapper
    loader_mod.SafeDatabaseProxy = _ProxyWrapper
    loader_mod.SafeInlineProxy = _ProxyWrapper
    loader_mod.LOADED_MODULES_DIR = "modules_loaded"
    loader_mod.LOADED_MODULES_PATH = Path("modules_loaded")
    loader_mod.set_session_access_hashes = _set_session_access_hashes
    loader_mod.get_module_hash = _get_module_hash

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
    for _attr_name in dir(_Utils):
        if _attr_name.startswith("_"):
            continue
        setattr(utils_mod, _attr_name, getattr(_Utils, _attr_name))
    utils_mod.BASEDIR = ""
    utils_mod.USERS_DIR = ""
    utils_mod.DOWNLOADS_DIR = ""

    security._security_mod.__name__ = f"{_FAKE_PKG_NAME}.security"
    translations._translations_mod.__name__ = f"{_FAKE_PKG_NAME}.translations"
    translations._translations_mod.SUPPORTED_LANGUAGES = {
        "en": "🇬🇧 English",
        "ru": "🇷🇺 Русский",
        "ua": "🇺🇦 Український",
        "de": "🇩🇪 Deutsch",
        "jp": "🇯🇵 日本語",
    }
    translations._translations_mod.MEME_LANGUAGES = {
        "leet": "🏴‍☠️ 1337",
        "uwu": "🏴‍☠️ UwU",
        "tiktok": "🏴‍☠️ TikTokKid",
        "neofit": "🏴‍☠️ Neofit",
    }
    translations._translations_mod.translator = _translator_stub
    translations._translations_mod.Strings = _StringsShim

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
    _install_extended_submodules(_FAKE_PKG_NAME, parent)

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


def _normalize_watcher_tags(method: Callable) -> dict:
    tags = dict(getattr(method, "__watcher_kwargs__", {}) or {})
    for tag_name in getattr(method, "__watcher_tags__", ()) or ():
        if isinstance(tag_name, str):
            tags.setdefault(tag_name, True)

    if tags.pop("in", False):
        tags["incoming"] = True

    aliases = {
        "no_commands": "no_commands",
        "only_commands": "only_commands",
        "out": "out",
        "incoming": "incoming",
        "only_pm": "only_pm",
        "no_pm": "no_pm",
        "only_groups": "only_groups",
        "no_groups": "no_groups",
        "only_channels": "only_channels",
        "no_channels": "no_channels",
        "only_media": "only_media",
        "no_media": "no_media",
        "only_photos": "only_photos",
        "no_photos": "no_photos",
        "only_videos": "only_videos",
        "no_videos": "no_videos",
        "only_audios": "only_audios",
        "no_audios": "no_audios",
        "only_docs": "only_docs",
        "no_docs": "no_docs",
        "only_stickers": "only_stickers",
        "no_stickers": "no_stickers",
        "only_forwards": "only_forwards",
        "no_forwards": "no_forwards",
        "only_reply": "only_reply",
        "no_reply": "no_reply",
        "only_inline": "only_inline",
        "no_inline": "no_inline",
        "startswith": "startswith",
        "endswith": "endswith",
        "contains": "contains",
        "regex": "regex",
        "from_id": "from_id",
        "chat_id": "chat_id",
        "filter": "filter",
    }
    normalized = {}
    for key, value in tags.items():
        mapped = aliases.get(key)
        if mapped:
            normalized[mapped] = value
    return normalized


def _watcher_passes_filters(event: Any, tags: dict, kernel) -> bool:
    msg = getattr(event, "message", event)
    text = getattr(msg, "raw_text", None) or getattr(msg, "text", "") or ""
    prefix = getattr(kernel, "custom_prefix", ".")

    if tags.get("out") and not getattr(msg, "out", False):
        return False
    if tags.get("incoming") and getattr(msg, "out", False):
        return False

    chat = getattr(event, "chat", None)
    is_pm = False
    is_group = False
    is_channel = False
    if chat is not None:
        is_group = bool(
            getattr(chat, "megagroup", False) or getattr(chat, "gigagroup", False)
        )
        is_channel = bool(getattr(chat, "broadcast", False))
        is_pm = not is_group and not is_channel
    else:
        is_pm = bool(getattr(event, "is_private", False))
        is_group = bool(getattr(event, "is_group", False))
        is_channel = bool(getattr(event, "is_channel", False))

    if tags.get("only_pm") and not is_pm:
        return False
    if tags.get("no_pm") and is_pm:
        return False
    if tags.get("only_groups") and not is_group:
        return False
    if tags.get("no_groups") and is_group:
        return False
    if tags.get("only_channels") and not is_channel:
        return False
    if tags.get("no_channels") and is_channel:
        return False

    media = getattr(msg, "media", None)
    if tags.get("only_media") and not media:
        return False
    if tags.get("no_media") and media:
        return False

    photo = bool(getattr(msg, "photo", None))
    video = bool(getattr(msg, "video", None))
    document = bool(getattr(msg, "document", None))
    sticker = bool(getattr(msg, "sticker", None))
    audio = bool(getattr(msg, "audio", None))

    if tags.get("only_photos") and not photo:
        return False
    if tags.get("no_photos") and photo:
        return False
    if tags.get("only_videos") and not video:
        return False
    if tags.get("no_videos") and video:
        return False
    if tags.get("only_docs") and not document:
        return False
    if tags.get("no_docs") and document:
        return False
    if tags.get("only_stickers") and not sticker:
        return False
    if tags.get("no_stickers") and sticker:
        return False
    if tags.get("only_audios") and not audio:
        return False
    if tags.get("no_audios") and audio:
        return False

    fwd = getattr(msg, "fwd_from", None)
    reply = getattr(msg, "reply_to", None) or getattr(msg, "reply_to_msg_id", None)
    if tags.get("only_forwards") and not fwd:
        return False
    if tags.get("no_forwards") and fwd:
        return False
    if tags.get("only_reply") and not reply:
        return False
    if tags.get("no_reply") and reply:
        return False

    if tags.get("only_inline") and not getattr(msg, "via_bot_id", None):
        return False
    if tags.get("no_inline") and getattr(msg, "via_bot_id", None):
        return False
    if tags.get("no_commands") and text.startswith(prefix):
        return False
    if tags.get("only_commands") and not text.startswith(prefix):
        return False

    if "startswith" in tags and not text.startswith(str(tags["startswith"])):
        return False
    if "endswith" in tags and not text.endswith(str(tags["endswith"])):
        return False
    if "contains" in tags and str(tags["contains"]) not in text:
        return False
    if "regex" in tags:
        try:
            if not re.search(str(tags["regex"]), text):
                return False
        except re.error:
            return False

    if "from_id" in tags and getattr(event, "sender_id", None) != tags["from_id"]:
        return False
    if "chat_id" in tags and getattr(event, "chat_id", None) != tags["chat_id"]:
        return False

    custom_filter = tags.get("filter")
    if callable(custom_filter):
        try:
            return bool(custom_filter(event))
        except Exception:
            return False

    return True


async def load_hikka_module(
    kernel,
    file_path: str,
    module_name: str,
) -> tuple[bool, str, dict]:
    from . import geek as _geek_compat
    from . import inline_types

    pkg_name = _ensure_fake_package()
    child_pkg = f"{pkg_name}.{module_name}"

    inline_mod = types.ModuleType("inline")
    inline_types_mod = types.ModuleType("inline.types")
    for _name in ("InlineCall", "BotInlineCall", "InlineMessage", "BotMessage"):
        if hasattr(inline_types, _name):
            setattr(inline_types_mod, _name, getattr(inline_types, _name))
    inline_mod.types = inline_types_mod
    sys.modules["inline"] = inline_mod
    sys.modules["inline.types"] = inline_types_mod

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
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
                if proc.returncode == 0:
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

    instance._mcub_bind(kernel, module_type)

    db_proxy = getattr(instance, "db", None)
    if db_proxy is not None and getattr(kernel, "db_manager", None):
        for owner in _instance_owner_names(instance, module_name):
            try:
                keys = await kernel.db_manager.db_get_module_keys(owner)
            except Exception:
                continue
            for key in keys:
                with contextlib.suppress(Exception):
                    value = await kernel.db_get(owner, key)
                    db_proxy._mem[db_proxy._mem_key(owner, key)] = value
                    canonical_owner = getattr(instance, "_db_owner", None)
                    if (
                        canonical_owner
                        and db_proxy._mem_key(canonical_owner, key) not in db_proxy._mem
                    ):
                        db_proxy._mem[db_proxy._mem_key(canonical_owner, key)] = value

    if hasattr(instance, "config") and (
        isinstance(instance.config, ModuleConfig)
        or getattr(instance.config, "_is_hikka_compat", False)
        or hasattr(instance.config, "_config")
    ):
        try:
            saved = {}
            for owner in _instance_owner_names(instance, module_name):
                legacy_raw = await kernel.db_get(owner, "__config__")
                saved.update(_parse_saved_config(legacy_raw))
            saved.update(
                _parse_saved_config(await kernel.get_module_config(module_name))
            )
            if saved:
                instance.config.load_from_dict(saved)
            elif hasattr(kernel, "save_module_config"):
                await kernel.save_module_config(module_name, instance.config.to_dict())

            if hasattr(instance.config, "_save_config"):
                db_proxy = getattr(instance, "db", None)
                instance.config._db = db_proxy
                instance.config._module_name = module_name

            if hasattr(kernel, "store_module_config_schema"):
                kernel.store_module_config_schema(module_name, instance.config)
        except Exception:
            pass

    registered_cmds: list[str] = []
    registered_aliases: list[str] = []
    conflicts: list[dict] = []
    event_handles: list = []
    watcher_handles: list = []
    callback_event_handles: list = []
    raw_handles: list = []
    inline_patterns: list[str] = []
    loop_handles: list[InfiniteLoop] = []

    if not kernel.current_loading_module:
        kernel.set_loading_module(module_name, "hikka")

    def _register_alias(alias_name: str, target_cmd: str) -> None:
        alias_name = str(alias_name).strip()
        if not alias_name:
            return
        if alias_name in kernel.command_handlers:
            raise ValueError(
                f"Alias '{alias_name}' conflicts with existing command '{alias_name}'"
            )
        kernel.aliases[alias_name] = target_cmd
        registered_aliases.append(alias_name)

    for attr_name in dir(cls):
        method = getattr(instance, attr_name, None)
        if isinstance(method, dict) or not callable(method):
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
                        from .inline_types import CompatMessage

                        wrapped_event = (
                            CompatMessage(event) if hasattr(event, "edit") else event
                        )
                        await _m(wrapped_event)
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
            from .inline_types import CompatMessage

            async def _wrapped_handler(event, _method=method):
                from .inline_types import CompatMessage

                wrapped_event = (
                    CompatMessage(event) if hasattr(event, "edit") else event
                )
                return await _maybe_await(_method(wrapped_event))

            _wrapped_handler._original = method
            kernel.register_command(cmd_name, _wrapped_handler)
            registered_cmds.append(cmd_name)
            alias = getattr(method, "alias", None)
            if alias:
                _register_alias(str(alias), cmd_name)
            aliases = getattr(method, "aliases", None)
            if isinstance(aliases, (list, tuple, set)):
                for item in aliases:
                    _register_alias(str(item), cmd_name)
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

    try:
        for inline_pattern, inline_method in get_inline_handlers(instance).items():
            kernel.register_inline_handler(inline_pattern, inline_method)
            inline_patterns.append(inline_pattern)
    except Exception as e:
        kernel.logger.warning(
            f"[hikka_compat] inline handler registration warning in {module_name}: {e}"
        )

    callback_map = dict(get_callback_handlers(instance))
    if callback_map:
        from telethon import events as _tl_events

        @kernel.client.on(_tl_events.CallbackQuery())
        async def _callback_bridge(
            event, _handlers=list(callback_map.values()), _mn=module_name
        ):
            if not getattr(instance, "_hikka_compat_ready", False):
                return

            from .inline_types import InlineCall, BotInlineCall

            inline_proxy = getattr(instance, "inline", None)
            is_bot_message = (
                getattr(getattr(event, "message", None), "chat", None) is not None
            )
            call_obj = (
                BotInlineCall(
                    event,
                    inline_proxy=inline_proxy,
                    unit_id="",
                )
                if is_bot_message
                else InlineCall(
                    event.data.decode() if event.data else "",
                    unit_id="",
                    inline_proxy=inline_proxy,
                    original_call=event,
                    inline_message_id=getattr(event, "inline_message_id", None),
                    chat_id=getattr(event, "chat_instance", None),
                    message_id=getattr(event, "message_id", None),
                    from_user_id=getattr(getattr(event, "from_user", None), "id", None),
                )
            )

            for _handler in _handlers:
                try:
                    from .inline_types import CompatMessage

                    if hasattr(call_obj, "message") and call_obj.message is not None:
                        orig_msg = getattr(call_obj.message, "_message", None)
                        if orig_msg is not None:
                            call_obj.message = CompatMessage(orig_msg)
                    await _maybe_await(_handler(call_obj))
                except Exception as _e:
                    kernel.logger.error(
                        f"[hikka_compat] callback handler error in {_mn}: {_e}"
                    )

        callback_event_handles.append(_callback_bridge)

    watcher_map = dict(get_watchers(instance))
    if watcher_map:
        from telethon import events as _tl_events

        for _watcher_name, _watcher_method in watcher_map.items():
            _tags = _normalize_watcher_tags(_watcher_method)

            @kernel.client.on(_tl_events.NewMessage())
            async def _watcher_bridge(
                event,
                _wm=_watcher_method,
                _tags=_tags,
                _mn=module_name,
            ):
                if not getattr(instance, "_hikka_compat_ready", False):
                    return
                if not _watcher_passes_filters(event, _tags, kernel):
                    return
                try:
                    from .inline_types import CompatMessage

                    wrapped_event = (
                        CompatMessage(event) if hasattr(event, "edit") else event
                    )
                    await _maybe_await(_wm(wrapped_event))
                except Exception as _e:
                    kernel.logger.error(f"[hikka_compat] watcher error in {_mn}: {_e}")

            watcher_handles.append(_watcher_bridge)

    from telethon import events as _tl_events

    for _attr_name in dir(instance):
        _raw_method = getattr(instance, _attr_name, None)
        if not callable(_raw_method) or not getattr(
            _raw_method, "is_raw_handler", False
        ):
            continue

        _updates = tuple(getattr(_raw_method, "updates", ()) or ())
        _raw_event = _tl_events.Raw(types=_updates if _updates else None)

        @kernel.client.on(_raw_event)
        async def _raw_bridge(event, _rm=_raw_method, _mn=module_name):
            if not getattr(instance, "_hikka_compat_ready", False):
                return
            try:
                await _maybe_await(_rm(event))
            except Exception as _e:
                kernel.logger.error(f"[hikka_compat] raw handler error in {_mn}: {_e}")

        raw_handles.append(_raw_bridge)

    for _attr_name in dir(instance):
        _loop_obj = getattr(instance, _attr_name, None)
        if isinstance(_loop_obj, InfiniteLoop):
            _loop_obj.module_instance = instance
            loop_handles.append(_loop_obj)

    instance._hikka_compat = True
    instance._hikka_compat_ready = False
    instance._registered_cmds = registered_cmds
    instance._registered_aliases = registered_aliases
    instance._inline_patterns = inline_patterns
    instance._callback_event_handles = callback_event_handles
    instance._watcher_handles = watcher_handles
    instance._raw_handles = raw_handles
    instance._loop_handles = loop_handles
    instance._event_handles = event_handles
    kernel.loaded_modules[module_name] = instance

    if hasattr(instance, "config_complete") and callable(instance.config_complete):
        try:
            await _maybe_await(instance.config_complete())
        except Exception as e:
            kernel.logger.warning(
                f"[hikka_compat] config_complete() error in {module_name}: {e}"
            )

    try:
        await _maybe_await(instance.on_load())
    except SelfUnload as e:
        kernel.logger.info(
            f"[hikka_compat] {module_name} self-unloaded on on_load: {e}"
        )
        await unload_hikka_module(kernel, module_name)
        kernel.clear_loading_module()
        return (
            False,
            str(e) or "SelfUnload",
            {"registered": registered_cmds, "conflicts": conflicts},
        )
    except Exception as e:
        kernel.logger.warning(f"[hikka_compat] on_load() error in {module_name}: {e}")

    if hasattr(instance, "client_ready") and callable(instance.client_ready):
        try:
            await _maybe_await(instance.client_ready(kernel.client, instance.db))
            instance._hikka_compat_ready = True
        except TypeError:
            try:
                await _maybe_await(instance.client_ready())
                instance._hikka_compat_ready = True
            except Exception as e:
                kernel.logger.warning(
                    f"[hikka_compat] client_ready() error in {module_name}: {e}"
                )
        except SelfUnload as e:
            kernel.logger.info(
                f"[hikka_compat] {module_name} self-unloaded on client_ready: {e}"
            )
            await unload_hikka_module(kernel, module_name)
            kernel.clear_loading_module()
            return (
                False,
                str(e) or "SelfUnload",
                {"registered": registered_cmds, "conflicts": conflicts},
            )
        except SelfSuspend as e:
            instance._self_suspended = True
            kernel.logger.info(
                f"[hikka_compat] {module_name} suspended on client_ready: {e}"
            )
        except Exception as e:
            kernel.logger.warning(
                f"[hikka_compat] client_ready() error in {module_name}: {e}"
            )
    else:
        instance._hikka_compat_ready = True

    for _loop_obj in loop_handles:
        if getattr(_loop_obj, "autostart", False):
            try:
                _loop_obj.start()
            except Exception as e:
                kernel.logger.warning(
                    f"[hikka_compat] loop autostart failed in {module_name}: {e}"
                )

    kernel.clear_loading_module()

    kernel.logger.info(
        f"[hikka_compat] Loaded '{module_name}' "
        f"({cls.__name__}) — commands: {registered_cmds}"
    )
    return True, "", {"registered": registered_cmds, "conflicts": conflicts}


async def unload_hikka_module(kernel, module_name: str) -> bool:
    actual_name = None
    for key in kernel.loaded_modules:
        if key.lower() == module_name.lower():
            actual_name = key
            break

    if actual_name is None:
        return False

    instance = kernel.loaded_modules.get(actual_name)
    if instance is None or not getattr(instance, "_hikka_compat", False):
        return False

    module_name = actual_name

    try:
        await instance.on_unload()
    except Exception as e:
        kernel.logger.warning(f"[hikka_compat] on_unload() error in {module_name}: {e}")

    for cmd in getattr(instance, "_registered_cmds", []):
        kernel.command_handlers.pop(cmd, None)
        kernel.command_owners.pop(cmd, None)

    for alias in getattr(instance, "_registered_aliases", []):
        kernel.aliases.pop(alias, None)

    for pattern in getattr(instance, "_inline_patterns", []):
        kernel.inline_handlers.pop(pattern, None)
        kernel.inline_handlers_owners.pop(pattern, None)

    for loop_obj in getattr(instance, "_loop_handles", []):
        try:
            await _maybe_await(loop_obj.stop())
        except Exception:
            pass

    for handle in getattr(instance, "_callback_event_handles", []):
        try:
            kernel.client.remove_event_handler(handle)
        except Exception:
            pass

    for handle in getattr(instance, "_watcher_handles", []):
        try:
            kernel.client.remove_event_handler(handle)
        except Exception:
            pass

    for handle in getattr(instance, "_raw_handles", []):
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
