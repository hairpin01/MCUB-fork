"""
setup wizard API
"""

import asyncio
import json
import logging
import os
import time
import traceback

import aiohttp_jinja2
from aiohttp import web

log = logging.getLogger("mcub.web.setup")

_SETUP_SESSION = "_mcub_setup_tmp"

def setup_routes(app: web.Application) -> None:
    app.router.add_get("/",                       index)
    app.router.add_get("/status",                 status)
    app.router.add_post("/api/setup/send_code",   api_send_code)
    app.router.add_post("/api/setup/verify_code", api_verify_code)
    app.router.add_get("/api/setup/state",        api_setup_state)
    app.router.add_get("/setup/reset",             setup_reset)
    # Bot management
    app.router.add_get("/bot",                    bot_page)
    app.router.add_post("/api/bot/verify_token",  api_bot_verify_token)
    app.router.add_post("/api/bot/save_token",    api_bot_save_token)
    app.router.add_post("/api/bot/start",         api_bot_start)
    app.router.add_get("/api/bot/status",         api_bot_status)
    app.router.add_static("/static", path="core/web/static", name="static")
    # serve logo from core/web/img/
    import os
    if os.path.isdir("core/web/img"):
        app.router.add_static("/static/img", path="core/web/img", name="img")

async def index(request: web.Request) -> web.Response:
    """Always show the setup wizard."""
    return aiohttp_jinja2.render_template("setup.html", request, {})


async def status(request: web.Request) -> web.Response:
    kernel = request.app.get("kernel")
    if kernel is None or not _is_configured(kernel):
        return web.json_response({"error": "Kernel not available"}, status=503)
    return web.json_response({
        "version":            kernel.VERSION,
        "prefix":             kernel.custom_prefix,
        "modules":            list(kernel.loaded_modules.keys()),
        "commands":           list(kernel.command_handlers.keys()),
        "uptime":             time.time() - kernel.start_time,
        "error_load_modules": kernel.error_load_modules,
    })

async def api_setup_state(request: web.Request) -> web.Response:
    s = request.app.get("setup_state") or {}
    return web.json_response({
        "has_session":   "client" in s,
        "awaiting_code": s.get("awaiting_code", False),
        "awaiting_2fa":  s.get("awaiting_2fa",  False),
        "done":          s.get("done",           False),
    })

async def api_send_code(request: web.Request) -> web.Response:
    print("\n[setup] === /api/setup/send_code called ===", flush=True)

    try:
        data = await request.json()
    except Exception as exc:
        print(f"[setup] bad JSON — {exc}", flush=True)
        return _err("Invalid JSON body")

    api_id_raw = str(data.get("api_id",   "")).strip()
    api_hash   = str(data.get("api_hash", "")).strip()
    phone      = str(data.get("phone",    "")).strip()

    print(f"[setup] api_id={api_id_raw!r}  phone={phone!r}", flush=True)

    if not api_id_raw.isdigit():
        return _err("API ID must be a number")
    if not api_hash:
        return _err("API Hash is required")
    if not phone.startswith("+"):
        return _err("Phone must start with + (e.g. +1234567890)")

    api_id = int(api_id_raw)

    state: dict = request.app.setdefault("setup_state", {})
    await _cleanup_state_client(state)
    _remove_session_files(_SETUP_SESSION)

    try:
        from telethon import TelegramClient
        from telethon.errors import FloodWaitError
    except ImportError:
        return _err("telethon is not installed — run: pip install telethon")

    print("[setup] Creating TelegramClient…", flush=True)
    client = TelegramClient(
        _SETUP_SESSION, api_id, api_hash,
        connection_retries=5, retry_delay=2, timeout=30,
    )

    try:
        print("[setup] Connecting to Telegram…", flush=True)
        await client.connect()
        print(f"[setup] Connected={client.is_connected()}. Requesting code…", flush=True)
        result = await client.send_code_request(phone)
        print(f"[setup] ✓ Code sent. hash={result.phone_code_hash!r}", flush=True)

    except FloodWaitError as exc:
        return _err(f"Too many attempts. Wait {exc.seconds} seconds.")

    except Exception as exc:
        tb = traceback.format_exc()
        print(f"[setup] SEND CODE FAILED:\n{tb}", flush=True)
        await _disconnect(client)
        return _err(_friendly_error(exc))

    state.clear()
    state.update({
        "client":          client,
        "api_id":          api_id,
        "api_hash":        api_hash,
        "phone":           phone,
        "phone_code_hash": result.phone_code_hash,
        "awaiting_code":   True,
        "awaiting_2fa":    False,
        "done":            False,
    })

    return web.json_response({"success": True, "message": "Code sent to Telegram"})

