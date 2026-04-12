# Module Config API

← [Index](../../API_DOC.md)

MCUB provides two ways to configure modules: a simple dict-based API and a structured **ModuleConfig** system (recommended). Both are backed by the database and persist across restarts.

## Simple Dict API

`kernel.get_module_config(module_name, default=None)` — Retrieve the full config dict for a module.

`kernel.save_module_config(module_name, config_data)` — Save the full config dict for a module.

`kernel.get_module_config_key(module_name, key, default=None)` — Retrieve a single key from the module config.

`kernel.set_module_config_key(module_name, key, value)` — Set a single key in the module config without overwriting other keys.

`kernel.delete_module_config_key(module_name, key)` — Remove a single key from the module config.

`kernel.update_module_config(module_name, updates)` — Merge a dict of updates into the module config (shallow merge).

`kernel.delete_module_config(module_name)` — Delete the entire config for a module.

`kernel.store_module_config_schema(module_name, config)` — **REQUIRED for UI!** Store a live ModuleConfig schema for the UI.

---

## ModuleConfig (Recommended)

The recommended way to create module configuration. Provides:
- Declarative parameter definitions with validation
- Automatic display in **Modules Config** UI
- Typed values with Boolean, Integer, Float, String, Choice, MultiChoice, Secret support

### Available Validators

| Validator | Description |
|-----------|-------------|
| `Boolean(default=...)` | Boolean value (True/False) |
| `Integer(default=..., min=..., max=...)` | Integer number |
| `Float(default=..., min=..., max=...)` | Floating point number |
| `String(default=..., min_len=..., max_len=...)` | String value |
| `Choice(choices=[...], default=...)` | One of a list of choices |
| `MultiChoice(choices=[...], default=[...])` | List of choices |
| `Secret(default=...)` | Secret value (hidden in UI) |

### Usage

```python
from core.lib.loader.module_config import ModuleConfig, ConfigValue, Boolean, String, Choice

def register(kernel):
    config = ModuleConfig(
        ConfigValue(
            "enabled",
            True,
            description="Enable module",
            validator=Boolean(default=True)
        ),
        ConfigValue(
            "api_key",
            "",
            description="API Key",
            validator=String(default="")
        ),
        ConfigValue(
            "mode",
            "default",
            description="Operation mode",
            validator=Choice(choices=["default", "fast", "safe"], default="default")
        )
    )

    async def startup():
        config_dict = await kernel.get_module_config(__name__, {"enabled": True, "api_key": "", "mode": "default"})
        config.from_dict(config_dict)
        await kernel.save_module_config(__name__, config.to_dict())
        kernel.store_module_config_schema(__name__, config)

    asyncio.create_task(startup())

    # Use get_config() helper for live reading
    def get_config():
        live_cfg = getattr(kernel, "_live_module_configs", {}).get(__name__)
        return live_cfg if live_cfg else config
```

### ConfigValue Parameters

```python
ConfigValue(
    key,                    # str: Parameter name (required)
    default,                # Default value
    description="",         # str: Description for UI
    validator=None,         # Validator (Boolean, String, Choice, etc.)
    hidden=False,           # bool: Hide in UI
    on_change=None          # callable: Function on change (on_change(old, new))
)
```

### Important Notes

1. **Always call `config.to_dict()` before saving** — this adds the `__mcub_config__` marker
2. **Define defaults twice** — in `ConfigValue` and in the dict for `get_module_config`
3. **`kernel.store_module_config_schema()` is REQUIRED** — without it, Choice fields won't have inline selection buttons
4. **Use `get_config()` helper for live reading** — always read from live config, never cache values
5. **Use Choice instead of String for enums** — provides dropdown UI
6. **Don't use typing.List for lists** — use String with JSON
