# Telethon-MCUB Extensions

← [Index](../../API_DOC.md) · [Telethon-MCUB reference](../reference/telethon.md)

This section documents MCUB-facing features added by the Telethon-MCUB fork.

| Page | What it covers |
| --- | --- |
| [Rich Messages](rich.md) | Full rich-message overview and examples |
| [Rich Media References](rich-media.md) | `tg://photo/video/audio/document/media` links and `rich_media` |
| [Inline Rich Forms](rich-inline.md) | `kernel.inline.rich_form()`, `InlineBuilder.rich_article()`, rich page buttons and inline aliases |
| [Rich Client Helpers](rich-client.md) | `send_rich_message`, `edit_rich_message`, `Message.edit_rich` |
| [Rich HTML Rendering](rich-html.md) | `message_to_html`, `rich_message_to_html`, supported output blocks |
| [Buttons and Premium Emoji](buttons-emoji.md) | Unified Layer 229 buttons, `Button.*`, `Button.rich`, `Button.copy`, emoji icons |
| [Parse Mode and Message Hooks](parser-hooks.md) | auto parse mode, HTML parser tags, native message hooks |
| [Events and Reactions](events-reactions.md) | `events.JoinRequest`, reaction helpers |
| [Uploads, Payments and Message Helpers](uploads-payments.md) | `upload_files`, `translate`, star gift helpers |
| [Compatibility Notes](compat.md) | topic replies, dict buttons, media compatibility, fallback behavior |
| [Helper API Pack](helpers.md) | RichBuilder, inline aliases, message/client/topic shortcuts |

## Quick pick

- Writing an MCUB module? Start with [Inline Rich Forms](rich-inline.md).
- Need media inside rich HTML? See [Rich Media References](rich-media.md).
- Working directly with Telethon client methods? See [Rich Client Helpers](rich-client.md).
- Converting received rich messages back to HTML? See [Rich HTML Rendering](rich-html.md).
- Need non-rich additions? See [Buttons and Premium Emoji](buttons-emoji.md),
  [Parse Mode and Message Hooks](parser-hooks.md), and
  [Events and Reactions](events-reactions.md).

## Current fork

These pages target Telethon-MCUB `1.44.3`, Telegram Layer `229`. The public
`Button.*` helpers remain the supported API. Rich page buttons are documented
in [Inline Rich Forms](rich-inline.md), and compatibility details are in
[Compatibility Notes](compat.md).
