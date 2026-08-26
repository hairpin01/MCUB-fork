# Inline Result Builders

← [Index](../../API_DOC.md)

Helper functions for building inline query results. Located in:

- `core_inline/api/core.py` - Result builders (article, photo, video, document, audio)
- `core_inline/api/inline.py` - Keyboard and button builders

Import them in your module:

```python
from core_inline.api.core import (
    build_inline_result_text,
    build_inline_result_photo,
    build_inline_result_video,
    build_inline_result_document,
    build_inline_result_audio,
)
from core_inline.api.inline import (
    build_inline_keyboard,
    build_inline_button,
    make_cb_button,
    cleanup_inline_callback_map,
)
```

---

## Result Builders

### `build_inline_result_text(title, text, description=None, parse_mode="HTML", result_id=None) -> dict`

Build an inline `article` result.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `title` | `str` | - | Result title |
| `text` | `str` | - | Message text content |
| `description` | `str \| None` | `None` | Short description (falls back to text[:200]) |
| `parse_mode` | `str` | `"HTML"` | Parse mode for text |
| `result_id` | `str \| None` | auto UUID | Unique result ID |

```python
result = build_inline_result_text(
    title="Search Result",
    text="<b>Hello</b> world",
    description="A greeting",
)
```

### `build_inline_result_photo(photo_url, text, title, description=None, parse_mode="HTML", thumb_url=None, result_id=None) -> dict`

Build an inline `photo` result.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `photo_url` | `str` | - | URL of the photo to display |
| `text` | `str` | - | Caption |
| `title` | `str` | - | Result title |
| `description` | `str \| None` | `None` | Short description |
| `parse_mode` | `str` | `"HTML"` | Parse mode |
| `thumb_url` | `str \| None` | `photo_url` | Thumbnail URL |
| `result_id` | `str \| None` | auto UUID | Unique result ID |

### `build_inline_result_video(video_url, text, title, mime_type="video/mp4", thumb_url=None, description=None, parse_mode="HTML", result_id=None) -> dict`

Build an inline `video` result.

### `build_inline_result_document(document_url, text, title, mime_type="application/octet-stream", thumb_url=None, description=None, parse_mode="HTML", result_id=None) -> dict`

Build an inline `document` result.

### `build_inline_result_audio(audio_url, text, title, performer="Unknown", duration=None, thumb_url=None, description=None, parse_mode="HTML", result_id=None) -> dict`

Build an inline `audio` result.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `audio_url` | `str` | - | URL of the audio file |
| `text` | `str` | - | Caption |
| `title` | `str` | - | Result title |
| `performer` | `str` | `"Unknown"` | Performer name |
| `duration` | `int \| None` | `None` | Duration in seconds |
| `thumb_url` | `str \| None` | `None` | Thumbnail URL |
| `description` | `str \| None` | `None` | Short description |
| `parse_mode` | `str` | `"HTML"` | Parse mode |
| `result_id` | `str \| None` | auto UUID | Unique result ID |

---

## Keyboard Builders

### `build_inline_keyboard(rows, resize=None, one_time=None) -> dict`

Convert a list of Telethon Button objects into an inline keyboard JSON dict.

```python
from telethon import Button

buttons = [
    [Button.inline("Yes", b"yes"), Button.inline("No", b"no")],
    [Button.url("Cancel", "https://example.com")],
]

keyboard = build_inline_keyboard(buttons)
# -> {"inline_keyboard": [[...], [...]]}
```

### `build_inline_button(btn) -> dict | None`

Convert a single Telethon Button to JSON dict. Supports:
- `KeyboardInlineButton.type` variants `InlineButtonTypeCallback`,
  `InlineButtonTypeUrl`, `InlineButtonTypeSwitchInline`, `InlineButtonTypeGame`,
  `InlineButtonTypeCopy`, and `InlineButtonTypeWebView` map to inline-button
  output such as `{"text": "...", "callback_data": "..."}` and
  `{"text": "...", "url": "..."}`.
- `KeyboardButton.type` variants include `ButtonTypeDefault`,
  `ButtonTypeRequestPhone`, `ButtonTypeRequestGeoLocation`,
  `ButtonTypeRequestPeer`, `ButtonTypeRequestPoll`, and
  `ButtonTypeSimpleWebView`; for example, phone and location map to
  `{"text": "...", "request_contact": true}` and
  `{"text": "...", "request_location": true}`.

This is the current Layer-229 unified model. Users should use public
`Button.*` helpers rather than constructing these TL objects manually.

Emoji icons are extracted from button styles when available.

---

## Callback Token Helpers

`InlineBuilder.article(...)` accepts `rich_text`, `rich_parse_mode` (`html`,
`markdown`, or `md`), `rich_message`, `rich_rtl`, `rich_noautolink`,
`rich_files`, and `rich_media`. `InlineBuilder.rich_article(...)` is the
shorter rich wrapper. These are regular keyword arguments, not a
special dictionary-only feature.

`InlineQuery.Event.answer_rich(title, rich_text=None, **kwargs)` aliases
`answer_article` with rich text. `answer_text` and `answer_media` are also
available aliases.

### `make_cb_button(kernel, text, callback, args=None, kwargs=None, ttl=900, icon=None, style="primary", token=None) -> dict`

Create a callback button with auto-generated secure token. See [Inline Form](inline-form.md) for full documentation.

```python
async def on_click(event, user_id):
    await event.answer(f"Hi {user_id}!", alert=True)

btn = make_cb_button(
    kernel,
    "Say Hi",
    on_click,
    args=[123],
    kwargs={"foo": "bar"},
    ttl=600,
    style="primary",
)
```

### `cleanup_inline_callback_map(kernel)`

Remove expired entries from the inline callback token map. Called automatically when creating forms and on button press, but can be invoked manually.
