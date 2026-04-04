# Cache API

`kernel.cache.set(key, value, ttl=None)`
Store value in cache.

```python
kernel.cache.set('user_data', {'name': 'John'}, ttl=3600)
```

`kernel.cache.get(key, default=None)`
Retrieve value from cache. Returns cached value or default.

```python
data = kernel.cache.get('user_data')
```

`kernel.cache.delete(key)`
Remove key from cache.

```python
kernel.cache.delete('user_data')
```

`kernel.cache.clear()`
Clear all cache entries.

```python
kernel.cache.clear()
```

---

## Usage Example

```python
def register(kernel):
    @kernel.register.command('cached')
    async def cached_handler(event):
        cache_key = f"{__name__}_data"

        data = kernel.cache.get(cache_key)
        if data is None:
            data = await fetch_data()
            kernel.cache.set(cache_key, data, ttl=300)

        await event.edit(f"Cached data: {data}")
```
