# Module Config API

← [Index](../../API_DOC.md)

MCUB provides two ways to configure modules: a simple dict-based API and a structured **ModuleConfig** system (recommended). Both are backed by the database and persist across restarts.

## Simple Dict API

`kernel.get_module_config(module_name, default=None)` - Retrieve the full config dict for a module.

`kernel.save_module_config(module_name, config_data)` - Save the full config dict for a module.

`kernel.get_module_config_key(module_name, key, default=None)` - Retrieve a single key from the module config.

`kernel.set_module_config_key(module_name, key, value)` - Set a single key in the module config without overwriting other keys.

`kernel.delete_module_config_key(module_name, key)` - Remove a single key from the module config.

`kernel.update_module_config(module_name, updates)` - Merge a dict of updates into the module config (shallow merge).

`kernel.delete_module_config(module_name)` - Delete the entire config for a module.

`kernel.store_module_config_schema(module_name, config)` - **REQUIRED for UI!** Store a live ModuleConfig schema for the UI.

---

## ModuleConfig (Recommended)

The recommended way to create module configuration. Provides:
- Declarative parameter definitions with validation
- Automatic display in **Modules Config** UI
- Typed values with Boolean, Integer, Float, String, Choice, MultiChoice, Secret support

### Available Validators

All validators accept/return Python values and raise `ValidationError` on invalid
input. Keep user-facing defaults in `ConfigValue(...)`; validator `default=` exists
mostly for compatibility and low-level normalization.

| Validator | Arguments | Description |
|-----------|-----------|-------------|
| `Boolean(default=None)` | `default` | Boolean value. Accepts booleans, common true/false strings and `0/1`. |
| `Integer(default=None, min=None, max=None)` | `min`, `max` | Integer number, rejects bool and non-integral floats. |
| `Float(default=None, min=None, max=None)` | `min`, `max` | Floating point number, rejects bool. |
| `String(default="", min_len=None, max_len=None, supports_placeholders=False, placeholder_scope=None)` | `min_len`, `max_len`, `supports_placeholders`, `placeholder_scope` | String value with optional length checks and placeholder help. |
| `Placeholders(default="", min_len=None, max_len=None, *, placeholder_scope="any")` | `placeholder_scope` | String with placeholder help enabled. |
| `Choice(choices, default=None)` | `choices` | One of a list of choices. If `default` is omitted, the first choice is used internally. |
| `MultiChoice(choices, default=None)` | `choices` | List of choices; config UI toggles choices on/off. |
| `List(default=None, item_type=None)` | `item_type` | List, optionally requiring every item to match a Python type or a `Validator` instance. |
| `DictType(default=None, key_type=None, value_type=None)` | `key_type`, `value_type` | Dictionary, optionally requiring keys/values to match Python types or `Validator` instances. |
| `Secret(default=None)` | `default` | Secret value. Uses string validation and marks value as hidden/secret in UI. |
| `Hidden(validator=None, default=None)` | `validator` | Wrap another validator and mark the value as hidden. |
| `Link(default="", schemes=("http", "https"), require_netloc=True, **kwargs)` | `schemes`, `require_netloc` | URL string. `**kwargs` are forwarded to `String` (`min_len`, `max_len`, ...). |
| `RegExp(pattern, default="", flags=0, fullmatch=True, **kwargs)` | `pattern`, `flags`, `fullmatch` | String matching a regex. `fullmatch=False` switches to search mode. |
| `TelegramID(default=0, min=-10**15, max=10**15, allow_zero=False)` | `allow_zero`, `min`, `max` | Telegram ID. Use `allow_zero=True` for explicit `0` sentinel values. The historical `default=0` sentinel is kept compatible. |
| `Union(*validators, default=...)` | validators | Combines validators; first successful validator wins. |
| `NoneType(default=None)` | `default` | `None` / `null` value. Also accepts empty string and `"none"`/`"null"` strings. |
| `Emoji(default="", min_count=1, max_count=None, **kwargs)` | `min_count`, `max_count` | Emoji or emoji sequence. `**kwargs` are forwarded to `String`. |
| `EntityLike(default="")` | `default` | Telegram entity-like value: numeric ID, `@username`, `t.me` invite/link, or URL. |

