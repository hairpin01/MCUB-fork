# Compatibility Notes

← [Telethon-MCUB Extensions](index.md)

Telethon-MCUB includes compatibility changes used by MCUB modules and existing
module ecosystems.

## Reply topic headers

`utils.get_message_id(...)` accepts `MessageReplyHeader` objects. This fixes
forum/topic reply flows where `reply_to` is a header object instead of a raw
integer.

```python
await client.send_message(chat, "reply", reply_to=event.message.reply_to)
```

Telethon-MCUB extracts `reply_to_top_id` or `reply_to_msg_id` as needed.

## Dict-style buttons

Inline helpers preserve compatibility with dict-style buttons used by MCUB:

```python
buttons = [{"text": "Run", "type": "callback", "data": "run"}]
```

## `invert_media` and media aliases

The fork preserves MCUB compatibility changes around media send/edit flows,
including `invert_media` forwarding and reply media aliases.

## Rich-message fallback

Rich helpers can fall back to regular parsed text when a peer rejects native
`rich_message`. This keeps modules usable across chats where Telegram rich
messages are not accepted.

See also:

- [Rich Messages](rich.md)
- [Inline Rich Forms](rich-inline.md)
- [Rich Client Helpers](rich-client.md)
