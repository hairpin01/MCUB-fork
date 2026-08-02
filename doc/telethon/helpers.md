# Telethon-MCUB Helper API Pack

← [Telethon-MCUB Extensions](index.md)

This page lists small convenience helpers added in Telethon-MCUB for MCUB-style
module code.

## Rich/text builders

```python
from telethon import custom

html = str(
    custom.RichBuilder()
    .h1("Title")
    .p("Body")
    .quote("Expandable quote", expandable=True)
    .ul(["first", "second"])
    .table([["A", "B"]], headers=["left", "right"])
    .media("Video", "clip", kind="video")
)
```

Formatting methods include:

- headings: `h1` ... `h6`;
- inline formatting: `bold`/`b`, `italic`/`i`, `underline`/`u`, `strike`/`s`,
  `sub`/`sup`, `code`, `spoiler`;
- blocks: `p`, `pre`, `quote`/`blockquote`, `details`, `ul`, `ol`, `table`,
  `br`, `hr`;
- `checklist` renders a visual `[x]`/`[ ]` list only; Telegram rich HTML input
  does not reliably create native checkbox blocks from HTML.
- links/media: `link(...)`, `media(text, id, kind="media")`.

## Inline shortcuts

```python
await event.answer_text("Title", "Body")
await event.answer_rich("Rich", "<h1>Title</h1>")
await event.answer_media("File", file, media_type="document")
```

`InlineBuilder.article(...)` and `rich_article(...)` also accept `rich_media`:

```python
await event.answer_rich(
    "Video",
    '<a href="tg://media?id=clip">Video</a>',
    rich_media={"clip": "https://example.com/video.mp4"},
)
```

## Message shortcuts

```python
await message.safe_edit("new text")
await message.react("🔥")
await message.unreact()
```

## Client shortcuts

```python
await client.safe_send_message(chat, "text")
await client.send_album(chat, ["a.jpg", "b.jpg"], captions=["A", "B"])
```

## Topic shortcuts

```python
await client.send_to_topic(chat, topic, "hello")
await client.reply_topic(event, "reply in same topic")
```