Put defaults in `ConfigValue`, not in the validator:

```python
from core.lib.loader.module_config import Boolean, Choice, ConfigValue, Integer, List

ConfigValue("enabled", True, validator=Boolean())
ConfigValue("timeout", 30, validator=Integer(min=1, max=300))
ConfigValue("mode", "default", validator=Choice(choices=["default", "fast", "safe"]))
ConfigValue("allowed_users", [], validator=List(item_type=int))
```

Use `TelegramID(allow_zero=True)` when `0` is a valid sentinel/default value,
for example a disabled `log_chat`. For backward compatibility,
`TelegramID(default=0)` also accepts `0`, but explicit `allow_zero=True` is
clearer in new modules.

`Union(...)` uses validators in the order provided. Put broad validators like
`String()` last if you want `Integer()` / `Float()` to preserve numeric values:
`Union(Integer(), Float(), String())`.

### Usage (Class-Style - Recommended)

```python
from __future__ import annotations

from core.lib.loader.module_base import ModuleBase
from core.lib.loader.module_config import (
    Boolean,
    Buttons,
    Choice,
    ConfigValue,
    Integer,
    ModuleConfig,
    String,
)


class MyModule(ModuleBase):
    name = "MyModule"
    version = "1.0.0"

    config = ModuleConfig(
        ConfigValue(
            "enabled",
            True,
            description="Enable module",
            validator=Boolean(),
        ),
        ConfigValue(
            "api_key",
            "",
            description="API Key",
            validator=String(),
        ),
        ConfigValue(
            "mode",
            "default",
            description="Operation mode",
            validator=Choice(
                choices=["default", "fast", "safe"],
            ),
        ),
        Buttons(
            "Maintenance",
            "Quick maintenance actions for this module",
            "Open maintenance",
            lambda module: [
                [module.Button.inline("Restart worker", module.restart_worker)]
            ],
            key="maintenance",
        ),
    )

    async def on_load(self) -> None:
        """Load persisted config values from DB into ModuleConfig."""
        config_dict = await self.kernel.get_module_config(
            self.name, self.config.to_dict()
        )
        self.config.from_dict(config_dict)
        self.kernel.store_module_config_schema(self.name, self.config)

    async def restart_worker(self, event) -> None:
        await event.answer("Restart requested", alert=True)
```

### Usage (Function-Style)

```python
from core.lib.loader.module_config import (
    Boolean,
    Choice,
    ConfigValue,
    ModuleConfig,
    String,
)


def register(kernel):
    config = ModuleConfig(
        ConfigValue(
            "enabled",
            True,
            description="Enable module",
            validator=Boolean(),
        ),
        ConfigValue(
            "api_key",
            "",
            description="API Key",
            validator=String(),
        ),
        ConfigValue(
            "mode",
            "default",
            description="Operation mode",
            validator=Choice(
                choices=["default", "fast", "safe"],
            ),
        ),
    )

    async def on_load():
        config_dict = await kernel.get_module_config(
            __name__, config.to_dict()
        )
        config.from_dict(config_dict)
        await kernel.save_module_config(__name__, config.to_dict())
        kernel.store_module_config_schema(__name__, config)

    kernel.register_on_load(on_load)
```

### UI Buttons Items

`Buttons(...)` adds a UI-only row to the module config menu. It is not a stored
config value, is not included in `config.to_dict()`, and cannot be edited with
`cfg`/`fcfg` as a value.

Use it for custom action menus near module settings:

```python
from core.lib.loader.module_config import Boolean, Buttons, ConfigValue, ModuleConfig, Row, String


class MyModule(ModuleBase):
    config = ModuleConfig(
        ConfigValue("template", "Hello", validator=String()),
        Row(),
        Buttons(
            "Template actions",          # title inside the buttons menu
            "Actions for template tools", # description inside the menu
            "Template tools",            # text in the config keys list
            lambda module: [
                [module.Button.inline("Preview", module.preview_template)],
                [module.Button.url("Docs", "https://github.com/hairpin01/MCUB-fork/API_DOC.md")],
            ],
            on_click=lambda module, event: module.refresh_template_tools(event),
            key="template_tools",         # optional stable internal key
        ),
    )
```

`buttons` can be a ready button matrix or a callable returning one. When buttons
need the live module instance, define the callable as `lambda module: ...` and
use `module.Button`. The config UI adds the Back/Close buttons itself.

`on_click` is called when the user opens this buttons group from the config UI.
It can be synchronous or asynchronous and can use the live module instance:

```python
Buttons(
    "Actions",
    "Run quick actions",
    "Open actions",
    lambda module: [[module.Button.inline("Run", module.run_action)]],
    on_click=lambda module, event: module.prepare_actions(event),
)
```

`Row()` is a UI-only layout marker for the module config key list. It ends the
current row, so the next config key starts on a new line. It is not stored, not
included in `config.to_dict()`, and is not counted as a config value.

`Answer(...)` adds an informational config button. When pressed, it answers with
a popup (`event.answer`) and does not edit the config form.

`Group(...)` adds a submenu with nested `ConfigValue` and UI-only items. Nested
`ConfigValue`s are still real config values and are saved normally; only the
group shell, rows, answers and buttons are UI-only.

`Divider(...)` adds a visual separator button. It is useful inside large groups.

`Url(...)` adds a direct URL button without creating a custom `Buttons(...)` menu.

`Callback(...)` adds a single callback button. The callback can accept
`(module, event)`, `(event)`, or no arguments and can be async.

`Status(...)` adds a read-only status view with dynamic value text.

`Notice(text, show_if=True)` adds a conditional popup button. Both `text` and
`show_if` may be static values or callables accepting the live module instance:

```python
Notice(
    lambda module: module.set_text_status,
    lambda module: module.rules_now_button,
)
```

Built-in UI-only items (`Buttons`, `Row`, `Answer`, `Group`, `Divider`, `Url`,
`Callback`, `Status`, `Notice`) expose
`ui_only = True` and `ui_type`.
`ModuleConfig` uses this contract to keep UI helpers out of stored config values.

#### UI-only Constructor Reference

| Item | Arguments | Behavior |
|------|-----------|----------|
| `Buttons(title, description="", button_text=None, buttons=None, *, on_click=None, key=None)` | `title`, `description`, `button_text`, `buttons`, `on_click`, `key` | Opens a custom button submenu. `buttons` can be a static matrix or `lambda module: ...`. `on_click` runs before opening. |
| `Row(*, key=None)` | `key` | Ends the current row so following buttons start on a new line. |
| `Divider(text="────────", show_if=True, *, key=None)` | `text`, `show_if`, `key` | Visual separator row. `text`/`show_if` may be static or `lambda module: ...`. |
| `Url(button_text, url, show_if=True, *, key=None)` | `button_text`, `url`, `show_if`, `key` | Direct URL button. `button_text` and `url` may be dynamic. |
| `Callback(button_text, on_click=None, show_if=True, *, key=None)` | `button_text`, `on_click`, `show_if`, `key` | Single callback button. `on_click` can be sync/async and can accept `(module, event)`, `(event)`, or no args. |
| `Status(title, value="", show_if=True, *, key=None)` | `title`, `value`, `show_if`, `key` | Read-only status view. `value` can be `lambda module: ...`. |
| `Notice(text, show_if=True, *, alert=True, key=None)` | `text`, `show_if`, `alert`, `key` | Conditional popup button. Uses `event.answer(text, alert=alert)`. |
| `Answer(button_text, text="", *, alert=True, key=None)` | `button_text`, `text`, `alert`, `key` | Informational popup button. Unlike `Notice`, button text and popup text are separate. |
| `Group(title, items, description="", *, button_text=None, on_click=None, show_if=True, key=None)` | `title`, `items`, `description`, `button_text`, `on_click`, `show_if`, `key` | Submenu containing nested `ConfigValue` and UI-only items. `on_click` runs before rendering the group. |

