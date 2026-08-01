# Inline Rich Forms and Articles

← [Telethon-MCUB Extensions](index.md) · [Rich Messages](rich.md)

## MCUB: `self.subinline.rich_form()`

Use this from class-style MCUB modules:

```python
await self.subinline.rich_form(
    m.chat_id,
    "<h1>Title</h1><p><b>Rich text</b></p>",
)
```

Markdown:

```python
await self.subinline.rich_form(
    m.chat_id,
    "# Title\n\n**Rich text**",
    rich_parse_mode="markdown",
)
```

Buttons work like normal inline forms:

```python
await self.subinline.rich_form(
    m.chat_id,
    "<h1>Confirm</h1><p>Choose action</p>",
    buttons=[{"text": "OK", "type": "callback", "data": "ok"}],
)
```

Rich media:

```python
await self.subinline.rich_form(
    m.chat_id,
    '<a href="tg://media?id=clip">Video</a>',
    rich_media={"clip": "https://example.com/clip.mp4"},
)
```

## Telethon-MCUB: inline builder

```python
await event.answer([
    event.builder.rich_article(
        "Rich article",
        "<h1>Title</h1><p><b>Body</b></p>",
    )
])
```

Equivalent explicit call:

```python
await event.answer([
    event.builder.article(
        "Rich article",
        rich_text="<h1>Title</h1><p><b>Body</b></p>",
        rich_parse_mode="html",
    )
])
```

## Convenience helpers

Single article:

```python
await event.answer_article("Title", "Body")
```

Single rich article:

```python
await event.answer_article(
    "Rich",
    rich_text="<h1>Title</h1><p>Body</p>",
)
```

Pagination:

```python
results = [event.builder.article(str(i), text=str(i)) for i in range(100)]
await event.answer_page(results, limit=50)
```

Manual pagination:

```python
page, next_offset = event.paginate(results, limit=50)
await event.answer(page, next_offset=next_offset)
```
