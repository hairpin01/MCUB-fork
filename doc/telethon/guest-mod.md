# Guest Mode for Bots

← [Telethon-MCUB Extensions](index.md) · [Events and Reactions](events-reactions.md)

Added in Telethon-MCUB `1.44.4`. Telegram Layer `229`.

Guest bots are bots that can be queried by `@username` from any non-secret
private chat, group or supergroup, even if they are not members of it. Telegram
sends the bot an `updateBotGuestChatQuery`, and the bot posts its answer into
the chat itself instead of sending a private message.

Telethon-MCUB adds `events.GuestMessage`, so `client.on` can handle both sides
of guest mode:

- the query a guest bot receives (`updateBotGuestChatQuery`, bot accounts);
- the message a guest bot posts (`message.guestchat_via_from`, userbots).

See <https://core.telegram.org/api/bots/guest-mode> for the Telegram side.

## Handling a guest query

```python
from telethon import events

@bot.on(events.GuestMessage)
async def handler(event):
    await event.reply(f"Hello, {event.text}!")
```

For a query, `reply()` does the only thing a guest bot is allowed to do: it
answers with `messages.setBotGuestChatResult`, which posts the message into the
chat where the bot was invoked.

With buttons:

```python
from telethon import Button

@bot.on(events.GuestMessage)
async def handler(event):
    await event.reply(
        "Pick one",
        buttons=[[Button.url("Docs", "https://core.telegram.org")]],
    )
```

## Handling messages posted by a guest bot

A userbot sees guest bot answers as ordinary new messages, with
`message.guestchat_via_from` set to the peer that invoked the bot:

```python
@client.on(events.GuestMessage)
async def handler(event):
    print(event.guestchat_via_from, event.text)
    await event.reply("Got it")
```

Here `reply()` is a normal reply into the chat, with `reply_to` already set.

## Filters

```python
@bot.on(events.GuestMessage(chats=-1001234567890, pattern="(?i)hello"))
async def handler(event):
    print(event.pattern_match.group(0))
```

| Argument | Meaning |
| --- | --- |
| `chats` | Chats/usernames/IDs to handle. Default: all chats |
| `blacklist_chats` | Treat `chats` as a blacklist instead of a whitelist |
| `from_users` | Only messages sent by these senders |
| `pattern` | String regex, compiled pattern or callable matched against the message text |
| `func` | Custom filter, receives the event |

Matching is done against the visible message text, so messages that carry a
rich message (and no plain text) are matched on their rendered text as well.

## Event members

| Member | Description |
| --- | --- |
| `message` | The message that triggered the bot, or the message posted by the bot |
| `query` | The original `UpdateBotGuestChatQuery`, `None` for posted messages |
| `query_id` | Query id to answer with, `None` if not a query |
| `qts` | `qts` of the query, `None` if not a query |
| `reference_messages` | Extra context messages sent with the query (for example replied-to messages) |
| `is_query` | `True` for `updateBotGuestChatQuery`, `False` for posted messages |
| `guestchat_via_from` | Peer that invoked the guest bot, set by Telegram on posted messages |
| `text` | Message text formatted as markdown |
| `pattern_match` | Result of the `pattern` argument, when one was given |
| `builder` | `InlineBuilder` instance for building the result to post |

Any other attribute of the underlying message (`sender_id`, `media`, `chat`,
`reply_to_msg_id`, …) is available directly on the event, so it can be used
like a `Message`.

## Reply helpers

| Method | Query (bot) | Posted message (userbot) |
| --- | --- | --- |
| `reply(text, **kwargs)` | Posts `text` into the chat via `setBotGuestChatResult` | Normal reply to the message |
| `respond(text, **kwargs)` | Same as `reply` | Sends to the chat without `reply_to` |
| `rich_reply(html=..., **kwargs)` | Posts an `InputBotInlineMessageRichMessage` | Normal reply via `client.send_rich_message` |
| `rich_respond(html=..., **kwargs)` | Same as `rich_reply` | Sends rich message without `reply_to` |
| `answer(result=None, **kwargs)` | Posts a ready `InputBotInlineResult` | Raises `RuntimeError` |

A query can only be answered once: further `reply`/`rich_reply`/`answer` calls
return `None` instead of failing.

`reply()` accepts `text`, `parse_mode`, `buttons`, `link_preview` and `title`
for queries, or any `client.send_message` argument for posted messages. The
`title` defaults to `None`, because guest bots normally post only the message
body.

## Rich messages

`rich_reply` takes the same rich inputs as the other rich helpers:

```python
@bot.on(events.GuestMessage)
async def handler(event):
    await event.rich_reply("<h1>Title</h1><p><b>Rich</b> body</p>")

@bot.on(events.GuestMessage)
async def markdown_handler(event):
    await event.rich_reply(markdown="# Title\n\n**Rich** body")
```

Options: `html`, `markdown`, `rich_message`, `title`, `buttons`, `rtl`,
`noautolink`, `files`, `rich_media`. Passing both `html` and `markdown` raises
`ValueError`.

`rich_media` works the same way as in inline rich forms, so a posted message can
embed media:

```python
@bot.on(events.GuestMessage)
async def handler(event):
    await event.rich_reply(
        '<p><a href="tg://photo?id=hero">Photo</a></p>',
        rich_media={"id": "hero", "media": "https://example.com/photo.jpg"},
    )
```

See [Rich Inline Forms](rich-inline.md) and [Rich Media References](rich-media.md)
for the rich message and media reference details.

## Media and custom results

`answer` takes any `InputBotInlineResult`, built with the event's `builder`:

```python
@bot.on(events.GuestMessage)
async def handler(event):
    await event.answer(event.builder.photo("photo.jpg", caption="Answer"))
```

Coroutines are awaited automatically, so `event.builder.article(...)` and
`event.builder.photo(...)` can be passed directly. Any other argument given to
`answer` is forwarded to `InlineBuilder.article`, which is useful for
`description`, `url`, `thumb`, `content`, `period`, `geo` and `contact`
results.

## Reference messages

Messages referenced by the triggering message (a replied-to message, for
example) are already initialized, so they can be read right away:

```python
@bot.on(events.GuestMessage)
async def handler(event):
    for message in event.reference_messages:
        print(message.id, message.text)
```

## Notes

- Guest bots post on behalf of the chat, so their answers are ordinary messages
  in that chat and can be replied to, edited or deleted by anyone who can.
- Only bots with the `bot_guestchat` flag can be invoked in guest mode.
- Guest mode is not available in secret chats or in groups with content
  protection enabled.