For all UI-only classes, `key` is optional and only controls the stable internal
UI key. It is not a stored config value. `show_if` can be a boolean or
`lambda module: ...` and controls whether the item appears in config UI.

```python
config = ModuleConfig(
    ConfigValue("first", True, validator=Boolean()),
    Row(),
    ConfigValue("second", "value", validator=String()),
    ConfigValue("third", "value", validator=String()),
)
```

This renders roughly as:

```text
[ first ]
[ second ] [ third ]
```

Grouped settings example:

```python
from core.lib.loader.module_config import Answer, ConfigValue, Group, ModuleConfig, Row, Secret


config = ModuleConfig(
    Group(
        "🗂 API",
        [
            ConfigValue("api_key", "", validator=Secret()),
            Row(),
            Answer("About", "api key from gemini ai"),
        ],
        description="Gemini API settings",
    )
)
```

Mixed UI-only controls example:

```python
from core.lib.loader.module_config import Callback, Divider, Notice, Status, Url


config = ModuleConfig(
    Group(
        "Runtime",
        [
            Status("State", lambda module: module.runtime_status()),
            Url("Docs", "https://github.com/hairpin01/MCUB-fork/API_DOC.md"),
            Divider(),
            Callback("Refresh", lambda module, event: module.refresh_runtime(event)),
            Notice(
                lambda module: module.set_text_status,
                lambda module: module.rules_now_button,
            ),
        ],
    )
)
```

Full class-style smoke-test example with inline, input, URL buttons and
`on_click` saving the config-menu event:

```python
import core.lib.loader.module_base as loader
import core.lib.loader.module_config as cfg
import core.lib.types as typ


class MyModule(loader.ModuleBase):
    name = "Module"

    config = cfg.ModuleConfig(
        cfg.Buttons(
            "Link",
            "Ссылки и тесты inline/input кнопок",
            "test menu",
            lambda module: [
                [
                    module.Button.inline("test отправить log", module.on_click),
                    module.Button.input("Написать в log", module.on_input),
                ],
                [
                    module.Button.url("MCUB", "https://github.com/hairpin01/MCUB-fork"),
                    module.Button.url(
                        "repo modules",
                        "https://github.com/hairpin01/repo-MCUB-fork",
                    ),
                ],
            ],
            on_click=lambda module, event: module.on_save_call(event),
        )
    )

    async def on_load(self) -> None:
        self._event_config: typ.InlineMessage | None = None
        await super().on_load()

    async def on_click(self, call: typ.InlineMessage) -> None:
        self.log.info("test log send!")
        await call.answer()

    async def on_input(
        self,
        call: typ.InlineMessage,
        args: str,
        data=None,
    ) -> None:
        self.log.info(args)
        if self._event_config is not None:
            await self._event_config.edit("log send!")

    async def on_save_call(self, call: typ.InlineMessage) -> None:
        self._event_config = call
```

### ModuleConfig Parameters and Methods

```python
ModuleConfig(
    *config_values,        # ConfigValue and/or UI-only items
    on_change=None,        # global catch-all callback
    version=None,          # schema version stored in to_dict()
    migrate=None,          # migrate(data) or migrate(data, old_version)
    custom_handler=None,   # custom UI handler for module-list entry clicks
)
```

Common methods:

