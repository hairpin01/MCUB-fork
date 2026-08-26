# Rich HTML Rendering

← [Telethon-MCUB Extensions](index.md) · [Rich Messages](rich.md)

Telethon-MCUB extends `telethon.extensions.html` in two separate directions:
the parser converts HTML into Rich TL blocks, while the renderer converts a
received Rich TL message back into semantic HTML.

## HTML to Rich TL

Rich HTML supports paragraphs (`p`), headings, `pre` and `code`,
`tg-math` and `tg-math-block`, `mark` and `tg-spoiler`, unordered and ordered
lists and checklists, tables with `align` and `valign`, `details`,
`blockquote` and pull quotes, and `tg-button-row` with `tg-button` children.
Use raw Python strings for LaTeX so backslashes are preserved:

```python
rich = r"""<p><tg-math>\alpha + \beta</tg-math></p>"""
```

Text and attributes are escaped with `&lt;`, `&amp;`, and `&quot;` where
needed. Button URLs are restricted to `http`, `https`, or `tg` schemes.
Nested blocks are validated,
including the global recursive 100-block limit and the 1 to 8 button limit
per button row. Invalid or unmapped media becomes unsupported rather than a
usable media block. `<tg-thinking>` creates draft-only `PageBlockThinking` and
is rejected for inline results. `PageBlockUnsupported` is also rejected for
inline results, with `RICH_MESSAGE_BLOCK_UNSUPPORTED` indicating that a block
or its media mapping is not supported by the endpoint. Isolate blocks
incrementally when troubleshooting.

Callback data may be represented with `data-base64` when it is not valid UTF-8.
That is a compatibility detail of the HTML format, not a reason to construct
TL objects manually.

`message_to_html(...)` prefers `message.rich_message` when it contains blocks.
If there is no rich message, it falls back to normal:

```python
html.unparse(message.message, message.entities)
```

## Convert a raw rich object

```python
html_text = html.rich_message_to_html(message.rich_message)
```

## Supported output

The renderer supports rich text nodes and common page blocks:

- paragraphs;
- headings and subheadings;
- bold, italic, underline, strike, code, spoiler;
- links, email, phone, mentions, custom emoji;
- math/code/preformatted blocks;
- blockquotes and pullquotes;
- lists, ordered lists, checkbox list items;
- details blocks;
- tables;
- related articles;
- embeds and embed posts;
- maps and `InputPageBlockMap`;
- photo/video/audio/document media links;
- unsupported placeholders;
- semantic button rows: `<tg-button-row>` and `<tg-button>`;

Media blocks render as rich HTML links:

```html
<a href="tg://photo?id=123">[photo]</a>
<a href="tg://video?id=456">[video]</a>
<a href="tg://audio?id=789">[audio]</a>
```

Spoiler media labels are wrapped with `<tg-spoiler>`.
