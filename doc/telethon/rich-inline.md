# Inline Rich Forms and Articles

← [Telethon-MCUB Extensions](index.md) · [Rich Messages](rich.md)

## MCUB: `kernel.inline.rich_form()`

Use this from class-style MCUB modules. `self.subinline` is the class-style
alias for `self.kernel.inline`.

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

Normal reply-markup buttons work like normal inline forms:

```python
await self.subinline.rich_form(
    m.chat_id,
    r"""<h1>Confirm</h1><p>Choose an action</p>""",
    buttons=[{"text": "OK", "type": "callback", "data": "ok"}],
)
```

Rich page buttons are rendered inside the rich message. They reuse the guarded
CallbackQuery watcher and `kernel.inline_callback_map`; no extra watcher is
installed. Telegram receives only a UUID token. The callable and its
`args`/`kwargs` stay in the process. Tokens are reusable until their TTL
expires, not one-shot:

`self.Button.rich` supports `inline`, `url`, `text` (display-only), `switch`,
`input`, `copy`, `game`, `unknown`, `style`, and `row`. Phone, location, and
poll requests are not representable as rich page buttons; use normal
`buttons=[self.Button.request_phone(...)]`-style reply markup instead.

`rich.input("Ask", handler=...)` uses MCUB's existing temporary inline-input
registration. Its handler receives `(event, typed_text, data)`, like normal
`Button.input`:

```python
await self.subinline.rich_form(
    m.chat_id,
    "<p>Type a value</p>",
    rich_buttons=[self.Button.rich.input("Ask", handler=self.on_input)],
)
```

```python
await self.kernel.inline.rich_form(
    m.chat_id,
    r"""<h1>Confirm</h1><p>Choose an action</p>""",
    rich_buttons=[
        self.Button.rich.inline(
            "Run",
            handler=self.on_run,
            args=(1, 2, 3),
            kwargs={"foo": "bar"},
            ttl=900,
            style="success",
        ),
    ],
)
```

Use nested sequences for multiple rows, or
`self.Button.rich.row(..., align="left" | "center" | "right")` for an aligned
row. Each row must contain 1 to 8 buttons. Rich-page styles are `primary`,
`danger`, `success`, and `link`; labels and attributes are escaped. Callback
data is limited to 1 to 64 UTF-8 bytes. The whole rich block tree has a
recursive limit of 100 blocks.

`buttons` is normal reply markup. `rich_buttons` is `PageButtons` content
inside the rich message, and both may be supplied. `rich_buttons` require an
HTML string in `rich_text`, and cannot be combined with a prebuilt
`rich_message`. `KernelHandlers.rich_form`, `CodeInline.rich_form`, and
`InlineMessage.edit_rich` accept the same argument. For example:

```python
await call.edit_rich(
    "<p>Updated</p>",
    rich_buttons=[self.Button.rich.inline("Run", handler=self.on_run)],
)
```

The full signature is:

For a hand-written row, pass `html_tag=True`. It registers the same callback
once but returns only one escaped `<tg-button>` tag, so you must wrap it in a
`<tg-button-row>` yourself. Prefer `rich_buttons` for automatic row validation
and rendering:

```python
html = (
    "<h1>Manual row</h1><tg-button-row>"
    + self.Button.rich.inline(
        "Run",
        handler=self.on_run,
        args=(1, 2, 3),
        kwargs={"foo": "bar"},
        style="success",
        html_tag=True,
    )
    + "</tg-button-row>"
)
await self.subinline.rich_form(m.chat_id, html)
```

```python
await self.kernel.inline.rich_form(
    chat_id,
    rich_text=None,
    *,
    buttons=None,
    rich_buttons=None,
    auto_send=True,
    ttl=200,
    reply_to=None,
    rich_parse_mode="html",
    rich_message=None,
    text=None,
    parse_mode=None,
    rtl=None,
    noautolink=None,
    files=None,
    rich_media=None,
    **kwargs,
)
```

`rich_parse_mode` accepts `html`, `markdown`, or `md`. `text` is the normal
formatted fallback, defaulting to `rich_text`; `parse_mode` controls that
fallback. With `auto_send=False`, the form is prepared without sending it.
`ttl`, `reply_to`, media options, and other normal form options retain their
usual behavior. A callback may set `allow_user` and `allow_ttl`. Unloading a
module removes its tokens. Restarting the process expires all in-memory
tokens. Unknown or expired tokens are rejected by the existing callback
handler and are not reconstructed.

`Button.inline` creates a normal Telegram inline keyboard callback. It is
outside the rich page and uses normal reply markup. `Button.rich.inline`
creates a `PageBlockButtonRow` button embedded in the rich message.

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