async def api_verify_code(request: web.Request) -> web.Response:
    print("\n[setup] === /api/setup/verify_code called ===", flush=True)

    state: dict = request.app.get("setup_state") or {}
    client = state.get("client")
    if client is None:
        return _err("No active session — please go back to step 1")

    try:
        data = await request.json()
    except Exception:
        return _err("Invalid JSON body")

    code     = str(data.get("code",     "")).strip()
    password = str(data.get("password", "")).strip()
    print(f"[setup] code={code!r}  has_password={bool(password)}", flush=True)

    from telethon.errors import (
        PhoneCodeInvalidError,
        PhoneCodeExpiredError,
        SessionPasswordNeededError,
        PasswordHashInvalidError,
        FloodWaitError,
    )

    # ── 2FA-only second call ──
    if state.get("awaiting_2fa") and not code:
        if not password:
            return _err("Password is required")
        print("[setup] Signing in with 2FA password…", flush=True)
        try:
            await client.sign_in(password=password)
        except PasswordHashInvalidError:
            return _err("Incorrect 2FA password")
        except Exception as exc:
            return _err(_friendly_error(exc))
        return await _finish_setup(request, state)

    if not code:
        return _err("Code is required")

    phone           = state["phone"]
    phone_code_hash = state["phone_code_hash"]
    print(f"[setup] sign_in phone={phone!r}", flush=True)

    try:
        await client.sign_in(phone, code, phone_code_hash=phone_code_hash)

    except SessionPasswordNeededError:
        print("[setup] 2FA required by account", flush=True)
        if password:
            try:
                await client.sign_in(password=password)
            except PasswordHashInvalidError:
                return _err("Incorrect 2FA password")
            except Exception as exc:
                return _err(_friendly_error(exc))
        else:
            state["awaiting_2fa"] = True
            return web.json_response({"requires_2fa": True})

    except PhoneCodeInvalidError:
        return _err("Invalid code — please check and try again")

    except PhoneCodeExpiredError:
        return _err("Code expired — go back and request a new one")

    except FloodWaitError as exc:
        return _err(f"Too many attempts — wait {exc.seconds}s", status=429)

    except Exception as exc:
        tb = traceback.format_exc()
        print(f"[setup] sign_in error:\n{tb}", flush=True)
        return _err(_friendly_error(exc))

    return await _finish_setup(request, state)

async def _finish_setup(request: web.Request, state: dict) -> web.Response:
    print("[setup] ✓ Auth OK — writing config.json…", flush=True)

    config = {
        "api_id":               state["api_id"],
        "api_hash":             state["api_hash"],
        "phone":                state["phone"],
        "command_prefix":       ".",
        "aliases":              {},
        "power_save_mode":      False,
        "2fa_enabled":          state.get("awaiting_2fa", False),
        "healthcheck_interval": 30,
        "developer_chat_id":    None,
        "language":             "ru",
        "theme":                "default",
        "proxy":                None,
        "inline_bot_token":     None,
        "inline_bot_username":  None,
        "db_version":           2,
    }

    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    print("[setup] config.json written", flush=True)

    await _disconnect(state.get("client"))
    _rename_session(_SETUP_SESSION, "user_session")

    state["done"]          = True
    state["awaiting_code"] = False
    state["awaiting_2fa"]  = False

    ev: asyncio.Event | None = request.app.get("setup_event")
    if ev is not None:
        ev.set()
        print("[setup] setup_event fired", flush=True)

    return web.json_response({
        "success": True,
        "message": "Setup complete! Kernel is starting…",
    })

def _err(msg: str, status: int = 400) -> web.Response:
    print(f"[setup] → error: {msg!r}", flush=True)
    return web.json_response({"error": msg}, status=status)


async def setup_reset(request: web.Request) -> web.Response:
    """Reset the setup and clear config.json and session files."""
    print("\n[setup] === /setup/reset called ===", flush=True)
    
    config_path = "config.json"
    session_files = [
        "user_session.session",
        "user_session.session-journal",
        "_mcub_setup_tmp.session",
        "_mcub_setup_tmp.session-journal",
    ]
    
    removed = []
    errors = []
    
    if os.path.exists(config_path):
        try:
            os.remove(config_path)
            removed.append(config_path)
        except Exception as e:
            errors.append(f"Failed to remove {config_path}: {e}")
    
    for sf in session_files:
        if os.path.exists(sf):
            try:
                os.remove(sf)
                removed.append(sf)
            except Exception as e:
                errors.append(f"Failed to remove {sf}: {e}")
    
    state: dict = request.app.get("setup_state") or {}
    await _cleanup_state_client(state)
    request.app["setup_state"] = {}
    
    print(f"[setup] Reset complete. Removed: {removed}", flush=True)
    if errors:
        print(f"[setup] Errors: {errors}", flush=True)
    
    raise web.HTTPFound(location="/")


