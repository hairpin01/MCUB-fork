# Events and Reactions

← [Telethon-MCUB Extensions](index.md)

## Join request event

Telethon-MCUB adds `events.JoinRequest` for chat/channel join requests.

```python
from telethon import events

@client.on(events.JoinRequest)
async def handler(event):
    user = await event.get_user()
    await event.approve()
```

Useful methods:

- `event.get_user()`
- `event.get_users()`
- `event.approve()`
- `event.reject()`
- `event.approve_all()`
- `event.reject_all()`

## Reactions API

Send a reaction:

```python
await client.send_reaction(chat, message, reaction="👍", big=False)
```

Get users who reacted:

```python
users = await client.get_message_reactions_list(
    chat,
    message,
    reaction="👍",
    limit=100,
)
```

Set default reaction:

```python
await client.set_default_reaction("❤️")
```

Set available chat reactions:

```python
await client.set_chat_available_reactions(
    chat,
    reactions=["👍", "❤️", "🔥"],
    reactions_limit=10,
)
```

Send photo as private media:

```python
await client.send_photo_as_private(chat, photo, caption="private")
```
