# SPDX-License-Identifier: MIT
# Telegram API Web Plugin for MCUB

from __future__ import annotations

import ast
import contextlib
import io
import os
import logging
import pprint
import time
import traceback
from typing import TYPE_CHECKING, Any

from aiohttp import web

from core.web import app_keys
from core.web.auth import require_auth

if TYPE_CHECKING:
    from core.lib.types import Kernel

logger = logging.getLogger(__name__)


def _json_success(data: Any, meta: dict | None = None) -> web.Response:
    response = {"data": data}
    if meta:
        response["meta"] = meta
    return web.json_response(response)


def _json_error(
    message: str,
    code: str = "BAD_REQUEST",
    status: int = 400,
    details: list | None = None,
) -> web.Response:
    error = {"code": code, "message": message}
    if details:
        error["details"] = details
    return web.json_response({"error": error}, status=status)


def _get_client(app: web.Application) -> tuple[Any, web.Response | None]:
    kernel = app.get(app_keys.KERNEL)
    if kernel is None:
        return None, _json_error(
            "Kernel is not available", code="KERNEL_UNAVAILABLE", status=503
        )
    client = getattr(kernel, "client", None)
    if client is None:
        return None, _json_error(
            "Telegram client is not available",
            code="CLIENT_UNAVAILABLE",
            status=503,
        )
    return client, None


def _serialize_message(msg: Any) -> dict:
    if msg is None:
        return {}
    chat_id = None
    sender_id = None
    try:
        chat_id = msg.chat_id
    except Exception:
        pass
    try:
        sender_id = msg.sender_id
    except Exception:
        pass

    # reply info
    reply_to = None
    try:
        rt = getattr(msg, "reply_to", None)
        if rt is not None and getattr(rt, "reply_to_msg_id", None):
            reply_to = {"id": rt.reply_to_msg_id}
    except Exception:
        pass

    # media info
    media = None
    try:
        m = getattr(msg, "media", None)
        if m is not None and type(m).__name__ != "MessageMediaWebPage":
            tname = type(m).__name__  # e.g. MessageMediaPhoto
            mtype = tname.replace("MessageMedia", "").lower() or "media"
            finfo = {}
            fobj = getattr(msg, "file", None)
            if fobj is not None:
                if getattr(fobj, "name", None):
                    finfo["name"] = fobj.name
                if getattr(fobj, "mime_type", None):
                    finfo["mime_type"] = fobj.mime_type
                if getattr(fobj, "size", None):
                    finfo["size"] = fobj.size
            media = {"type": mtype, **finfo}
    except Exception:
        pass

    # buttons info
    buttons = []
    bstyle = ""
    try:
        rm = getattr(msg, "reply_markup", None)
        if rm is not None:
            bstyle = "inline" if "Inline" in type(rm).__name__ else "reply"
        btns = getattr(msg, "buttons", None)
        if btns:
            idx = 0
            for row in btns:
                for b in row:
                    if b is not None:
                        buttons.append({
                            "index": idx,
                            "text": getattr(b, "text", ""),
                            "style": bstyle,
                        })
                    idx += 1
    except Exception:
        pass

    serialized = {
        "id": getattr(msg, "id", None),
        "chat_id": chat_id,
        "sender_id": sender_id,
        "text": getattr(msg, "raw_text", getattr(msg, "text", "")),
        "date": str(getattr(msg, "date", "")),
    }
    if reply_to is not None:
        serialized["reply_to"] = reply_to
    if media is not None:
        serialized["media"] = media
    if buttons:
        serialized["buttons"] = buttons
    return serialized


_NO_RETURN = object()


