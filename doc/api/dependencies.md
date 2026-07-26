# Dependency Management API

← [Index](../../API_DOC.md)

MCUB provides automatic dependency resolution and installation for modules.
When a module specifies `# requires: pip_package` in its header or has `dependencies` in a class-style module, the loader automatically installs missing packages.

---

## How It Works

1. Module is loaded, the loader reads `# requires:` header or `dependencies` attribute
2. `pre_install_requirements()` parses and validates the requirements
3. Missing packages are installed via pip using `install_dependencies_batch()`
4. If a module tries to import something missing at runtime, `exec_with_auto_deps()` catches `ImportError` and auto-installs

All methods are available on the kernel. The module API handles them automatically - you usually don't need to call them directly.

---

## Kernel Methods

### `kernel.resolve_pip_name(import_name: str) -> str`

Convert a Python import name to its pip package name.

```python
name = kernel.resolve_pip_name("PIL")
# -> "Pillow"
name = kernel.resolve_pip_name("sklearn")
# -> "scikit-learn"
```

Has built-in mappings for common packages:
| Import name | Pip package |
|-------------|-------------|
| `PIL` | `Pillow` |
| `cv2` | `opencv-python` |
| `sklearn` | `scikit-learn` |
| `bs4` | `beautifulsoup4` |
| `yaml` | `PyYAML` |
| `google.generativeai` | `google-generativeai` |
| and more... |  |

### `async kernel.pre_install_requirements(code: str, module_name: str) -> None`

Parse `# requires:` comments from module source code and install any missing packages.

```python
code = "# requires: aiohttp, requests\n..."
await kernel.pre_install_requirements(code, "my_module")
```

### `async kernel.install_dependencies_batch(requirements: list[str], module_name: str) -> list[str]`

Install a list of pip packages. Returns a list of packages that failed to install.

```python
failed = await kernel.install_dependencies_batch(
    ["aiohttp", "requests", "beautifulsoup4"],
    "my_module",
)
if failed:
    print(f"Failed to install: {failed}")
```

### `async kernel.pre_install_requirements_batch(modules_data: list[tuple[str, str]]) -> list[str]`

Install dependencies for multiple modules at once (batch mode). Each entry is `(module_name, code)`.

```python
modules_data = [
    ("mod_a", "# requires: aiohttp\n..."),
    ("mod_b", "# requires: pillow\n..."),
]
failed = await kernel.pre_install_requirements_batch(modules_data)
```

### `async kernel.exec_with_auto_deps(code: str, module_globals: dict, module_name: str) -> dict`

Execute code with automatic `ImportError` recovery. If an import fails, it resolves the pip name, installs the package, and retries.

```python
code = """
import aiohttp
async def fetch(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return await resp.text()
"""
result = await kernel.exec_with_auto_deps(code, {}, "my_module")
```

---

## Module-Declared Dependencies

### Function-Style Modules

Use the `# requires:` comment header:

```python
# requires: aiohttp, pillow
# author: @user
# description: Module with dependencies

def register(kernel):
    import aiohttp
    # ...
```

### Class-Style Modules

Use the `dependencies` class attribute:

```python
class MyModule(ModuleBase):
    name = "MyModule"
    dependencies = ["aiohttp", "pillow"]
    # ...
```

The loader automatically installs all dependencies before the module is registered.

---

## Requirements Format

Requirements follow pip syntax:

```python
# requires: package_name
# requires: package_name>=1.0,<2.0
# requires: package_name>=1.0, package2
# requires: git+https://github.com/user/repo.git
```

Multiple packages can be comma-separated or specified on separate lines.