| Method | Description |
|--------|-------------|
| `config["key"]` / `config["key"] = value` | Read/write validated values. Writes trigger per-key and global `on_change`. |
| `config.get(key, default=None)` | Safe read with default. |
| `config.items()` / `config.keys()` | Stored config values only; UI-only items are excluded. |
| `config.ui_items()` | Stored values plus UI-only items in display order. |
| `config.group_items(group_key)` | Items inside a `Group(...)` submenu. |
| `config.to_dict()` | Convert to DB-safe dict and add `__mcub_config__` marker. Adds `__mcub_config_version__` when `version` is set. |
| `config.from_dict(data)` | Hydrate values from DB. Calls `migrate` first, ignores unknown keys, does **not** fire `on_change`. |
| `config.bind_owner(module)` | Bind live module instance for owner-aware callbacks. Usually done by the loader. |
| `config.set_custom_handler(callback)` | Set custom handler for the module button in the Modules Config list. |
| `config.set_on_change(callback)` | Set global catch-all `on_change`. |
| `config.set_on_change("key", callback)` | Set per-key `on_change` after construction. |
| `config.reset_to_defaults(*keys, trigger_on_change=True)` | Reset all or selected keys to their defaults. |

### Custom Module Config Handler

By default, clicking a module in **Modules Config** opens the standard key list.
Set `custom_handler` to override only that module-list button. Standard config UI
is still available through the callback data passed to the handler.

```python
config = ModuleConfig(
    ConfigValue("enabled", True, validator=Boolean()),
    custom_handler=lambda module, event, data: module.open_custom_config(event, data),
)


async def open_custom_config(self, event, data):
    await event.edit(
        "<b>Custom config</b>",
        buttons=[
            [self.Button.inline("⚙️ Standard config", data["standard_config"])],
            [self.Button.inline("🔙 Modules", data["back_to_modules"])],
            [self.Button.inline("❌ Close", data["close"])],
        ],
        parse_mode="html",
    )
```

Supported callback forms:

- `custom_handler(module, event, data)` - full owner-aware form.
- `custom_handler(module, event)` - no data payload.
- `custom_handler(event)` or `custom_handler()` - simple forms.

`data` is a dict with ready-to-use callback bytes:

| Key | Meaning |
|-----|---------|
| `module_name` | Current module name. |
| `modules_page` | Page number in the modules list. |
| `back_to_modules` | Back to the modules list page. |
| `standard_config` | Open the standard config UI for this module. |
| `menu` | Back to the main config menu. |
| `close` | Close the inline form. |

If the handler returns `None`, MCUB assumes it edited/answered the event itself.
It may also return:

- `"text"` - edited as HTML text.
- `(text, buttons)` or `(text, buttons, parse_mode)`.
- `{"text": ..., "buttons": ..., "parse_mode": "html"}`.

### ConfigValue Parameters

```python
ConfigValue(
    key,                    # str: Parameter name (required)
    default,                # Default value
    description="",         # str/callable: Description for UI
    validator=None,         # Validator (Boolean, String, Choice, etc.)
    hidden=False,           # bool: Hide in UI
    on_change=None,         # callable: Function on change (on_change(old, new))
    show_if=True,           # bool/callable: Show in config UI only when true
)
```

`show_if` can be a boolean or a callable. For class-style modules, use
`lambda module: ...` to hide a value based on live module state:

```python
ConfigValue(
    "log_chat",
    "",
    description="Log chat used only when notifications are enabled",
    validator=String(),
    show_if=lambda module: module.config["notify_errors"],
)
```

`description` can also be owner-aware. This is useful for localized module
strings:

```python
ConfigValue(
    "key",
    None,
    description=lambda module: module.strings("desc_none"),
    validator=NoneType(),
)
```

### `on_change` Hook

`on_change` is called when a value is changed through `ModuleConfig.__setitem__`.
This includes changes made from the config UI, inline `cfg`, `.cfg`, and `.fcfg`
for live `ModuleConfig` schemas.

The callback can be synchronous or asynchronous. For class-style modules, use
`lambda module, old, new: ...` when the callback needs the live module instance.
The older `on_change(old, new)` form is still supported when no module instance
is needed.

```python
async def restart_worker(module, old: bool, new: bool) -> None:
    if old == new:
        return
    await module.restart_worker(enabled=new)


config = ModuleConfig(
    ConfigValue(
        "worker_enabled",
        True,
        description="Enable background worker",
        validator=Boolean(),
        on_change=lambda module, old, new: restart_worker(module, old, new),
    ),
)
```

