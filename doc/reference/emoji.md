# Premium Emoji Guide

← [Index](../../API_DOC.md)

## Using Custom Emojis

MCUB supports Telegram premium custom emojis through the emoji parser.

### Basic Usage

```python
from utils import emoji_parser

text = emoji_parser.add_emoji("Hello", emoji_id=5368324170671202286)
await event.reply(text)
```

### Multiple Emojis

```python
text = "Start"
text = emoji_parser.add_emoji(text, emoji_id=5368324170671202286)
text += " Middle "
text = emoji_parser.add_emoji(text, emoji_id=5370869711888194012)
text += " End"

await event.reply(text)
```

### Parse Emoji Tags

```python
if emoji_parser.is_emoji_tag(text):
    parsed_text, entities = emoji_parser.parse_to_entities(text)
    await event.client.send_message(chat_id, parsed_text, entities=entities)
```

## Alternative Format (telethon-mcub)

MCUB also supports a simplified emoji format:

```html
<emoji document_id=5253884036924844372>📌</emoji>
```

This format works directly in messages and is automatically parsed by telethon-mcub.

## Finding Emoji IDs

1. Use [@ShowJsonBot](https://t.me/ShowJsonBot) to forward messages with custom emojis
2. Look for `custom_emoji_id` in the JSON response
3. Use the numeric ID in your code

Or:
1. Write `.py print(r_text)` in response to premium emoji
