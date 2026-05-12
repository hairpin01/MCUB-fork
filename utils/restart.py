# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01

# author: @Hairpin00
# version: 1.1.0
# description: kernel restart

import csv
import inspect
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ALLOWED_RESTART_ARGS = {"--no-web", "--proxy-web", "--port", "--host", "--core"}
ARGS_WITH_VALUES = {"--proxy-web", "--port", "--host", "--core"}


@dataclass(frozen=True)
class RestartContext:
    """Parsed restart notification context."""

    chat_id: int
    message_id: int
    timestamp: float
    thread_id: int | None = None


async def _maybe_await(result) -> None:
    """Await a value only when it is awaitable."""
    if inspect.isawaitable(result):
        await result


async def _close_kernel_resources(kernel) -> None:
    """Close restart-sensitive kernel resources in a safe order."""
    db_conn = getattr(kernel, "db_conn", None)
    if db_conn and hasattr(db_conn, "close"):
        await _maybe_await(db_conn.close())

    if hasattr(kernel, "session") and kernel.session is not None:
        if not kernel.session.closed:
            await kernel.session.close()
        kernel.session = None

    background_tasks = getattr(kernel, "_background_tasks", None)
    if background_tasks:
        for task in background_tasks:
            if not task.done():
                task.cancel()
        kernel._background_tasks = []

    scheduler = getattr(kernel, "scheduler", None)
    if scheduler:
        if hasattr(scheduler, "cancel_all_tasks"):
            scheduler.cancel_all_tasks()

        if hasattr(scheduler, "stop"):
            await _maybe_await(scheduler.stop())


def build_safe_restart_args(
    argv: list[str] | None = None,
    entrypoint: str | None = None,
) -> list[str]:
    """
    Build a sanitized argv list for process restart.

    Keeps only known kernel flags and drops flags requiring values
    when those values are missing.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    script = sys.argv[0] if entrypoint is None else entrypoint
    safe_args: list[str] = []

    if script.endswith("__main__.py"):
        safe_args.extend(["-m", "core"])

    i = 0
    while i < len(args):
        arg = args[i]
        key = arg.split("=", 1)[0]

        if key not in ALLOWED_RESTART_ARGS:
            i += 1
            continue

        if key in ARGS_WITH_VALUES and "=" not in arg:
            if i + 1 >= len(args):
                i += 1
                continue

            value = args[i + 1]
            if value.startswith("--"):
                i += 1
                continue

            safe_args.extend([arg, value])
            i += 2
            continue

        safe_args.append(arg)
        i += 1

    return safe_args


def safe_restart(argv: list[str] | None = None, entrypoint: str | None = None) -> None:
    """Restart current process with sanitized CLI args."""
    safe_args = build_safe_restart_args(argv=argv, entrypoint=entrypoint)
    os.execv(sys.executable, [sys.executable, *safe_args])


def write_restart_file(
    restart_file: str,
    chat_id: int,
    message_id: int,
    thread_id: int | None = None,
) -> None:
    """
    Persist restart context for post-restart notification.

    Current format is JSON. Readers intentionally keep support for the
    historical ``chat_id,msg_id,timestamp[,thread_id]`` CSV-like format so an
    update can still finish a restart that was initiated by an older build.
    """
    payload: dict[str, int | float] = {
        "chat_id": chat_id,
        "message_id": message_id,
        "timestamp": time.time(),
    }
    if thread_id is not None:
        payload["thread_id"] = thread_id
    with open(restart_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"))


def _coerce_restart_context(payload: dict[str, Any]) -> RestartContext:
    """Validate and normalize restart context values."""
    chat_id = int(payload["chat_id"])
    message_id = int(payload.get("message_id", payload.get("msg_id")))
    timestamp = float(payload.get("timestamp", payload.get("restart_time")))

    thread_value = payload.get("thread_id")
    thread_id = None if thread_value in (None, "") else int(thread_value)

    return RestartContext(
        chat_id=chat_id,
        message_id=message_id,
        timestamp=timestamp,
        thread_id=thread_id,
    )


def parse_restart_context(raw: str) -> RestartContext:
    """Parse restart context from robust JSON or legacy CSV data.

    Raises ``ValueError`` when the file is empty, malformed or missing required
    fields. Legacy CSV is parsed with ``csv.reader`` instead of brittle
    ``str.split(',')`` to handle whitespace and quoted values predictably.
    """
    text = raw.strip()
    if not text:
        raise ValueError("restart context is empty")

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        rows = list(csv.reader([text], skipinitialspace=True))
        if not rows or len(rows[0]) < 3:
            raise ValueError("legacy restart context must have at least 3 fields")

        row = rows[0]
        payload = {
            "chat_id": row[0],
            "message_id": row[1],
            "timestamp": row[2],
        }
        if len(row) >= 4:
            payload["thread_id"] = row[3]
    else:
        if not isinstance(payload, dict):
            raise ValueError("restart context JSON must be an object")

    try:
        return _coerce_restart_context(payload)
    except (KeyError, TypeError, ValueError) as e:
        raise ValueError(f"invalid restart context: {e}") from e


def read_restart_context(restart_file: str | os.PathLike[str]) -> RestartContext:
    """Read and parse a restart context file."""
    return parse_restart_context(Path(restart_file).read_text(encoding="utf-8"))


async def restart_kernel(
    kernel,
    chat_id: int | None = None,
    message_id: int | None = None,
    thread_id: int | None = None,
):
    """
    Выпoлняeт пepeзaгpyзкy пpoцecca юзepбoтa.
    Coxpaняeт дaнныe для пocт-pecтapт yвeдoмлeния и кoppeктнo зaкpывaeт pecypcы.

    Args:
        kernel: экзeмпляp клacca Kernel
        chat_id: ID чaтa для oтпpaвки yвeдoмлeния пocлe пepeзaгpyзки
        message_id: ID cooбщeния, кoтopoe бyдeт oтpeдaктиpoвaнo пocлe пepeзaгpyзки
        thread_id: ID тeмы/тoпикa (oпциoнaльнo)
    """
    kernel.logger.info("Restart...")

    # Save restart info if chat and message were passed
    if chat_id is not None and message_id is not None:
        try:
            write_restart_file(
                kernel.RESTART_FILE,
                chat_id=chat_id,
                message_id=message_id,
                thread_id=thread_id,
            )
            kernel.logger.debug(f"Дaнныe pecтapтa coxpaнeны в {kernel.RESTART_FILE}")
        except Exception as e:
            kernel.logger.error(f"He yдaлocь coxpaнить дaнныe pecтapтa: {e}")

    # Close kernel resources
    try:
        await _close_kernel_resources(kernel)
    except Exception as e:
        kernel.logger.error(f"Oшибкa пpи зaкpытии pecypcoв: {e}")

    # Restart process
    safe_restart()