`on_change` is not called while loading persisted values with `from_dict()`.
It is for user/runtime changes, not for initial hydration from the database.

`ModuleConfig` also supports a global catch-all `on_change` callback. It is called
after the per-value hook for every changed key:

```python
config = ModuleConfig(
    ConfigValue("enabled", True, validator=Boolean()),
    ConfigValue("mode", "safe", validator=String()),
    on_change=lambda module, key, old, new: module.schedule_config_save(),
)
```

The global callback can be `on_change(key, old, new)` or owner-aware
`on_change(module, key, old, new)`.

You can also install hooks after construction:

```python
config.set_on_change(lambda module, key, old, new: module.schedule_config_save())
config.set_on_change("enabled", lambda old, new: print("enabled changed"))
```

Reset values back to defaults with:

```python
config.reset_to_defaults()                  # all keys, fires on_change hooks
config.reset_to_defaults("enabled")         # selected key
config.reset_to_defaults(trigger_on_change=False)  # silent reset
```

### Schema Version and Migration

Use `version=` and `migrate=` when stored config data needs to be transformed
before hydration. `to_dict()` stores `__mcub_config_version__`; `from_dict()` calls
`migrate(data)` or `migrate(data, old_version)` before loading known keys.

```python
def migrate_config(data: dict, old_version):
    data = dict(data)
    if "old_api_key" in data:
        data["api_key"] = data.pop("old_api_key")
    return data


config = ModuleConfig(
    ConfigValue("api_key", "", validator=String()),
    version=2,
    migrate=migrate_config,
)
```

Unknown keys are still ignored after migration, so migrations can safely keep
compatibility with older stored dictionaries.

### Custom Validators

Create custom validators by subclassing `Validator` and overriding `validate()`.
Raise `ValidationError` for invalid values and return the normalized Python value
for valid input. Set `internal_id` to control the type name shown in schema/UI.

```python
import re
from typing import Any

from core.lib.loader.module_config import ConfigValue, ModuleConfig, ValidationError, Validator


class HexColor(Validator):
    internal_id = "HexColor"
    _pattern = re.compile(r"^#[0-9a-fA-F]{6}$")

    def validate(self, value: Any) -> str:
        if not isinstance(value, str):
            raise ValidationError("Expected hex color string")

        value = value.strip()
        if not self._pattern.fullmatch(value):
            raise ValidationError("Expected color like #ff8800")

        return value.lower()


config = ModuleConfig(
    ConfigValue(
        "accent_color",
        "#ff8800",
        description="UI accent color",
        validator=HexColor(),
    ),
)
```

If stored representation differs from runtime representation, also override
`to_python()` and `to_storage()`:

```python
class CsvList(Validator):
    internal_id = "CsvList"

    def validate(self, value: Any) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return value
        raise ValidationError("Expected comma-separated string or list of strings")

    def to_python(self, value: Any) -> list[str]:
        return self.validate(value)

    def to_storage(self, value: Any) -> str:
        return ",".join(self.validate(value))
```

### Important Notes

1. **Always call `config.to_dict()` before saving** - this adds the `__mcub_config__` marker
2. **`kernel.store_module_config_schema()` is REQUIRED** - without it, Choice fields won't have inline selection buttons
3. **Always use `ConfigValue` objects** inside `ModuleConfig()`, never pass validators (`Boolean`, `String`, etc.) directly - `ModuleConfig.__init__` expects `*ConfigValue`
4. **Read values via `self.config["key"]`** for class-style or `config["key"]` for function-style - always read from the live instance
5. **Use Choice instead of String for enums** - provides dropdown UI in the config panel
6. **Keep default values in `ConfigValue`** - validators should validate/normalize, not duplicate the same default
7. **Use list validators for lists** - `List(item_type=...)` for arbitrary lists, `MultiChoice(choices=[...])` for lists selected from known choices