def _compile_exec_function(code: str):
    """Compile code into an async __exec() function (same pattern as evaluator)."""
    tree = ast.parse(code or "pass", mode="exec")
    body = list(tree.body)
    if body and isinstance(body[-1], ast.Expr):
        body[-1] = ast.copy_location(ast.Return(value=body[-1].value), body[-1])
    body.append(ast.Return(value=ast.Name(id="_NO_RETURN", ctx=ast.Load())))

    fn = ast.AsyncFunctionDef(
        name="__exec",
        args=ast.arguments(
            posonlyargs=[],
            args=[],
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=None,
            defaults=[],
        ),
        body=body,
        decorator_list=[],
    )
    module = ast.Module(body=[fn], type_ignores=[])
    ast.fix_missing_locations(module)
    return compile(module, "<exec_telegram>", "exec")


def _format_exec_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    width = 1 if isinstance(value, (dict, list, tuple, set, frozenset)) else 88
    return pprint.pformat(value, width=width, compact=False, sort_dicts=False)


@require_auth
async def send_message(request: web.Request) -> web.Response:
    client, err = _get_client(request.app)
    if err:
        return err

    try:
        payload = await request.json()
    except Exception:
        return _json_error("Invalid JSON body", code="INVALID_JSON", status=400)

    chat = payload.get("chat") or payload.get("peer") or payload.get("entity")
    text = payload.get("text") or payload.get("message")

    if not chat:
        return _json_error(
            "Missing required field 'chat'", code="MISSING_FIELD", status=400
        )
    if text is None:
        return _json_error(
            "Missing required field 'text'", code="MISSING_FIELD", status=400
        )

    reply_to = payload.get("reply_to")
    silent = payload.get("silent", False)

    kwargs = {}
    if reply_to is not None:
        kwargs["reply_to"] = int(reply_to)
    if silent:
        kwargs["silent"] = True

    try:
        target_entity = "me" if str(chat).lower() in ("me", "self") else chat
        try:
            target_entity = int(target_entity)
        except (ValueError, TypeError):
            pass

        msg = await client.send_message(target_entity, str(text), **kwargs)
        return _json_success({"success": True, "message": _serialize_message(msg)})
    except Exception as e:
        logger.error("Failed to send message: %s", e, exc_info=True)
        return _json_error(str(e), code="SEND_FAILED", status=500)


@require_auth
async def edit_message(request: web.Request) -> web.Response:
    client, err = _get_client(request.app)
    if err:
        return err

    try:
        payload = await request.json()
    except Exception:
        return _json_error("Invalid JSON body", code="INVALID_JSON", status=400)

    chat = payload.get("chat") or payload.get("peer") or payload.get("entity")
    message_id = payload.get("message_id") or payload.get("message")
    text = payload.get("text")

    if not chat:
        return _json_error(
            "Missing required field 'chat'", code="MISSING_FIELD", status=400
        )
    if not message_id:
        return _json_error(
            "Missing required field 'message_id'",
            code="MISSING_FIELD",
            status=400,
        )
    if text is None:
        return _json_error(
            "Missing required field 'text'", code="MISSING_FIELD", status=400
        )

    try:
        target_entity = "me" if str(chat).lower() in ("me", "self") else chat
        try:
            target_entity = int(target_entity)
        except (ValueError, TypeError):
            pass

        msg = await client.edit_message(
            target_entity, int(message_id), str(text)
        )
        return _json_success({"success": True, "message": _serialize_message(msg)})
    except Exception as e:
        logger.error("Failed to edit message: %s", e, exc_info=True)
        return _json_error(str(e), code="EDIT_FAILED", status=500)


@require_auth
async def delete_messages(request: web.Request) -> web.Response:
    client, err = _get_client(request.app)
    if err:
        return err

    try:
        payload = await request.json()
    except Exception:
        return _json_error("Invalid JSON body", code="INVALID_JSON", status=400)

    chat = payload.get("chat") or payload.get("peer") or payload.get("entity")
    message_ids = (
        payload.get("message_ids")
        or payload.get("ids")
        or payload.get("message_id")
    )

    if not chat:
        return _json_error(
            "Missing required field 'chat'", code="MISSING_FIELD", status=400
        )
    if not message_ids:
        return _json_error(
            "Missing required field 'message_ids'",
            code="MISSING_FIELD",
            status=400,
        )

    if isinstance(message_ids, (int, str)):
        message_ids = [int(message_ids)]
    else:
        message_ids = [int(i) for i in message_ids]

    revoke = payload.get("revoke", True)

    try:
        target_entity = "me" if str(chat).lower() in ("me", "self") else chat
        try:
            target_entity = int(target_entity)
        except (ValueError, TypeError):
            pass

        await client.delete_messages(target_entity, message_ids, revoke=revoke)
        return _json_success({"success": True, "deleted_ids": message_ids})
    except Exception as e:
        logger.error("Failed to delete messages: %s", e, exc_info=True)
        return _json_error(str(e), code="DELETE_FAILED", status=500)


