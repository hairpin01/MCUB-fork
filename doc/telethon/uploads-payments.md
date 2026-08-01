# Uploads, Payments and Message Helpers

← [Telethon-MCUB Extensions](index.md)

## Batch uploads

Telethon-MCUB adds `upload_files()` for batch upload workflows.

```python
files = await client.upload_files([
    "a.jpg",
    "b.mp4",
    "c.zip",
])
```

Use it when a module needs multiple uploaded handles before sending or building
other requests.

## Translation helper

Message objects expose `translate()`:

```python
translated = await message.translate("en")
```

## Star gifts / payments helpers

Telethon-MCUB exposes helpers for saved star gifts:

```python
gifts = await client.get_saved_gifts()
```

Upgrade a gift:

```python
await client.upgrade_gift(gift)
```

Internal helper:

```python
input_gift = client._get_input_stargift(gift)
```

These helpers are low-level Telegram-account features; prefer existing MCUB
modules if one already wraps the desired flow.
