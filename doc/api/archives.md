# Archive Installation API

← [Index](../../API_DOC.md)

MCUB supports installing modules from ZIP and tar.gz archives via `kernel.install_from_archive()` and the `ArchiveManager` class.

Archives can be:
- **Single module** - a `.py` file or a package with `__init__.py`
- **Multi-module pack** - multiple modules in one archive, each with a `register()` function or `ModuleBase` subclass

---

## ArchiveManager

The `ArchiveManager` handles downloading, validating, and extracting module archives. It is available as `kernel.archive_manager` but its methods are typically called through higher-level `kernel.install_from_archive()`.

### `kernel.archive_manager.download(url: str) -> bytes | None`

Download an archive from a URL. Validates the URL against allowed domains (SSRF protection).

**Trusted domains (no warning):**
- `raw.githubusercontent.com`
- `github.com`
- `raw.githubusercontentusercontent.com`
- `raw.github.com`

Other domains still work but produce a warning log.

```python
data = await kernel.archive_manager.download("https://github.com/user/repo/archive/main.zip")
if data:
    print(f"Downloaded {len(data)} bytes")
```

### `kernel.archive_manager.validate(archive_bytes: bytes) -> bool`

Check that the archive is valid and contains at least one `.py` file. Supports both ZIP and tar.gz formats.

```python
if kernel.archive_manager.validate(data):
    print("Archive is valid")
```

### `async kernel.archive_manager.extract(archive_bytes: bytes, target_dir: str) -> ExtractionResult`

Extract an archive to a directory. Returns an `ExtractionResult` dataclass.

```python
result = await kernel.archive_manager.extract(data, "modules_loaded/")
if result.success:
    print(f"Extracted {len(result.modules)} modules")
    for mod in result.modules:
        print(f"  - {mod.name} ({mod.file_path})")
```

**`ExtractionResult` fields:**

| Field | Type | Description |
|-------|------|-------------|
| `success` | `bool` | Whether extraction succeeded |
| `extracted_dir` | `str \| None` | Path to extracted directory |
| `modules` | `list[ModuleInfo] \| None` | List of found modules |
| `metadata` | `PyProjectMeta \| None` | Metadata from pyproject.toml (if any) |
| `pack_type` | `str \| None` | `"single"` or `"pack"` |
| `error` | `str \| None` | Error message on failure |

---

## PyProjectMeta

Metadata parsed from `pyproject.toml` inside the archive.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str \| None` | Package name |
| `version` | `str \| None` | Package version |
| `dependencies` | `list \| None` | Pip dependencies |
| `main_module` | `str \| None` | Main module name (from `[tool.mcub.main]`) |
| `pack_type` | `str \| None` | `"single"` or `"pack"` |

Example `pyproject.toml` in archive:

```toml
[tool.mcub]
name = "my-module"
version = "1.0.0"
main = "my_module"
type = "single"
```

---

## ModuleInfo

Information about a module found in an archive.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Module name (filename without `.py`) |
| `file_path` | `str` | Relative path inside archive |
| `is_main` | `bool` | Whether this is the main module |

---

## `async kernel.install_from_url(url, module_name=None, auto_dependencies=True)`

Install from a URL - automatically detects whether it's a direct `.py` file or an archive, downloads, extracts, and loads the module. [Full Docs](api/module-api.md)

```python
# Direct .py URL
success, msg = await kernel.install_from_url(
    "https://raw.githubusercontent.com/user/repo/main/module.py"
)

# Archive URL
success, msg = await kernel.install_from_url(
    "https://github.com/user/repo/archive/main.zip"
)
```

---

## Module Type Detection

Archives are automatically classified:

| Type | Description |
|------|-------------|
| `single` | One module file or one `register()` entry point |
| `pack` | Multiple modules, each with their own `register()` or `ModuleBase` class |

Detection rules:
1. If `pyproject.toml` specifies `type`, that is used
2. Single `.py` file → `single`
3. Multiple files with multiple `register()` functions → `pack`
4. Otherwise → `single`
