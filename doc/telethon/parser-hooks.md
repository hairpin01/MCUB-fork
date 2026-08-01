# Parse Mode, HTML Parser and Message Hooks

← [Telethon-MCUB Extensions](index.md)

## Auto-detect `parse_mode`

When `parse_mode` is not explicitly passed, Telethon-MCUB can inspect message
content and choose a parser automatically.

HTML-like input:

```python
await client.send_message(chat, "<b>bold</b>")
```

Markdown-like input:

```python
await client.send_message(chat, "**bold**")
```

Explicit `parse_mode` still wins:

```python
await client.send_message(chat, "**not markdown**", parse_mode=None)
```

If both HTML and Markdown markers are present, HTML wins.

## HTML parser additions

The HTML parser supports MCUB/Telegram formatting tags including:

- `<tg-spoiler>` / `<spoiler>`
- `<tg-emoji emoji-id="...">...</tg-emoji>`
- `<emoji document_id="...">...</emoji>`
- heading tags `<h1>` ... `<h6>` as bold block-style text
- `<blockquote>` and expandable blockquote variants

Example:

```python
await client.send_message(
    chat,
    '<blockquote expandable="false">Hidden quote</blockquote>',
    parse_mode="html",
)
```

## Native message hook pipeline

Telethon-MCUB adds a pre-handler hook pipeline:

```python
def hook(event):
    # return False to stop propagation
    return True

client.add_message_hook(hook, priority=10)
client.remove_message_hook(hook)
```

Hooks run before regular event handlers. Higher priority runs earlier.

This is intended for MCUB's command dispatcher and other low-level pipeline
consumers. Normal modules usually do not need to register hooks directly.
