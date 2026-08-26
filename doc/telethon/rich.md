# Rich Messages in Telethon-MCUB and MCUB

← [Index](../../API_DOC.md) · [Telethon-MCUB Extensions](index.md) · [Telethon-MCUB reference](../reference/telethon.md) · [Inline Form](../inline/inline-form.md)

This page documents the rich-message features added on top of Telethon-MCUB and
how MCUB modules should use them.

The documented baseline is Telethon-MCUB `1.44.3` and Telegram Layer `229`.
For inline forms, see [Inline Rich Forms](rich-inline.md), including
`rich_buttons` and `self.Button.rich.inline`.

Rich messages are Telegram messages backed by `InputRichMessage` instead of a
plain text string with normal `MessageEntity` formatting. They support structured
blocks, richer HTML/Markdown sources, and media references inside the rich text.

Related pages:

- [Rich Media References](rich-media.md)
- [Inline Rich Forms and Articles](rich-inline.md)
- [Rich Client Helpers](rich-client.md)
- [Rich HTML Rendering](rich-html.md)

---

## Quick MCUB usage

For MCUB modules, prefer `self.subinline.rich_form(...)` when you want to show a
rich message through inline mode.

```python
await self.subinline.rich_form(
    m.chat_id,
    "<h1>Title</h1><p><b>Rich text</b></p>",
)
```

Markdown is supported too:

```python
await self.subinline.rich_form(
    m.chat_id,
    "# Title\n\n**Rich text**",
    rich_parse_mode="markdown",
)
```

### Rich form with callback edit

Inline callbacks receive MCUB's inline message object, so callback handlers can
edit the already-opened inline form with rich formatting:

```python
@loader.callback  # loader -> core.lib.loader.module_base
async def on_menu(self, call, data=None) -> None:
    await call.edit_rich(
        "<h1>menu</h1>",
        rich_buttons=[self.Button.rich.inline("Refresh", handler=self.on_menu)],
        fallback=False,  # keep real Telegram errors visible while debugging
    )


await self.subinline.rich_form(
    m.chat_id,
    "open menu",
    buttons=[
        [
            self.Button.inline(
                "click",
                self.on_menu,
                style="success",
            )
        ]
    ],
)
```

---

## Rich media in MCUB without TL boilerplate

You do **not** need to manually write `types.InputRichFilePhoto(...)` in modules.
Use `rich_media`:

```python
reply = await m.get_reply_message()

await self.subinline.rich_form(
    m.chat_id,
    '<h1>Photo</h1><a href="tg://photo?id=hero">Open photo</a>',
    rich_media={"hero": reply},
)
```

The key (`"hero"`) is the same id used in the `tg://...` link. It is **not** a
list index.

### Remote URL media

Remote URLs are supported through `tg://media?id=...`. MCUB uploads the URL via
Telegram, infers the media type from the extension, and rewrites the link to the
real rich media scheme:

```python
await self.subinline.rich_form(
    m.chat_id,
    '<h1>Video</h1><a href="tg://media?id=hero">Open video</a>',
    rich_media={"hero": "https://example.com/video.mp4"},
)
```

For a `.mp4` URL, MCUB rewrites the HTML internally to:

```html
<a href="tg://video?id=hero">Open video</a>
```

Supported inferred types:

| URL extension | Rich scheme |
| --- | --- |
| `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif` | `tg://photo?id=...` |
| `.mp4`, `.mov`, `.m4v`, `.webm`, `.mkv` | `tg://video?id=...` |
| `.mp3`, `.ogg`, `.oga`, `.m4a`, `.wav`, `.flac` | `tg://audio?id=...` |
| anything else | `tg://document?id=...` |

You can also be explicit:

```python
await self.subinline.rich_form(
    m.chat_id,
    '<a href="tg://video?id=clip">Clip</a>',
    rich_media=[{"id": "clip", "media": "https://example.com/clip.mp4", "type": "video"}],
)
```

### Accepted `rich_media` shapes

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

`media` may be an existing Telegram media object, message/media object, or a
remote HTTP(S) URL. Local paths are not silently converted here; upload the file
or send/reply to it first if you need a Telegram media object.

---

## Telethon-MCUB: sending rich messages

Telethon-MCUB exposes high-level helpers for direct rich messages.

```python
await client.send_rich_message(
    chat,
    html="<h1>Title</h1><p><b>Rich text</b></p>",
)
```

