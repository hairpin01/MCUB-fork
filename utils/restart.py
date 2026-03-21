# author: @Hairpin00
# version: 1.1.0
# description: kernel restart

import os
import sys
import time
import inspect
from typing import Optional

ALLOWED_RESTART_ARGS = {"--no-web", "--proxy-web", "--port", "--host", "--core"}
ARGS_WITH_VALUES = {"--proxy-web", "--port", "--host", "--core"}


async def _maybe_await(result) -> None:
    """Await a value only when it is awaitable."""
    if inspect.isawaitable(result):
        await result


async def _close_kernel_resources(kernel) -> None:
    """Close restart-sensitive kernel resources in a safe order."""
    db_conn = getattr(kernel, "db_conn", None)
    if db_conn and hasattr(db_conn, "close"):
        await _maybe_await(db_conn.close())

    scheduler = getattr(kernel, "scheduler", None)
    if not scheduler:
        return

    if hasattr(scheduler, "cancel_all_tasks"):
        scheduler.cancel_all_tasks()
        return

    if hasattr(scheduler, "stop"):
        await _maybe_await(scheduler.stop())


def build_safe_restart_args(
    argv: Optional[list[str]] = None,
    entrypoint: Optional[str] = None,
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


def safe_restart(argv: Optional[list[str]] = None, entrypoint: Optional[str] = None) -> None:
    """Restart current process with sanitized CLI args."""
    safe_args = build_safe_restart_args(argv=argv, entrypoint=entrypoint)
    os.execv(sys.executable, [sys.executable, *safe_args])


def write_restart_file(
    restart_file: str,
    chat_id: int,
    message_id: int,
    thread_id: Optional[int] = None,
) -> None:
    """
    Persist restart context for post-restart notification.
    Format: chat_id,msg_id,timestamp[,thread_id]
    """
    parts = [str(chat_id), str(message_id), str(time.time())]
    if thread_id is not None:
        parts.append(str(thread_id))
    with open(restart_file, "w", encoding="utf-8") as f:
        f.write(",".join(parts))


async def restart_kernel(
    kernel,
    chat_id: Optional[int] = None,
    message_id: Optional[int] = None,
    thread_id: Optional[int] = None,
):
    """
    Выполняет перезагрузку процесса юзербота.
    Сохраняет данные для пост-рестарт уведомления и корректно закрывает ресурсы.

    Args:
        kernel: экземпляр класса Kernel
        chat_id: ID чата для отправки уведомления после перезагрузки
        message_id: ID сообщения, которое будет отредактировано после перезагрузки
        thread_id: ID темы/топика (опционально)
    """
    kernel.logger.info("Restart...")

    # Сохраняем информацию о перезагрузке, если переданы чат и сообщение
    if chat_id is not None and message_id is not None:
        try:
            write_restart_file(
                kernel.RESTART_FILE,
                chat_id=chat_id,
                message_id=message_id,
                thread_id=thread_id,
            )
            kernel.logger.debug(f"Данные рестарта сохранены в {kernel.RESTART_FILE}")
        except Exception as e:
            kernel.logger.error(f"Не удалось сохранить данные рестарта: {e}")

    # Закрываем ресурсы ядра
    try:
        await _close_kernel_resources(kernel)
    except Exception as e:
        kernel.logger.error(f"Ошибка при закрытии ресурсов: {e}")

    # Перезапуск процесса
    safe_restart()
