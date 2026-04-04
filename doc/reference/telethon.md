# Telethon-MCUB Additional Methods

## Payments

- `get_saved_gifts()` — Get saved star gifts
- `upgrade_gift()` — Upgrade star gift
- `_get_input_stargift()` — Helper for parsing gift IDs

## Messages

- `translate()` — Translate message to specified language

## Uploads

- `upload_files()` — Batch file upload with parallel support

## Reactions

- `send_reaction(entity, message, reaction="👍", big=False, add_to_recent=True)` — Send reaction to message
- `get_message_reactions_list(entity, message, reaction=None, limit=100)` — Get list of users who reacted
- `set_default_reaction(reaction="👍")` — Set default reaction for new messages
- `set_chat_available_reactions(entity, reactions, reactions_limit=None, paid_enabled=None)` — Set available reactions for chat/channel
- `send_photo_as_private(entity, photo, caption=None, **kwargs)` — Send photo as private message

## Events

`events.JoinRequest` — New event for chat join requests

- `event.get_user()` — Get user who requested to join
- `event.get_users()` — Get all users who requested to join
- `event.approve()` — Approve join request
- `event.reject()` — Reject join request
- `event.approve_all()` — Approve all pending requests
- `event.reject_all()` — Reject all pending requests

## HTML Parser Extensions

- Added support for `<tg-spoiler>` tag
- Added support for `<emoji document_id="...">` tag
- Added support for `<tg-emoji>` tag

### Blockquote improvements

- `<blockquote>` — regular quote
- `<blockquote expandable>` — expandable quote (expanded by default)
- `<blockquote expandable="false">` — collapsed quote

[CHANGELOG](https://github.com/hairpin01/Telethon-MCUB/blob/v1/CHANGELOG.md)
