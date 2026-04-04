# Best Practices

This section covers recommended patterns and modern APIs for writing MCUB modules.

## Modern Module Configuration

Use `ModuleConfig` for declarative configuration with validation and UI support:

```python
from core.lib.loader.module_config import ModuleConfig, ConfigValue, Boolean, String, Choice, Integer

def register(kernel):
    config = ModuleConfig(
        ConfigValue(
            "enabled",
            True,
            description="Enable module",
            validator=Boolean(default=True)
        ),
        ConfigValue(
            "api_url",
            "https://api.example.com",
            description="API endpoint URL",
            validator=String(default="https://api.example.com")
        ),
        ConfigValue(
            "timeout",
            30,
            description="Request timeout (seconds)",
            validator=Integer(default=30, min=1, max=300)
        ),
        ConfigValue(
            "mode",
            "default",
            description="Operation mode",
            validator=Choice(choices=["default", "fast", "safe"], default="default")
        )
    )

    async def startup():
        config_dict = await kernel.get_module_config(__name__, {
            "enabled": True,
            "api_url": "https://api.example.com",
            "timeout": 30,
            "mode": "default"
        })
        config.from_dict(config_dict)
        await kernel.save_module_config(__name__, config.to_dict())
        kernel.store_module_config_schema(__name__, config)

    asyncio.create_task(startup())

    def get_config():
        live_cfg = getattr(kernel, "_live_module_configs", {}).get(__name__)
        return live_cfg if live_cfg else config
```

## Error Handling Pattern

```python
@kernel.register.command('safe')
async def safe_handler(event):
    try:
        result = await risky_operation()
        await event.edit(f"Result: {result}")

    except ValueError as e:
        await kernel.logger.warning(f"Invalid value: {e}")
        await event.edit("Invalid input")

    except ConnectionError as e:
        await kernel.logger.error(f"Connection failed: {e}")
        await event.edit("Network error")

    except Exception as e:
        await kernel.handle_error(e, source="safe_handler", event=event)
        await event.edit("Unexpected error occurred")
```

## Async Parallel Operations

```python
@kernel.register.command('parallel')
async def parallel_handler(event):
    results = await asyncio.gather(
        operation1(),
        operation2(),
        operation3(),
        return_exceptions=True
    )
    success_count = sum(1 for r in results if not isinstance(r, Exception))
    await event.edit(f"Completed: {success_count}/3")
```

## Resource Management with Cache

```python
@kernel.register.command('cached')
async def cached_handler(event):
    cache_key = f"{__name__}_data"

    data = kernel.cache.get(cache_key)
    if data is None:
        data = await fetch_data()
        kernel.cache.set(cache_key, data, ttl=300)

    await event.edit(f"Cached data: {data}")
```
