# Introduction

MCUB (`Mitrich UserBot`) is a modular Telegram **userbot** framework built on Telethon. This documentation describes the extended API for creating modules.

## Quick Start

See [getting-started/index.md](getting-started/index.md) for quick start guide.

## Module Structure

```python
# requires: library1, library2
# author: Author Name
# version: 1.0.0
# description: Module description here
# banner_url: https://example.com/banner.png
# scop: kernel (min|max|None) v(version|[__lastest__])

def register(kernel):
    # Module code here
```

### Module Header Comments

| Directive | Description |
|-----------|-------------|
| `# requires:` | Comma-separated list of pip packages |
| `# author:` | Author name or username |
| `# version:` | Module version (e.g. `1.0.0`) |
| `# description:` | Short module description |
| `# banner_url:` | URL to image for banner display on load/man |
| `# scop:` | Kernel compatibility constraints |

### Banner

Displays an image banner when module loads:

```python
# banner_url: https://raw.githubusercontent.com/user/repo/main/banner.png
```

### Kernel Compatibility (`# scop:`)

```
# scop: inline
# scop: ffmpeg
# scop: kernel min v{version}
# scop: kernel max v{version}
```

| Flag | Description |
|------|-------------|
| `inline` | Module requires an inline bot |
| `ffmpeg` | Module requires `ffmpeg` |
| `kernel min v{version}` | Minimum kernel version |
| `kernel max v{version}` | Maximum kernel version |

### Command Descriptions

```python
@kernel.register.command("cmd", alias=['command'])
# list trust users
async def command_handler(event):
    # ...
```