@require_auth
async def get_me(request: web.Request) -> web.Response:
    client, err = _get_client(request.app)
    if err:
        return err

    try:
        me = await client.get_me()
        return _json_success(
            {
                "id": getattr(me, "id", None),
                "first_name": getattr(me, "first_name", None),
                "last_name": getattr(me, "last_name", None),
                "username": getattr(me, "username", None),
                "phone": getattr(me, "phone", None),
                "is_bot": getattr(me, "bot", False),
            }
        )
    except Exception as e:
        logger.error("Failed to get me: %s", e, exc_info=True)
        return _json_error(str(e), code="GET_ME_FAILED", status=500)


@require_auth
async def get_messages(request: web.Request) -> web.Response:
    client, err = _get_client(request.app)
    if err:
        return err

    chat = (
        request.query.get("chat")
        or request.query.get("chat_id")
        or request.query.get("peer")
        or request.query.get("entity")
    )
    if not chat:
        try:
            body = await request.json()
            chat = (
                body.get("chat")
                or body.get("chat_id")
                or body.get("peer")
                or body.get("entity")
            )
            limit = body.get("limit", 10)
        except Exception:
            limit = 10
    else:
        limit = request.query.get("limit", 10)

    if not chat:
        return _json_error(
            "Missing required param 'chat'", code="MISSING_FIELD", status=400
        )

    try:
        limit = max(1, min(100, int(limit)))
    except (ValueError, TypeError):
        limit = 10

    try:
        target_entity = "me" if str(chat).lower() in ("me", "self") else chat
        try:
            target_entity = int(target_entity)
        except (ValueError, TypeError):
            pass

        messages = await client.get_messages(target_entity, limit=limit)
        serialized = [_serialize_message(m) for m in messages]
        # enrich reply previews with parent message text
        reply_ids = sorted({
            m["reply_to"]["id"]
            for m in serialized
            if isinstance(m.get("reply_to"), dict) and m["reply_to"].get("id")
        })
        parents = {}
        if reply_ids:
            fetched = await client.get_messages(target_entity, ids=reply_ids)
            for pm in fetched:
                if pm is not None:
                    parents[pm.id] = {
                        "id": pm.id,
                        "sender_id": getattr(pm, "sender_id", None),
                        "text": (getattr(pm, "raw_text", None) or getattr(pm, "text", None) or "")[:120],
                    }
        for m in serialized:
            rt = m.get("reply_to")
            if isinstance(rt, dict) and rt.get("id") in parents:
                rt["preview"] = parents[rt["id"]]
        return _json_success(serialized, meta={"count": len(serialized), "limit": limit})
    except Exception as e:
        logger.error("Failed to get messages: %s", e, exc_info=True)
        return _json_error(str(e), code="GET_MESSAGES_FAILED", status=500)