def _friendly_error(exc: Exception) -> str:
    s = str(exc); low = s.lower()
    if "api_id" in low or "api_hash" in low:
        return "Invalid API ID or API Hash"
    if "phone" in low and "invalid" in low:
        return "Invalid phone number"
    if "connection" in low or "connect" in low:
        return f"Connection failed — check your internet. {s}"
    return s or repr(exc)


async def _cleanup_state_client(state: dict) -> None:
    await _disconnect(state.pop("client", None))


async def _disconnect(client) -> None:
    if client is None:
        return
    try:
        if client.is_connected():
            await client.disconnect()
    except Exception:
        pass


def _remove_session_files(name: str) -> None:
    for ext in (".session", ".session-journal"):
        p = name + ext
        if os.path.exists(p):
            try:
                os.remove(p)
                print(f"[setup] removed {p}", flush=True)
            except Exception as e:
                print(f"[setup] WARNING: cannot remove {p}: {e}", flush=True)


def _rename_session(src: str, dst: str) -> None:
    for ext in (".session", ".session-journal"):
        s, d = src + ext, dst + ext
        if os.path.exists(s):
            if os.path.exists(d):
                os.remove(d)
            os.rename(s, d)
            print(f"[setup] renamed {s} → {d}", flush=True)


async def bot_page(request: web.Request) -> web.Response:
    kernel = request.app.get("kernel")
    if kernel is None:
        return aiohttp_jinja2.render_template("setup.html", request, {})
    return aiohttp_jinja2.render_template("setup.html", request, {"bot_page": True})


async def api_bot_status(request: web.Request) -> web.Response:
    kernel = request.app.get("kernel")
    if kernel is None:
        return web.json_response({"error": "Kernel not ready"}, status=503)
    
    bot_token = kernel.config.get("inline_bot_token")
    bot_username = kernel.config.get("inline_bot_username")
    bot_running = False
    
    if hasattr(kernel, 'bot_client') and kernel.bot_client:
        try:
            bot_running = kernel.bot_client.is_connected()
        except Exception:
            pass
    
    return web.json_response({
        "has_token": bool(bot_token),
        "username": bot_username,
        "running": bot_running,
    })


async def api_bot_verify_token(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)
    
    token = data.get("token", "").strip()
    if not token:
        return web.json_response({"error": "Token is required"}, status=400)
    
    try:
        import aiohttp
    except ImportError:
        return web.json_response({"error": "aiohttp not installed"}, status=500)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.telegram.org/bot{token}/getMe") as resp:
                result = await resp.json()
                if result.get("ok"):
                    bot_info = result["result"]
                    return web.json_response({
                        "valid": True,
                        "username": bot_info.get("username"),
                        "name": bot_info.get("first_name"),
                    })
                else:
                    return web.json_response({
                        "valid": False,
                        "error": result.get("description", "Invalid token"),
                    })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def api_bot_save_token(request: web.Request) -> web.Response:
    kernel = request.app.get("kernel")
    if kernel is None:
        return web.json_response({"error": "Kernel not ready"}, status=503)
    
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)
    
    token = data.get("token", "").strip()
    if not token:
        return web.json_response({"error": "Token is required"}, status=400)
    
    kernel.config["inline_bot_token"] = token
    with open(kernel.CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(kernel.config, f, ensure_ascii=False, indent=2)
    
    return web.json_response({"success": True, "message": "Token saved. Restart kernel to apply."})


async def api_bot_start(request: web.Request) -> web.Response:
    kernel = request.app.get("kernel")
    if kernel is None:
        return web.json_response({"error": "Kernel not ready"}, status=503)
    
    token = kernel.config.get("inline_bot_token")
    if not token:
        return web.json_response({"error": "No bot token configured"}, status=400)
    
    try:
        from core_inline.bot import InlineBot
        inline_bot = InlineBot(kernel)
        await inline_bot.start_bot()
        return web.json_response({"success": True, "message": "Bot started"})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


def _is_configured(kernel) -> bool:
    if kernel is None:
        return os.path.exists("config.json")
    return bool(getattr(kernel, "config", {}).get("api_id"))


def _fmt_uptime(start_ts) -> str:
    if not start_ts:
        return "N/A"
    h, rem = divmod(int(time.time() - start_ts), 3600)
    m, s   = divmod(rem, 60)
    return f"{h:02}:{m:02}:{s:02}"
