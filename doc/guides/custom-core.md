# Custom Core MCUB

← [Index](../../API_DOC.md)

MCUB supports multiple interchangeable kernel cores. Each core is a `.py` file placed in `core/kernel/` that exposes a single `Kernel` class.

## How the Loader Works

`__main__.py` scans `core/kernel/` for `.py` files (excluding `_`-prefixed ones):

```python
from importlib import import_module
Kernel = import_module(f"core.kernel.{selected_core}").Kernel
kernel = Kernel()
await kernel.run()
```

Your custom core just needs to:
- File lives at `core/kernel/<your_core_name>.py`
- Export a class named `Kernel`
- Have an `async def run(self)` method

## Minimal Custom Core

The simplest possible core — inherits everything from `standard`:

```python
# core/kernel/mycore.py
from .standard import Kernel as _StandardKernel

class Kernel(_StandardKernel):
    async def run(self):
        self.logger.info("mycore: starting up")
        await super().run()
```

Activate it:
```bash
python3 -m core --core mycore
# or set as default
python3 -m core --set-default-core mycore
```

## Common Extension Points

| Method | When to override |
|--------|-----------------|
| `__init__` | Add new state, change default paths/repos |
| `run` | Change startup sequence, add pre/post hooks |
| `load_system_modules` | Load extra built-in modules or skip certain ones |
| `process_command` | Intercept or transform commands before dispatch |
| `handle_error` | Custom error reporting |

## Example — Custom Error Handler

```python
class Kernel(_StandardKernel):
    async def handle_error(self, e, source="unknown", event=None):
        await super().handle_error(e, source=source, event=event)
        await my_monitoring.send(f"[{source}] {e}")
```

## Core Naming Conventions

| Name | Intended meaning |
|------|-----------------|
| `standard` | Default, frequently updated |
| `zen` | Stable branch, updated less often |
| `micro` / `lite` | Stripped-down, low-resource variant |
| `dev` / `nightly` | Experimental, may be unstable |

> [!TIP]
> Prefix your core file with your username to avoid conflicts: `core/kernel/hairpin_custom.py`.
