# Rich Client Helpers

← [Telethon-MCUB Extensions](index.md) · [Rich Messages](rich.md)

Telethon-MCUB adds helpers for sending and editing Telegram rich messages.

## Send HTML rich message

```python
await client.send_rich_message(
    chat,
    html="<h1>Title</h1><p><b>Rich text</b></p>",
)
```

## Send Markdown rich message

```python
await client.send_rich_message(
    chat,
    markdown="# Title\n\n**Rich text**",
)
```

## Send prebuilt rich message

```python
await client.send_rich_message(
    chat,
    rich_message=input_rich_message,
)
```

## Edit rich message

```python
await client.edit_rich_message(
    chat,
    message_id,
    html="<h1>Updated</h1><p>New body</p>",
)
```

On message objects:

```python
await message.edit_rich(html="<b>Updated</b>")
```

## Fallback behavior

Some peers may reject `rich_message`. The helpers can fall back to a regular
parsed message/edit when Telegram returns a rich-message unsupported error.

Use fallback text explicitly when needed:

```python
await client.send_rich_message(
    chat,
    html="<h1>Title</h1>",
    fallback_text="<b>Title</b>",
    fallback_parse_mode="html",
)
```
