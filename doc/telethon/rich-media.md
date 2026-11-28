# Rich Media References

← [Telethon-MCUB Extensions](index.md) · [Rich Messages](rich.md)

Rich HTML does not embed raw files directly. It references media by an id:

```html
<img src="tg://photo?id=hero"/>
<a href="tg://video?id=clip">Video</a>
<a href="tg://audio?id=song">Audio</a>
<a href="tg://document?id=file1">File</a>
```

The id (`hero`, `clip`, `song`, `file1`) is a string chosen by you. It must
match the corresponding media entry. To embed a photo as a `PageBlockPhoto`, use `img src`; an anchor creates a text link instead.

## MCUB: use `rich_media`

MCUB modules should use `rich_media` instead of manually importing Telethon TL
constructors:

```python
reply = await m.get_reply_message()

await self.subinline.rich_form(
    m.chat_id,
    '<img src="tg://photo?id=hero"/>',
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

### Local file paths are supported

`rich_media` accepts existing local files as either a `str` path or a
`pathlib.Path`. MCUB uploads the file through Telegram; the path is not placed
inside the rich HTML and the whole file is not read into module memory. The
referenced `tg://...` type takes priority, so use an `img` tag for a photo block and
a document/video/audio link for other files:

```python
from pathlib import Path

hero = Path("assets") / "hero image.jpg"
await self.subinline.rich_form(
    m.chat_id,
    '<img src="tg://photo?id=hero"/>',
    rich_media={"hero": hero},
)
```

The equivalent string-path form is also valid:

```python
await self.subinline.rich_form(
    m.chat_id,
    '<a href="tg://document?id=report">Open report</a>',
    rich_media={"report": "/tmp/report.pdf"},
)
```

The path must exist and must be a file, not a directory. Image extensions
(`.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`) infer `photo` when no `tg://` type
or explicit media type is supplied; video and audio uploads are documents with
the corresponding rich reference type.

## URL media

For a remote image, use `tg://media?id=...` as the image source and put the HTTPS URL in `rich_media`:

```python
await self.subinline.rich_form(
    m.chat_id,
    '<img src="tg://media?id=hero"/>',
    rich_media={"hero": "https://example.com/photo.png"},
)
```

MCUB downloads the file, uploads it to Telegram and rewrites the reference based on the URL extension:

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
    rich_text='<img src="tg://photo?id=hero"/>',
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
    '<img src="tg://photo?id=hero"/>',
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
