# Rich Media References

← [Telethon-MCUB Extensions](index.md) · [Rich Messages](rich.md)

Rich HTML does not embed raw files directly. It references media by an id:

```html
<a href="tg://photo?id=hero">Photo</a>
<a href="tg://video?id=clip">Video</a>
<a href="tg://audio?id=song">Audio</a>
<a href="tg://document?id=file1">File</a>
```

The id (`hero`, `clip`, `song`, `file1`) is a string chosen by you. It must
match the corresponding media entry.

## MCUB: use `rich_media`

MCUB modules should use `rich_media` instead of manually importing Telethon TL
constructors:

```python
reply = await m.get_reply_message()

await self.subinline.rich_form(
    m.chat_id,
    '<a href="tg://photo?id=hero">Open photo</a>',
    rich_media={"hero": reply},
)
```

Accepted forms:

```python
rich_media={"hero": media}
```

```python
rich_media=[
    {"id": "hero", "media": media, "type": "photo"},
    {"id": "file1", "media": document, "type": "document"},
]
```

```python
rich_media=[("hero", media)]
```

Existing local files may be supplied as `str` paths or `pathlib.Path` objects.
MCUB uploads them through Telegram without reading the whole file into module
memory. The referenced `tg://...` type takes priority, so use a photo link for
an image and a document/video/audio link for other files:

```python
from pathlib import Path

hero = Path("assets") / "hero image.jpg"
await self.subinline.rich_form(
    m.chat_id,
    '<a href="tg://photo?id=hero">Open local photo</a>',
    rich_media={"hero": hero},
)
```

The path must exist and must be a file, not a directory. Image extensions
(`.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`) infer `photo` when no `tg://` type
or explicit media type is supplied; video and audio uploads are documents with
the corresponding rich reference type.

## URL media

For remote URLs, use the generic alias `tg://media?id=...`:

```python
await self.subinline.rich_form(
    m.chat_id,
    '<a href="tg://media?id=hero">Open video</a>',
    rich_media={"hero": "https://example.com/video.mp4"},
)
```

MCUB uploads the URL via Telegram and rewrites the link internally:

| URL extension | Rewritten link |
| --- | --- |
| `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif` | `tg://photo?id=...` |
| `.mp4`, `.mov`, `.m4v`, `.webm`, `.mkv` | `tg://video?id=...` |
| `.mp3`, `.ogg`, `.oga`, `.m4a`, `.wav`, `.flac` | `tg://audio?id=...` |
| anything else | `tg://document?id=...` |

## Raw Telethon-MCUB

If you are not using MCUB's `rich_media`, you can pass `rich_files` manually:

```python
from telethon.tl import types

await event.answer_article(
    "Photo",
    rich_text='<a href="tg://photo?id=hero">Photo</a>',
    rich_files=[types.InputRichFilePhoto("hero", input_photo)],
)
```

`id` is **not** a list index. It is the string id in `InputRichFilePhoto` or
`InputRichFileDocument`.

## Common mismatch

Bad:

```python
await self.subinline.rich_form(
    m.chat_id,
    '<a href="tg://photo?id=hero">Photo</a>',
    rich_media={"hero": document_or_video},
)
```

Good:

```python
await self.subinline.rich_form(
    m.chat_id,
    '<a href="tg://media?id=hero">Media</a>',
    rich_media={"hero": "https://example.com/video.mp4"},
)
```
