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

### HTML examples

The value passed as `rich_text` is ordinary HTML-like markup. A single rich
message can contain several block types:

```python
rich = """
<h1>Release notes</h1>
<p><b>Rich HTML</b> supports <i>formatting</i>, links and spoilers.</p>
<ul>
  <li>Paragraphs and headings</li>
  <li><tg-spoiler>Hidden text</tg-spoiler></li>
</ul>
<blockquote expandable="false">A collapsed quote.</blockquote>
<pre language="python">print("hello")</pre>
<table>
  <tr><th align="left">Feature</th><th align="right">Status</th></tr>
  <tr><td>Rich HTML</td><td>Ready</td></tr>
</table>
"""

await self.subinline.rich_form(m.chat_id, rich)
```

Math, expandable details, and rich-page buttons use the same HTML source:

```python
rich = r"""
<p>Inline math: <tg-math>x^2 + y^2 = z^2</tg-math></p>
<tg-math-block>\int_0^1 x^2 dx</tg-math-block>
<details>
  <summary>Details</summary>
  <p>This content is revealed by the details block.</p>
</details>
<tg-button-row align="center">
  <tg-button type="url" url="https://example.com">Open docs</tg-button>
</tg-button-row>
"""
```

`<tg-button-row>` accepts `align="left"`, `align="center"`, or
`align="right"`; each row must contain 1 to 8 buttons. For callback buttons,
prefer `rich_buttons` and `self.Button.rich.inline(...)` so MCUB can register
and validate the callback token automatically (see [Inline Rich Forms](rich-inline.md)).

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