Markdown:

```python
await client.send_rich_message(
    chat,
    markdown="# Title\n\n**Rich text**",
)
```

With a prebuilt rich message:

```python
await client.send_rich_message(
    chat,
    rich_message=my_input_rich_message,
)
```

If Telegram rejects rich messages for a peer, the helper can fall back to a
regular parsed text message.

---

## Telethon-MCUB: editing rich messages

```python
await client.edit_rich_message(
    chat,
    message_id,
    html="<h1>Updated</h1><p>New body</p>",
)
```

On `Message` objects:

```python
await message.edit_rich(html="<b>Updated</b>")
```

Fallback to normal `edit_message` is supported for peers that reject
`rich_message` edits.

---

## Inline rich articles

Telethon-MCUB inline builder can create rich articles directly:

```python
await event.answer([
    event.builder.rich_article(
        "Rich article",
        "<h1>Title</h1><p><b>Rich text</b></p>",
    )
])
```

Equivalent explicit form:

```python
await event.answer([
    event.builder.article(
        "Rich article",
        rich_text="<h1>Title</h1><p><b>Rich text</b></p>",
        rich_parse_mode="html",
    )
])
```

Rich article parameters:

| Parameter | Meaning |
| --- | --- |
| `rich_text` | HTML or Markdown source |
| `rich_parse_mode` | `"html"`, `"markdown"`, or `"md"` |
| `rich_message` | prebuilt `InputRichMessage` |
| `rich_rtl` | render right-to-left |
| `rich_noautolink` | disable automatic link detection |
| `rich_files` | explicit `InputRichFilePhoto/InputRichFileDocument` refs |

---

## Inline query convenience helpers

Telethon-MCUB adds helpers for common inline handlers.

Single article:

```python
await event.answer_article(
    "Title",
    "Plain text body",
)
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

Manual slicing:

```python
page, next_offset = event.paginate(results, limit=50)
await event.answer(page, next_offset=next_offset)
```

---

## Rich HTML media links

Rich HTML references media through `tg://...` links.

```html
<a href="tg://photo?id=hero">Photo</a>
<a href="tg://video?id=clip">Video</a>
<a href="tg://audio?id=song">Audio</a>
<a href="tg://document?id=file1">File</a>
```

In raw Telethon-MCUB, the id must match an `InputRichFile*` object:

```python
from telethon.tl import types

await event.answer_article(
    "Photo",
    rich_text='<a href="tg://photo?id=hero">Photo</a>',
    rich_files=[
        types.InputRichFilePhoto("hero", input_photo),
    ],
)
```

In MCUB modules, prefer `rich_media` to avoid this boilerplate.

---

## Rendering received rich messages back to HTML

Telethon-MCUB extends `telethon.extensions.html` with rich-message rendering:

```python
from telethon.extensions import html

text = html.message_to_html(message)
```

`message_to_html(...)` prefers `message.rich_message` when available, and falls
back to normal `html.unparse(message.message, message.entities)` otherwise.

Direct rich object rendering:

```python
html_text = html.rich_message_to_html(message.rich_message)
```

Supported rich blocks include paragraphs, headings, quotes, code/math blocks,
lists, checkbox list items, details, tables, related articles, embeds, maps,
media blocks, unsupported placeholders, and media links such as:

```html
<a href="tg://photo?id=123">[photo]</a>
<a href="tg://video?id=456">[video]</a>
<a href="tg://audio?id=789">[audio]</a>
```

---

## Common errors

### `RICH_MESSAGE_DOCUMENT_INVALID`

Usually means the HTML asks for one media type, but the attached rich file is a
different type.

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

or explicit:

```python
await self.subinline.rich_form(
    m.chat_id,
    '<a href="tg://video?id=hero">Video</a>',
    rich_media={"hero": video_or_url},
)
```

### Empty inline result / normal text fallback

Some inline adapters cannot answer with native Telegram rich messages. MCUB falls
back to a regular formatted article where possible. If native rich mode is
required, make sure the inline query is handled by Telethon-MCUB, not a pure Bot
API adapter.

---

## Related files

- [Inline Form](../inline/inline-form.md)
- [Class-style modules](../registration/class-style.md)
- [Telethon-MCUB additional methods](../reference/telethon.md)
- [Telethon-MCUB changelog](https://github.com/hairpin01/Telethon-MCUB/blob/v1/CHANGELOG.md)
