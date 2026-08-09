# Rich HTML Rendering

← [Telethon-MCUB Extensions](index.md) · [Rich Messages](rich.md)

Telethon-MCUB extends `telethon.extensions.html` for received rich messages.

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
- unsupported placeholders.

Media blocks render as rich HTML links:

```html
<a href="tg://photo?id=123">[photo]</a>
<a href="tg://video?id=456">[video]</a>
<a href="tg://audio?id=789">[audio]</a>
```

Spoiler media labels are wrapped with `<tg-spoiler>`.
