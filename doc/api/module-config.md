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

| Validator | Description |
|-----------|-------------|
| `Boolean()` | Boolean value (True/False) |
| `Integer(min=..., max=...)` | Integer number |
| `Float(min=..., max=...)` | Floating point number |
| `String(min_len=..., max_len=...)` | String value |
| `Choice(choices=[...])` | One of a list of choices |
| `MultiChoice(choices=[...])` | List of choices |
| `List(item_type=...)` | List, optionally with item type validation |
| `DictType(key_type=..., value_type=...)` | Dictionary, optionally with key/value type validation |
| `Secret()` | Secret value (hidden in UI) |
| `Link(schemes=("http", "https"), require_netloc=True)` | Valid URL |
| `RegExp(pattern=..., flags=0, fullmatch=True)` | String that matches the given regular expression |
| `TelegramID(allow_zero=False)` | Telegram ID |
| `Union(*validators)` | Combines multiple validators, e.g. `Union(Integer(), Float())` |
| `NoneType()` | `None` / `null` value |
| `Emoji(min_count=1, max_count=None)` | Valid emoji or emoji sequence |
| `EntityLike()` | Telegram entity-like value: ID, `@username`, `t.me` link or URL |

Put defaults in `ConfigValue`, not in the validator:

```python
from core.lib.loader.module_config import Boolean, Choice, ConfigValue, Integer, List

ConfigValue("enabled", True, validator=Boolean())
ConfigValue("timeout", 30, validator=Integer(min=1, max=300))
ConfigValue("mode", "default", validator=Choice(choices=["default", "fast", "safe"]))
ConfigValue("allowed_users", [], validator=List(item_type=int))
```

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

### ConfigValue Parameters

```python
ConfigValue(
    key,                    # str: Parameter name (required)
    default,                # Default value
    description="",         # str: Description for UI
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
