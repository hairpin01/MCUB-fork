# Module Structure

← [Index](../../API_DOC.md)

## Basic Structure

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

## Module Header Comments

Each module file can contain special comment directives:

| Directive | Description |
|-----------|-------------|
| `# requires:` | Comma-separated list of pip packages |
| `# author:` | Author name or username |
| `# version:` | Module version (e.g. `1.0.0`) |
| `# description:` | Short module description |
| `# banner_url:` | URL to image for banner display on load/man |
| `# scop:` | Kernel compatibility constraints |

## Banner (`# banner_url:`)

Displays an image banner when module loads or when viewing with `man` command.

```python
# banner_url: https://raw.githubusercontent.com/user/repo/main/banner.png
```

> Banner uses `invert_media=True` for better visibility.

## Kernel Compatibility (`# scop:`)

Controls which kernel versions the module is compatible with.

**Syntax:**
```
# scop: inline
# scop: ffmpeg
# scop: kernel min v{version}
# scop: kernel max v{version}
```

**Flags:**

| Flag | Description |
|------|-------------|
| `inline` | Module requires an inline bot to be configured |
| `ffmpeg` | Module requires `ffmpeg` to be installed |
| `kernel min v{version}` | Minimum kernel version required |
| `kernel max v{version}` | Maximum kernel version supported |

> [!NOTE]
> For `min`/`max` version you can use `[__lastest__]` — the kernel will resolve it to the latest available version.

**Multiple flags** can be combined:
```python
# scop: inline
# scop: ffmpeg
# scop: kernel min v1.0.2
# scop: kernel max v[__lastest__]
```

## Command Descriptions

There are **4 ways** to document commands:

### 1. Comment after decorator (recommended)

Place a single-line comment **immediately after** the `@kernel.register.command(...)` decorator.

```python
@kernel.register.command('cmd', alias=['command'])
# list trust users
async def command_handler(event):
    # ...
```

> [!TIP]
> Keep command descriptions to **one line** — concise and lowercase.

### 2. `doc` parameter (dict with multiple languages)

```python
@kernel.register.command('ping', doc={
    'en': 'check bot latency',
    'ru': 'проверить задержку бота'
})
async def ping(event):
    await event.edit('Pong!')
```

### 3. `doc_en` / `doc_ru` parameters

```python
@kernel.register.command('hello', doc_en='greet user', doc_ru='поприветствовать пользователя')
async def hello(event):
    await event.edit('Hello!')
```

### 4. Combining with aliases

```python
@kernel.register.command('trust', alias=['tl', 'trustlist'])
# list trusted users
async def trust_list(event):
    ...
```

**Full example:**
```python
def register(kernel):

    @kernel.register.command('trust', alias=['tl'])
    # list trusted users
    async def trust_list(event):
        ...

    @kernel.register.command('untrust', alias=['utl'])
    # remove user from trust list
    async def untrust_user(event):
        ...

    @kernel.register.command('ping', doc={'en': 'check bot latency', 'ru': 'проверить задержку'})
    async def ping(event):
        await event.edit('Pong!')
```

## Supported Languages

Only `ru` and `en` are supported in the UI (defined in settings module):

| Code | Language |
|------|----------|
| `ru` | Russian |
| `en` | English |

> [!TIP]
> Keep command descriptions to **one line** — concise and lowercase.

**Full example:**
```python
def register(kernel):

    @kernel.register.command("trust", alias=['tl'])
    # list trusted users
    async def trust_list(event):
        ...

    @kernel.register.command("untrust", alias=['utl'])
    # remove user from trust list
    async def untrust_user(event):
        ...
```
