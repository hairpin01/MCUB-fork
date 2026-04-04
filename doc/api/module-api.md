# Kernel Module API

## Repository Management

`kernel.add_repository(url)` — Add a new module repository URL.

```python
success, msg = await kernel.add_repository("https://example.com/modules/")
```

`kernel.remove_repository(index)` — Remove a repository by its 1-based index.

```python
success, msg = await kernel.remove_repository(2)
```

`kernel.get_repo_name(url)` — Get the human-readable name for a repository.

```python
name = await kernel.get_repo_name("https://github.com/user/repo/")
```

`kernel.get_repo_modules_list(repo_url)` — Fetch the list of available modules from a repository.

```python
modules = await kernel.get_repo_modules_list("https://github.com/user/repo/")
```

`kernel.download_module_from_repo(repo_url, module_name)` — Download module source code from a repository.

```python
code = await kernel.download_module_from_repo("https://github.com/user/repo/", "mymodule")
```

---

## Module Loading API

`kernel.load_module_from_file(file_path, module_name, is_system=False, source_url=None, source_repo=None)`
Load a Python module from a file path and register it with the kernel.

```python
success, msg = await kernel.load_module_from_file(
    "/path/to/module.py",
    "mymodule",
    is_system=False
)
```

`kernel.install_from_url(url, module_name=None, auto_dependencies=True)`
Download and install a module directly from a URL.

```python
# Install from direct .py URL
success, msg = await kernel.install_from_url("https://example.com/modules/mymodule.py")

# Install from repo by name
success, msg = await kernel.install_from_url("https://github.com/user/repo/", "mymodule")
```

`kernel.load_system_modules()` — Load all modules from the system modules directory (`modules/`).

`kernel.load_user_modules()` — Load all modules from the user modules directory (`modules_loaded/`).

`kernel.unregister_module_commands(module_name, force=False)` — Stop loops/handlers and unregister all commands for a module.

```python
# Unload user module
await kernel.unregister_module_commands("mymodule")

# Force unload system module
await kernel.unregister_module_commands("loader", force=True)
```

---

## Module Source Tracking

`kernel._module_sources` — Dictionary tracking where each module was installed from.

```python
{
    "module_name": {
        "url": "https://...",   # Direct URL or None
        "repo": "https://..."   # Repo URL or None
    }
}
```

```python
if "mymodule" in kernel._module_sources:
    source = kernel._module_sources["mymodule"]
    await event.edit(f"Installed from: {source.get('repo') or source.get('url')}")
```