@require_auth
async def get_unread_messages(request: web.Request) -> web.Response:
    client, err = _get_client(request.app)
    if err:
        return err

    try:
        limit_dialogs = max(1, min(100, int(request.query.get("limit_dialogs", 20))))
    except (ValueError, TypeError):
        limit_dialogs = 20

    specific_chat = request.query.get("chat") or request.query.get("peer")

    try:
        from telethon import utils
        results = []
        if specific_chat:
            target_entity = "me" if str(specific_chat).lower() in ("me", "self") else specific_chat
            try:
                target_entity = int(target_entity)
            except (ValueError, TypeError):
                pass

            entity = await client.get_entity(target_entity)
            entity_id = utils.get_peer_id(entity)
            unread_count = 0
            async for dialog in client.iter_dialogs(limit=50):
                if dialog.id == entity_id:
                    unread_count = dialog.unread_count
                    break
            
            fetch_limit = min(max(unread_count, 1), 20)
            messages = await client.get_messages(target_entity, limit=fetch_limit)
            results.append({
                "chat_id": entity_id,
                "title": getattr(entity, "title", getattr(entity, "first_name", str(entity_id))),
                "unread_count": unread_count,
                "messages": [_serialize_message(m) for m in messages]
            })
        else:
            async for dialog in client.iter_dialogs(limit=limit_dialogs):
                if dialog.unread_count > 0:
                    fetch_count = min(dialog.unread_count, 10)
                    msgs = await client.get_messages(dialog.input_entity, limit=fetch_count)
                    results.append({
                        "chat_id": dialog.id,
                        "title": dialog.name,
                        "unread_count": dialog.unread_count,
                        "unread_mentions_count": dialog.unread_mentions_count,
                        "messages": [_serialize_message(m) for m in msgs]
                    })
        return _json_success(results, meta={"chats_count": len(results)})
    except Exception as e:
        logger.error("Failed to get unread messages: %s", e, exc_info=True)
        return _json_error(str(e), code="GET_UNREAD_FAILED", status=500)


@require_auth
async def create_chat(request: web.Request) -> web.Response:
    client, err = _get_client(request.app)
    if err:
        return err

    try:
        payload = await request.json()
    except Exception:
        return _json_error("Invalid JSON body", code="INVALID_JSON", status=400)

    title = payload.get("title")
    if not title:
        return _json_error(
            "Missing required field 'title'", code="MISSING_FIELD", status=400
        )

    about = payload.get("about", "")
    is_channel = payload.get("is_channel", False)
    megagroup = payload.get("megagroup", True if not is_channel else False)
    users = payload.get("users", [])

    if isinstance(users, str):
        users = [u.strip() for u in users.split(",") if u.strip()]

    try:
        from telethon import functions, utils
        req = functions.channels.CreateChannelRequest(
            title=str(title),
            about=str(about),
            megagroup=megagroup,
            broadcast=is_channel,
        )
        result = await client(req)
        chat_info = {}
        if hasattr(result, "chats") and result.chats:
            c = result.chats[0]
            chat_info = {
                "id": utils.get_peer_id(c),
                "title": getattr(c, "title", title),
                "username": getattr(c, "username", None),
                "megagroup": getattr(c, "megagroup", False),
                "broadcast": getattr(c, "broadcast", False),
            }

            if users:
                user_entities = []
                for u in users:
                    target_u = "me" if str(u).lower() in ("me", "self") else u
                    try:
                        target_u = int(target_u)
                    except (ValueError, TypeError):
                        pass
                    user_entities.append(target_u)
                try:
                    await client(functions.channels.InviteToChannelRequest(
                        channel=c,
                        users=user_entities
                    ))
                except Exception as invite_err:
                    chat_info["invite_error"] = str(invite_err)

        return _json_success({
            "success": True,
            "created": True,
            "chat": chat_info
        })
    except Exception as e:
        logger.error("Failed to create chat: %s", e, exc_info=True)
        return _json_error(str(e), code="CREATE_CHAT_FAILED", status=500)


