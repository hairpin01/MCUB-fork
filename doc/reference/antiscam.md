# AntiScamModules

Telethon-MCUB blocks dangerous account-level requests before sending them to Telegram.

## Blocked Requests

- `account.DeleteAccountRequest`
- `account.ResetPasswordRequest`
- `auth.ResetAuthorizationsRequest`
- `auth.LogOutRequest`

The check is recursive and also works for wrapped `Invoke*` containers.

## Example (blocked dangerous request)

```python
from telethon import functions
from telethon.client.protection import ScamModuleDetected

try:
    req = functions.InvokeWithoutUpdatesRequest(
        query=functions.InvokeWithTakeoutRequest(
            takeout_id=1,
            query=functions.account.DeleteAccountRequest(reason="test"),
        )
    )
    await kernel.client(req)
except ScamModuleDetected as e:
    print(e)
    # Method 'DeleteAccountRequest' blocked!
```

## System Dialog Masking

```python
r = await kernel.client.get_messages(777000, limit=1)
print(r[0].message)       # YldWdmR3PT0=
print(r[0].reply_markup)  # None
```
