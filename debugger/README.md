# MCUB Debugger

Static analysis tool for MCUB modules. Detects common errors before runtime.

> [!IMPORTANT]
> **Python 3.10+ required.** MCUB Debugger supports only Python 3.10 and newer. For best experience, use the latest version (e.g., Python 3.14.x).

## Installation

```bash
# As pip package (requires network)
pip install mcub-debugger

# Or from source (no network needed)
cd debugger
pip install -e .
```

Or use directly as module:

```bash
python -m debugger.cli modules/
```

## Usage

### Command Line

```bash
# Debug single module
mcub-debugger modules/my_module.py
python -m debugger.cli modules/my_module.py

# Debug all modules in directory
mcub-debugger modules/
python -m debugger.cli modules/

# Output formats
mcub-debugger modules/ -f json
mcub-debugger modules/ -f simple

# Save report
mcub-debugger modules/ -o report.txt
```

### Python API

```python
from debugger import ModuleDebugger, debug_module

# Debug single file
result = debug_module("modules/my_module.py")

if result.has_warnings:
    for warning in result.warnings:
        print(f"[{warning.rule_id}] Line {warning.line}: {warning.message}")

# Debug directory
debugger = ModuleDebugger()
results = debugger.debug_directory("modules/")
```

## Detected Issues

| Rule ID | Severity | Issue |
|---------|----------|-------|
| MCUB001 | Warning | `event.edit()` with `buttons=` argument |
| MCUB002 | Warning | `event.edit()` with `reply_markup=` argument |
| MCUB003 | Error | Callback/inline event without `pattern` filter |
| MCUB004 | Warning | `event.answer()` with `show_alert=` instead of `alert=` |
| MCUB005 | Warning | `event.delete()` for bot client messages |
| MCUB006 | Warning | Inline/callback events without `bot_client=True` |
| MCUB008 | Warning | Async function without `await` |
| MCUB009 | Error | Typos in `register` method names |
| MCUB010 | Warning | Incorrect button format |
| MCUB011 | Error | Unknown event type |
| MCUB012 | Info | Consider using `client.delete_messages()` |
| MCUB013 | Warning | Accessing `event.message` in deleted handler |
| MCUB014 | Warning | `event.edit()` in callback handler notes |
| MCUB015 | Error | Handler must be `async def` |
| MCUB016 | Warning | Button callback data should be bytes |
| MCUB017 | Warning | Callback/inline events require `bot_client=True` |
| MCUB018 | Warning | Event handler should have pattern filter |

## Example Output

```
──────────────────────────────────────────────────────────────────────
[WARNING] MCUB016 method 'handler' lines 42
Message: Button callback data should be bytes (b'...'), not string.
modules/test.py:42:21

| 42      Button.inline("Click", data="string_data")
| 42                      ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Fix: Change data='string_data' to data=b'string_data'
──────────────────────────────────────────────────────────────────────

──────────────────────────────────────────────────────────────────────
[WARNING] MCUB017 method 'callback' lines 15
Message: Event 'callbackquery' requires bot_client=True.
modules/test.py:15:1

| 15  @kernel.register.event("callbackquery", pattern=r"test")
| 15  ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Fix: Add bot_client=True to @kernel.register.event() decorator
──────────────────────────────────────────────────────────────────────
```

## Features

- **AST-based analysis** - Parses Python code into AST for accurate detection
- **Context awareness** - Tracks variable types and scope
- **Decorator parsing** - Extracts arguments from `@kernel.register.*` decorators
- **Multiple output formats** - text, json, simple
- **Extensible rules** - Easy to add new detection rules

## License

MIT