@require_auth
async def delete_chat(request: web.Request) -> web.Response:
    client, err = _get_client(request.app)
    if err:
        return err

    try:
        payload = await request.json()
    except Exception:
        return _json_error("Invalid JSON body", code="INVALID_JSON", status=400)

    chat = payload.get("chat") or payload.get("peer") or payload.get("entity")
    if not chat:
        return _json_error(
            "Missing required field 'chat'", code="MISSING_FIELD", status=400
        )

    revoke = payload.get("revoke", True)

    try:
        from telethon import functions, types
        target_entity = "me" if str(chat).lower() in ("me", "self") else chat
        try:
            target_entity = int(target_entity)
        except (ValueError, TypeError):
            pass

        entity = await client.get_entity(target_entity)
        deleted_completely = False
        if isinstance(entity, types.Channel):
            if getattr(entity, "creator", False):
                try:
                    await client(functions.channels.DeleteChannelRequest(channel=entity))
                    deleted_completely = True
                except Exception:
                    await client.delete_dialog(entity, revoke=revoke)
            else:
                await client.delete_dialog(entity, revoke=revoke)
        else:
            await client.delete_dialog(entity, revoke=revoke)

        return _json_success({
            "success": True,
            "chat": str(chat),
            "deleted_completely": deleted_completely
        })
    except Exception as e:
        logger.error("Failed to delete chat: %s", e, exc_info=True)
        return _json_error(str(e), code="DELETE_CHAT_FAILED", status=500)


@require_auth
async def run_command(request: web.Request) -> web.Response:
    kernel = request.app.get(app_keys.KERNEL)
    if kernel is None:
        return _json_error("Kernel is not available", code="KERNEL_UNAVAILABLE", status=503)

    try:
        payload = await request.json()
    except Exception:
        return _json_error("Invalid JSON body", code="INVALID_JSON", status=400)

    command = payload.get("command")
    if not command:
        return _json_error(
            "Missing required field 'command'", code="MISSING_FIELD", status=400
        )

    prefix = getattr(kernel, "custom_prefix", ".")
    command_str = str(command).strip()
    if command_str.startswith(prefix):
        command_str = command_str[len(prefix):].strip()

    args = payload.get("args")
    chat = payload.get("chat") or payload.get("chat_id") or payload.get("peer")
    reply_to = payload.get("reply_to")

    chat_id = None
    if chat is not None:
        chat_id = "me" if str(chat).lower() in ("me", "self") else chat
        try:
            chat_id = int(chat_id)
        except (ValueError, TypeError):
            pass

    if reply_to is not None:
        try:
            reply_to = int(reply_to)
        except (ValueError, TypeError):
            reply_to = None

    register = getattr(kernel, "register", None)
    if register is None or not hasattr(register, "invoke"):
        return _json_error(
            "kernel.register.invoke is not available",
            code="KERNEL_REGISTER_UNAVAILABLE",
            status=500
        )

    try:
        sent_msg = await register.invoke(
            command=command_str,
            args=args,
            chat_id=chat_id,
            reply_to=reply_to,
        )
        return _json_success({
            "success": True,
            "command": command_str,
            "args": args,
            "message": _serialize_message(sent_msg)
        })
    except Exception as e:
        logger.error("Failed to run command '%s': %s", command_str, e, exc_info=True)
        return _json_error(str(e), code="COMMAND_EXEC_FAILED", status=500)


