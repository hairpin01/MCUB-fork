# Telethon-MCUB Additional Methods

← [Index](../../API_DOC.md) · [Telethon-MCUB Extensions](../telethon/index.md)

> Rich message helpers, inline rich forms, media refs and examples are
> documented separately: [Rich Messages](../telethon/rich.md).

Detailed Telethon-MCUB pages:

- [Buttons and Premium Emoji](../telethon/buttons-emoji.md)
- [Parse Mode and Message Hooks](../telethon/parser-hooks.md)
- [Events and Reactions](../telethon/events-reactions.md)
- [Uploads, Payments and Message Helpers](../telethon/uploads-payments.md)
- [Compatibility Notes](../telethon/compat.md)
- [Inline Rich Forms and `Button.rich`](../telethon/rich-inline.md)
- [Rich Client Helpers](../telethon/rich-client.md)

## Payments

- `get_saved_gifts()` - Get saved star gifts
- `upgrade_gift()` - Upgrade star gift
- `_get_input_stargift()` - Helper for parsing gift IDs

## Messages

- `translate()` - Translate message to specified language

## Uploads

- `upload_files()` - Batch file upload with parallel support

## Reactions

- `send_reaction(entity, message, reaction="👍", big=False, add_to_recent=True)` - Send reaction to message
- `get_message_reactions_list(entity, message, reaction=None, limit=100)` - Get list of users who reacted
- `set_default_reaction(reaction="👍")` - Set default reaction for new messages
- `set_chat_available_reactions(entity, reactions, reactions_limit=None, paid_enabled=None)` - Set available reactions for chat/channel
- `send_photo_as_private(entity, photo, caption=None, **kwargs)` - Send photo as private message

## Events

`events.JoinRequest` - New event for chat join requests

- `event.get_user()` - Get user who requested to join
- `event.get_users()` - Get all users who requested to join
- `event.approve()` - Approve join request
- `event.reject()` - Reject join request
- `event.approve_all()` - Approve all pending requests
- `event.reject_all()` - Reject all pending requests

## HTML Parser Extensions

- Added support for `<tg-spoiler>` tag
- Added support for `<emoji document_id="...">` tag
- Added support for `<tg-emoji>` tag
- Added rich-message HTML rendering helpers:
  - `html.message_to_html(message)`
  - `html.rich_message_to_html(message.rich_message)`
  - rich media links (`tg://photo`, `tg://video`, `tg://audio`, `tg://document`)

See [Rich Messages](../telethon/rich.md) for complete examples.

### Blockquote improvements

- `<blockquote>` - regular quote
- `<blockquote expandable>` - expandable quote (expanded by default)
- `<blockquote expandable="false">` - collapsed quote

[CHANGELOG](https://github.com/hairpin01/Telethon-MCUB/blob/v1/CHANGELOG.md)