@require_auth
async def exec_telegram(request: web.Request) -> web.Response:
    kernel = request.app.get(app_keys.KERNEL)
    if kernel is None:
        return _json_error("Kernel is not available", code="KERNEL_UNAVAILABLE", status=503)

    client = getattr(kernel, "client", None)
    bot = getattr(kernel, "bot_client", None)
    if client is None:
        return _json_error(
            "Telegram client is not available",
            code="CLIENT_UNAVAILABLE",
            status=503,
        )

    try:
        payload = await request.json()
    except Exception:
        return _json_error("Invalid JSON body", code="INVALID_JSON", status=400)

    code = payload.get("code")
    if not code or not str(code).strip():
        return _json_error(
            "Missing required field 'code'", code="MISSING_FIELD", status=400
        )
    code = str(code)

    # Optional timeout (seconds, capped)
    try:
        timeout_s = min(max(float(payload.get("timeout", 30)), 1), 300)
    except (TypeError, ValueError):
        timeout_s = 30

    try:
        compiled = _compile_exec_function(code)
    except SyntaxError as e:
        return _json_error(
            f"Syntax error: {e}", code="SYNTAX_ERROR", status=400
        )

    import asyncio

    local_vars: dict[str, Any] = {
        "client": client,
        "c": client,
        "bot": bot,
        "kernel": kernel,
        "k": kernel,
        "asyncio": asyncio,
        "telethon": __import__("telethon"),
        "Button": __import__("telethon").Button,
        "events": __import__("telethon").events,
    }

    output = io.StringIO()
    start_time = time.time()
    return_val = _NO_RETURN
    tb_raw = None

    try:
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            exec(compiled, local_vars)
            return_val = await asyncio.wait_for(
                local_vars["__exec"](), timeout=timeout_s
            )
    except asyncio.TimeoutError:
        return _json_error(
            f"Execution timed out after {timeout_s}s",
            code="TIMEOUT",
            status=504,
        )
    except Exception:
        tb_raw = traceback.format_exc()

    elapsed = round((time.time() - start_time) * 1000, 2)

    if tb_raw:
        logger.warning("exec_telegram failed: %s", tb_raw)
        clean_tb = tb_raw.replace("Traceback (most recent call last):\n", "", 1).rstrip()
        return _json_error(
            clean_tb.splitlines()[-1] if clean_tb else "Unknown error",
            code="EXEC_FAILED",
            status=500,
            details=clean_tb.splitlines(),
        )

    data: dict[str, Any] = {
        "success": True,
        "stdout": output.getvalue().rstrip("\n"),
        "elapsed_ms": elapsed,
    }
    if return_val is not _NO_RETURN:
        data["return"] = _format_exec_value(return_val)
    return _json_success(data)


@require_auth
async def download_media(request: web.Request) -> web.Response:
    """Download media from a message to the local Termux filesystem."""
    client, err = _get_client(request.app)
    if err:
        return err
    try:
        body = await request.json()
    except Exception:
        body = {}
    chat = body.get("chat") or body.get("chat_id") or body.get("peer")
    message_id = body.get("message_id")
    if message_id is None:
        return _json_error("Missing required field 'message_id'", code="MISSING_FIELD", status=400)
    if not chat:
        return _json_error("Missing required field 'chat'", code="MISSING_FIELD", status=400)
    try:
        message_id = int(message_id)
    except (ValueError, TypeError):
        return _json_error("Field 'message_id' must be an integer", code="INVALID_FIELD", status=400)

    default_dir = os.path.expanduser("~/Download/Operit/TelegramMedia")
    out_dir = body.get("out_dir") or default_dir
    os.makedirs(out_dir, exist_ok=True)
    base_name = body.get("file_name")

    try:
        target_entity = "me" if str(chat).lower() in ("me", "self") else chat
        try:
            target_entity = int(target_entity)
        except (ValueError, TypeError):
            pass
        msg = await client.get_messages(target_entity, ids=message_id)
        if msg is None or getattr(msg, "media", None) is None:
            return _json_error("Message not found or has no media", code="NO_MEDIA", status=404)
        base = base_name or str(message_id)
        # smart extension from actual media
        if not os.path.splitext(base)[1]:
            fobj = getattr(msg, "file", None)
            ext = None
            if fobj is not None:
                if getattr(fobj, "ext", None):
                    ext = fobj.ext
                elif getattr(fobj, "mime_type", None):
                    mapping = {
                        "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
                        "image/gif": ".gif", "video/mp4": ".mp4", "audio/mpeg": ".mp3",
                        "audio/ogg": ".ogg", "application/pdf": ".pdf",
                    }
                    ext = mapping.get(fobj.mime_type)
            ext = ext or ".jpg"
            base = base + ext
        path = await msg.download_media(file=os.path.join(out_dir, base))
        return _json_success({
            "success": True,
            "path": path,
            "message_id": message_id,
            "chat_id": getattr(msg, "chat_id", None),
        })
    except Exception as e:
        logger.error("Failed to download media: %s", e, exc_info=True)
        return _json_error(str(e), code="DOWNLOAD_MEDIA_FAILED", status=500)


@require_auth
async def click_button(request: web.Request) -> web.Response:
    """Click an inline button of a message by flat index."""
    client, err = _get_client(request.app)
    if err:
        return err
    try:
        body = await request.json()
    except Exception:
        body = {}
    chat = body.get("chat") or body.get("chat_id") or body.get("peer")
    message_id = body.get("message_id")
    button_index = body.get("button_index", 0)
    if message_id is None or not chat:
        return _json_error("Missing required fields 'chat' and 'message_id'", code="MISSING_FIELD", status=400)
    try:
        message_id = int(message_id)
        button_index = int(button_index)
    except (ValueError, TypeError):
        return _json_error("'message_id' and 'button_index' must be integers", code="INVALID_FIELD", status=400)

    try:
        target_entity = "me" if str(chat).lower() in ("me", "self") else chat
        try:
            target_entity = int(target_entity)
        except (ValueError, TypeError):
            pass
        msg = await client.get_messages(target_entity, ids=message_id)
        if msg is None:
            return _json_error("Message not found", code="MESSAGE_NOT_FOUND", status=404)
        btns = getattr(msg, "buttons", None)
        flat = []
        if btns:
            for row in btns:
                for b in row:
                    if b is not None:
                        flat.append(b)
        if not flat:
            return _json_error("Message has no buttons", code="NO_BUTTONS", status=404)
        if button_index < 0 or button_index >= len(flat):
            return _json_error(
                f"button_index out of range: 0..{len(flat)-1}", code="BUTTON_NOT_FOUND", status=400
            )
        btn = flat[button_index]
        await btn.click()
        return _json_success({
            "success": True,
            "clicked": {"index": button_index, "text": getattr(btn, "text", "")},
        })
    except Exception as e:
        logger.error("Failed to click button: %s", e, exc_info=True)
        return _json_error(str(e), code="CLICK_BUTTON_FAILED", status=500)


def setup(app: web.Application, kernel: Kernel) -> None:
    prefix = app.get(app_keys.API_EXTENDER_PREFIX, "/api/ext")
    logger.info("Registering telegram_api routes with prefix: %s", prefix)

    app.router.add_post(f"{prefix}/send_message", send_message)
    app.router.add_post(f"{prefix}/edit_message", edit_message)
    app.router.add_post(f"{prefix}/delete_messages", delete_messages)
    app.router.add_get(f"{prefix}/get_me", get_me)

    app.router.add_get(f"{prefix}/get_messages", get_messages)
    app.router.add_post(f"{prefix}/get_messages", get_messages)
    app.router.add_get(f"{prefix}/get_unread_messages", get_unread_messages)
    app.router.add_post(f"{prefix}/create_chat", create_chat)
    app.router.add_post(f"{prefix}/delete_chat", delete_chat)
    app.router.add_post(f"{prefix}/run_command", run_command)
    app.router.add_post(f"{prefix}/exec_telegram", exec_telegram)
    app.router.add_post(f"{prefix}/download_media", download_media)
    app.router.add_post(f"{prefix}/click_button", click_button)

    if not prefix.endswith("/v1"):
        app.router.add_post(f"{prefix}/v1/send_message", send_message)
        app.router.add_post(f"{prefix}/v1/edit_message", edit_message)
        app.router.add_post(f"{prefix}/v1/delete_messages", delete_messages)
        app.router.add_get(f"{prefix}/v1/get_me", get_me)

        app.router.add_get(f"{prefix}/v1/get_messages", get_messages)
        app.router.add_post(f"{prefix}/v1/get_messages", get_messages)
        app.router.add_get(f"{prefix}/v1/get_unread_messages", get_unread_messages)
        app.router.add_post(f"{prefix}/v1/create_chat", create_chat)
        app.router.add_post(f"{prefix}/v1/delete_chat", delete_chat)
        app.router.add_post(f"{prefix}/v1/run_command", run_command)
        app.router.add_post(f"{prefix}/v1/exec_telegram", exec_telegram)
    app.router.add_post(f"{prefix}/v1/download_media", download_media)
    app.router.add_post(f"{prefix}/v1/click_button", click_button)